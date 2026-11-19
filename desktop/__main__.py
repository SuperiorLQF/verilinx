"""Run the Qt editor with python -m desktop."""

import argparse
from copy import deepcopy
from functools import partial
import json
from pathlib import Path
import sys
from uuid import uuid4

from PySide6.QtCore import QIODevice, QObject, QRunnable, QSaveFile, QThreadPool, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QDockWidget,
    QFileDialog, QFormLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QTabWidget, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from backend import main as engine
from backend.engine import identifier, MAX_BYTES
from .canvas import BlockItem, Canvas, EdgeItem, terminal_rect

COMPONENTS = {
    "input": "顶层输入", "output": "顶层输出", "constant": "常量",
    "split": "分线器", "concat": "集线器", "reshape": "形状转换",
}


def component(kind, name, position):
    def port(label, role, width=8, lanes=0):
        return {"name": label, "role": role, "shape": {"packed": [[width - 1, 0]] if width > 1 else [],
                "unpacked": [[0, lanes - 1]] if lanes else [], "atom_width": 1}}
    if kind == "split":
        ports = [port("in", "target", 16), port("high", "source"), port("low", "source")]
    elif kind == "concat":
        ports = [port("high", "target"), port("low", "target"), port("out", "source", 16)]
    elif kind == "reshape":
        ports = [port("in", "target", 8, 6), port("out", "source", 48)]
    elif kind == "output":
        ports = [port("in", "target")]
    else:
        ports = [port("out", "source")]
    return {"id": str(uuid4()), "name": name, "kind": kind, "position": position,
            "ports": ports, "expression": "8'h00"}


def reanalyze_parameters(project):
    engine.parameters(engine.ProjectRequest(project=project))
    for index, node in enumerate(project["nodes"]):
        if node["kind"] == "module":
            project["nodes"][index] = engine.analyze_instance(engine.InstanceRequest(project=project, node=node))
    return project


def analyze_node(project, node):
    request = engine.InstanceRequest(project=project, node=node)
    return engine.analyze_instance(request) if node["kind"] == "module" else engine.analyze_component(request)


def bundle_request(path):
    if path.stat().st_size > MAX_BYTES * 8:
        raise ValueError("源码包文件过大。")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and all(isinstance(value, str) for value in data.values()):
        entries = [name for name in data if "/" not in name and name.lower().endswith(".f")]
        if "project.f" in data:
            entry = "project.f"
        elif len(entries) == 1:
            entry = entries[0]
        else:
            raise ValueError("源码包需要 project.f 或唯一的根目录 filelist。也可用 files 和 filelist 字段指定入口。")
        return engine.ImportRequest(files=data, filelist=entry)
    return engine.ImportRequest.model_validate(data)


class JobSignals(QObject):
    finished = Signal(object, object)


class Job(QRunnable):
    def __init__(self, operation):
        super().__init__()
        self.operation = operation
        self.signals = JobSignals()

    def run(self):
        try:
            result = self.operation()
        except Exception as error:
            self.signals.finished.emit(None, error)
        else:
            self.signals.finished.emit(result, None)


class Form(QDialog):
    def __init__(self, title, parent):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 300)
        self.fields = QFormLayout(self)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    def text(self, label, value):
        widget = QLineEdit(value)
        self.fields.addRow(label, widget)
        return widget

    def multiline(self, label, value):
        widget = QPlainTextEdit(value)
        self.fields.addRow(label, widget)
        return widget

    def run(self):
        if self.buttons.parent() is None:
            self.fields.addRow(self.buttons)
        return self.exec() == QDialog.DialogCode.Accepted


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1360, 870)
        self.project = None
        self.dirty = False
        self.current_file = None
        self.job = None
        self.on_job_finished = None

        self.canvas = Canvas()
        self.setCentralWidget(self.canvas)
        self.canvas.message.connect(self.statusBar().showMessage)
        self.canvas.modified.connect(self.mark_dirty)
        self.canvas.edit_requested.connect(self.edit_node)
        self.canvas.scene().selectionChanged.connect(self.update_actions)

        self.modules = QListWidget()
        self.modules.itemDoubleClicked.connect(lambda item: self.add_module(item.text()))
        self.search = QLineEdit(placeholderText="筛选模块…")
        self.search.textChanged.connect(self.filter_modules)
        self.add_module_button = QPushButton("添加所选模块")
        self.add_module_button.clicked.connect(self.add_selected_module)
        self.modules.currentItemChanged.connect(self.update_actions)
        module_panel = QWidget()
        module_layout = QVBoxLayout(module_panel)
        module_layout.addWidget(self.search)
        module_layout.addWidget(self.modules)
        module_layout.addWidget(self.add_module_button)

        component_panel = QWidget()
        component_layout = QVBoxLayout(component_panel)
        self.component_buttons = []
        for kind, label in COMPONENTS.items():
            button = QPushButton(label)
            button.clicked.connect(partial(self.add_component, kind))
            component_layout.addWidget(button)
            self.component_buttons.append(button)
        component_layout.addStretch(1)
        library = QTabWidget()
        library.addTab(module_panel, "模块库")
        library.addTab(component_panel, "信号组件")
        self.add_dock("设计资源", Qt.DockWidgetArea.LeftDockWidgetArea, library)

        self.output = QTabWidget()
        self.log = QPlainTextEdit(readOnly=True)
        self.rtl = QPlainTextEdit(readOnly=True)
        self.rtl.setStyleSheet("font-family: monospace")
        self.output.addTab(self.log, "诊断")
        self.output.addTab(self.rtl, "SystemVerilog")
        self.output_dock = self.add_dock("输出", Qt.DockWidgetArea.BottomDockWidgetArea, self.output)
        self.resizeDocks([self.output_dock], [155], Qt.Orientation.Vertical)

        files = self.menuBar().addMenu("文件")
        design = self.menuBar().addMenu("设计")
        view = self.menuBar().addMenu("视图")
        toolbar = QToolBar("工程")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        self.import_action = self.action(files, toolbar, "导入 filelist", self.import_filelist)
        self.bundle_action = self.action(files, None, "导入 JSON 源码包", self.import_bundle)
        self.open_action = self.action(files, toolbar, "打开工程", self.open_project, QKeySequence.StandardKey.Open)
        examples = files.addMenu("示例")
        self.action(examples, None, "LED 闪灯示例", self.load_demo)
        self.examples_action = examples.menuAction()
        self.examples_button = QToolButton(toolbar)
        self.examples_button.setText(examples.title())
        self.examples_button.setMenu(examples)
        self.examples_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbar.addWidget(self.examples_button)
        toolbar.addSeparator()
        self.parameters_action = self.action(design, toolbar, "顶层参数", self.edit_parameters)
        self.check_action = self.action(design, toolbar, "检查设计", self.check)
        self.export_action = self.action(files, toolbar, "导出顶层", self.export, QKeySequence.StandardKey.Save)
        toolbar.addSeparator()
        self.edit_action = self.action(design, toolbar, "配置节点", self.edit_selected)
        self.redraw_action = self.action(design, toolbar, "重画连线", self.canvas.redraw_wire)
        self.delete_action = self.action(design, None, "删除选中项", self.canvas.delete_selected)
        self.select_action = self.action(design, None, "全选", self.select_all, QKeySequence.StandardKey.SelectAll)
        align = design.addMenu("批量对齐")
        self.align_actions = [
            self.action(align, None, label, partial(self.align, axis, side))
            for label, axis, side in (
                ("左边缘", "x", "min"), ("水平居中", "x", "center"), ("右边缘", "x", "max"),
                ("顶边缘", "y", "min"), ("垂直居中", "y", "center"), ("底边缘", "y", "max"),
            )
        ]
        self.fit_action = self.action(view, toolbar, "适应画布", self.canvas.fit_design, "F")
        view.addAction(self.output_dock.toggleViewAction())
        self.statusBar().showMessage("导入 filelist、打开 .sv 工程，或从「示例」中选择一个工程。")
        self.setStyleSheet("""
            QMainWindow { background: #f5f7f8; }
            QToolBar { background: #fff; border-bottom: 1px solid #d4e0df; padding: 5px; spacing: 5px; }
            QToolButton { padding: 5px 8px; border-radius: 4px; }
            QToolButton:hover { background: #e5f2ee; }
            QDockWidget::title { background: #eaf0ef; padding: 6px; }
            QGraphicsView { border: 0; }
        """)
        self.refresh_title()
        self.update_actions()

    def add_dock(self, title, area, widget):
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        return dock

    def action(self, menu, toolbar, text, function, shortcut=None):
        action = QAction(text, self)
        action.triggered.connect(function)
        if shortcut:
            action.setShortcut(shortcut)
        menu.addAction(action)
        if toolbar:
            toolbar.addAction(action)
        return action

    def refresh_title(self):
        title = self.project["name"] if self.project else "未命名工程"
        self.setWindowTitle(f"{title}[*]  ·  Verilinx")
        self.setWindowModified(self.dirty)

    def mark_dirty(self):
        self.dirty = True
        self.refresh_title()

    def update_actions(self, *_):
        if not hasattr(self, "fit_action"):
            return
        ready = self.project is not None and self.job is None
        selected = self.canvas.scene().selectedItems()
        block = self.canvas.selected_block()
        for action in (self.parameters_action, self.check_action, self.export_action, self.fit_action, self.select_action):
            action.setEnabled(ready)
        self.edit_action.setEnabled(ready and block is not None)
        self.redraw_action.setEnabled(ready and sum(isinstance(item, EdgeItem) for item in selected) == 1)
        self.delete_action.setEnabled(ready and bool(selected))
        for action in self.align_actions:
            action.setEnabled(ready and sum(isinstance(item, BlockItem) for item in selected) > 1)
        for button in self.component_buttons:
            button.setEnabled(ready)
        self.add_module_button.setEnabled(ready and self.modules.currentItem() is not None)

    def set_project(self, project, *, replace=False, path=None):
        self.project = project
        shifted = self.canvas.load(project, fit=replace)
        if replace:
            self.current_file = path
            self.dirty = bool(path is not None and shifted)
            self.log.clear()
            self.rtl.clear()
            self.filter_modules()
        self.refresh_title()
        self.update_actions()
        return shifted

    def filter_modules(self, *_):
        self.modules.clear()
        if self.project:
            query = self.search.text().casefold()
            self.modules.addItems([module["name"] for module in self.project.get("modules", [])
                                   if query in module["name"].casefold()])
        self.update_actions()

    def replace_allowed(self):
        if self.job is not None:
            return False
        if not self.dirty:
            return True
        choice = QMessageBox.question(self, "未导出的修改", "放弃当前工程中尚未导出的修改？",
                                      QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                      QMessageBox.StandardButton.Cancel)
        return choice == QMessageBox.StandardButton.Discard

    def closeEvent(self, event: QCloseEvent):
        if self.replace_allowed():
            event.accept()
        else:
            event.ignore()

    def job_error(self, error):
        detail = str(error)
        self.log.appendPlainText(detail)
        self.output.setCurrentWidget(self.log)
        self.output_dock.show()
        self.statusBar().showMessage("操作未完成，详情见诊断。")

    def run_job(self, message, operation, done):
        if self.job is not None:
            return
        self.canvas.cancel_wire()
        self.job = Job(operation)
        self.on_job_finished = done
        self.job.signals.finished.connect(self.finish_job, Qt.ConnectionType.QueuedConnection)
        self.canvas.setEnabled(False)
        for action in (self.import_action, self.bundle_action, self.open_action, self.examples_action):
            action.setEnabled(False)
        self.examples_button.setEnabled(False)
        self.update_actions()
        self.statusBar().showMessage(message)
        QThreadPool.globalInstance().start(self.job)

    @Slot(object, object)
    def finish_job(self, result, error):
        done = self.on_job_finished
        self.job = self.on_job_finished = None
        self.canvas.setEnabled(True)
        for action in (self.import_action, self.bundle_action, self.open_action, self.examples_action):
            action.setEnabled(True)
        self.examples_button.setEnabled(True)
        self.update_actions()
        if error:
            self.job_error(error)
            return
        try:
            done(result)
        except (OSError, ValueError) as failure:
            self.job_error(failure)

    def loaded(self, project, path=None):
        shifted = self.set_project(project, replace=True, path=path)
        suffix = f" · 已调整 {shifted} 个节点的布局" if shifted else ""
        self.statusBar().showMessage(f"{project['name']} · {len(project.get('modules', []))} 个模块{suffix}")

    def load_demo(self):
        if self.replace_allowed():
            self.run_job("正在载入 LED 闪灯示例…", engine.demo, self.loaded)

    def import_filelist(self):
        if self.job:
            return
        filename, _ = QFileDialog.getOpenFileName(self, "选择入口 filelist", "", "Filelist (*.f *.F);;所有文件 (*)")
        if not filename:
            return
        path = Path(filename)
        root, ok = QInputDialog.getText(self, "项目根目录", "包含入口文件及其依赖的根目录", text=str(path.parent))
        if not ok or not self.replace_allowed():
            return
        try:
            entry = path.relative_to(Path(root).expanduser().resolve()).as_posix()
        except ValueError:
            self.job_error("入口 filelist 必须位于项目根目录内。")
            return
        request = engine.ImportRequest(filelist=entry, directory=str(Path(root).expanduser()))
        self.run_job("slang 正在分析 filelist…", partial(engine.import_files, request), self.loaded)

    def import_bundle(self):
        if self.job:
            return
        filename, _ = QFileDialog.getOpenFileName(self, "打开 JSON 源码包", "", "JSON (*.json)")
        if not filename or not self.replace_allowed():
            return

        def load():
            return engine.import_files(bundle_request(Path(filename)))

        self.run_job("slang 正在分析源码包…", load, self.loaded)

    def open_project(self):
        if self.job:
            return
        filename, _ = QFileDialog.getOpenFileName(self, "打开顶层工程", "", "SystemVerilog (*.sv *.v)")
        if filename and self.replace_allowed():
            self.restore_file(Path(filename))

    def restore_file(self, path):
        def restore():
            return engine.restore(engine.TextRequest(text=path.read_text(encoding="utf-8")))

        self.run_job("正在恢复工程…", restore, lambda project: self.loaded(project, path))

    def new_name(self, prefix):
        used = {node["name"] for node in self.project["nodes"]}
        suffix = 0
        while f"{prefix}_{suffix}" in used:
            suffix += 1
        return f"{prefix}_{suffix}"

    def new_position(self, kind=None):
        center = self.canvas.mapToScene(self.canvas.viewport().rect().center())
        count = len(self.project["nodes"]) % 6
        origin_x, origin_y = 136, 70
        if kind in ("input", "output"):
            origin = terminal_rect(kind).center()
            origin_x, origin_y = origin.x(), origin.y()
        return {"x": center.x() - origin_x + 28 * count, "y": center.y() - origin_y + 22 * count}

    def commit_node(self, node):
        project = self.project
        for index, current in enumerate(project["nodes"]):
            if current["id"] == node["id"]:
                project["nodes"][index] = node
                break
        else:
            project["nodes"].append(node)
        self.set_project(project)
        self.canvas.blocks[node["id"]].setSelected(True)
        self.canvas.ensureVisible(self.canvas.blocks[node["id"]])
        self.mark_dirty()
        self.statusBar().showMessage(f"已更新 {node['name']}")

    def add_selected_module(self):
        item = self.modules.currentItem()
        if item:
            self.add_module(item.text())

    def add_module(self, module):
        if self.project is None or self.job:
            return
        node = {"id": str(uuid4()), "kind": "module", "module": module, "name": self.new_name(f"U_{module}"),
                "overrides": {}, "count": "1", "position": self.new_position()}
        self.run_job("正在求值模块默认参数…", partial(analyze_node, deepcopy(self.project), node), self.commit_node)

    def add_component(self, kind, *_):
        if self.project is None or self.job:
            return
        node = component(kind, self.new_name(kind), self.new_position(kind))
        self.edit_node(node["id"], new=node)

    def edit_selected(self):
        item = self.canvas.selected_block()
        if item:
            self.edit_node(item.block["id"])

    def edit_node(self, node_id, *, new=None):
        if self.project is None or self.job:
            return
        current = new if new is not None else next(n for n in self.project["nodes"] if n["id"] == node_id)
        node = deepcopy(current)
        form = Form("配置 " + node.get("module", COMPONENTS.get(node["kind"], node["kind"])), self)
        name = form.text("节点名称", node["name"])
        module = node["kind"] == "module"
        if module:
            count = form.text("generate 数量", node.get("count", "1"))
            overrides = form.multiline("参数覆盖", "\n".join(f"{key} = {value}" for key, value in node.get("overrides", {}).items()))
        else:
            ports = form.multiline("端口定义（JSON）", json.dumps(node["ports"], indent=2, ensure_ascii=False))
            if node["kind"] == "constant":
                expression = form.text("常量表达式", node.get("expression", ""))
        while True:
            if not form.run():
                return
            try:
                node["name"] = identifier(name.text().strip())
                if module:
                    node["count"] = count.text().strip()
                    node["overrides"] = {}
                    for line in overrides.toPlainText().splitlines():
                        if line.strip():
                            key, separator, value = line.partition("=")
                            if not separator or not key.strip() or not value.strip():
                                raise ValueError("每行填写 NAME = expression。")
                            node["overrides"][key.strip()] = value.strip()
                else:
                    node["ports"] = json.loads(ports.toPlainText())
                    if node["kind"] == "constant":
                        node["expression"] = expression.text()
                break
            except ValueError as error:
                QMessageBox.warning(form, "检查输入", str(error))
        self.run_job("正在检查节点配置…", partial(analyze_node, deepcopy(self.project), node), self.commit_node)

    def edit_parameters(self):
        if self.project is None or self.job:
            return
        form = Form("顶层参数", self)
        name = form.text("顶层模块名", self.project["name"])
        params = form.multiline("每行一条 parameter", self.project["parameters"])
        if not form.run():
            return
        project = deepcopy(self.project)
        try:
            project["name"] = identifier(name.text().strip())
        except ValueError as error:
            self.job_error(error)
            return
        project["parameters"] = params.toPlainText()

        def done(result):
            self.set_project(result)
            self.mark_dirty()
            self.statusBar().showMessage("已更新顶层参数。")

        self.run_job("正在重新求值所有实例…", partial(reanalyze_parameters, project), done)

    def snapshot(self):
        if self.canvas.draft:
            self.statusBar().showMessage("请完成或取消当前布线。")
            return None
        project = deepcopy(self.project)
        project["viewport"] = self.canvas.saved_viewport()
        # The editor recomputes detours from the node positions on each load.
        return project

    def check(self):
        if self.project is None or self.job:
            return
        project = self.snapshot()
        if project is None:
            return
        self.run_job("正在检查设计并生成 RTL…", lambda: engine.analyze(engine.ProjectRequest(project=project)), self.checked)

    def checked(self, result):
        self.log.setPlainText("\n".join([*result["warnings"], result["diagnostics"] or "slang 检查通过"]))
        self.rtl.setPlainText(result["rtl"])
        self.output.setCurrentWidget(self.log)
        self.output_dock.show()
        self.statusBar().showMessage("检查完成，有未连接端口。" if result["warnings"] else "检查通过。")

    def export(self):
        if self.project is None or self.job:
            return
        project = self.snapshot()
        if project is None:
            return
        suggest = str(self.current_file or (Path.cwd() / f"{project['name']}.sv"))
        filename, _ = QFileDialog.getSaveFileName(self, "导出顶层工程", suggest, "SystemVerilog (*.sv)")
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != ".sv":
            path = path.with_name(path.name + ".sv")

        def done(result):
            target = QSaveFile(str(path))
            data = result["text"].encode("utf-8")
            if not target.open(QIODevice.OpenModeFlag.WriteOnly) or target.write(data) != len(data) or not target.commit():
                raise OSError(target.errorString())
            self.current_file = path
            self.dirty = False
            self.refresh_title()
            self.rtl.setPlainText(result["text"])
            self.statusBar().showMessage(f"已导出 {path}")

        self.run_job("正在编译顶层工程…", lambda: engine.export(engine.ProjectRequest(project=project)), done)

    def select_all(self):
        if self.canvas.draft:
            return
        for item in [*self.canvas.blocks.values(), *self.canvas.edges.values()]:
            item.setSelected(True)

    def align(self, axis, side, *_):
        if self.canvas.draft:
            return
        items = [item for item in self.canvas.scene().selectedItems() if isinstance(item, BlockItem)]
        if len(items) < 2:
            return
        rects = [item.body_rect.translated(item.pos()) for item in items]
        horizontal = axis == "x"
        near = min(rect.left() if horizontal else rect.top() for rect in rects)
        far = max(rect.right() if horizontal else rect.bottom() for rect in rects)
        for item, rect in zip(items, rects):
            start = rect.left() if horizontal else rect.top()
            end = rect.right() if horizontal else rect.bottom()
            if side == "min":
                delta = near - start
            elif side == "max":
                delta = far - end
            else:
                delta = (near + far - start - end) / 2
            item.moveBy(delta if horizontal else 0, 0 if horizontal else delta)


def main():
    parser = argparse.ArgumentParser(description="Verilinx Qt desktop editor")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--demo", action="store_true", help="load the default example at launch")
    source.add_argument("project", nargs="?", type=Path, help="open a Verilinx .sv project")
    args = parser.parse_args()
    app = QApplication([sys.argv[0]])
    app.setApplicationName("Verilinx")
    window = Window()
    window.show()
    if args.demo:
        QTimer.singleShot(0, window.load_demo)
    elif args.project:
        QTimer.singleShot(0, partial(window.restore_file, args.project))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
