"""Smoke the Qt workflow with real widget events and the shared compiler."""

from itertools import pairwise, product
from pathlib import Path

import pytest


def test_retraced_branch_at_a_bend_is_removed():
    from desktop.routing import simple_path

    path = [(0, 0), (60, 0), (60, 50), (40, 50), (40, 30), (60, 30), (100, 30)]
    assert simple_path(path) == [(0, 0), (60, 0), (60, 30), (100, 30)]
    assert simple_path([(0, 0), (60, 0), (40, 0), (40, 10)]) == [(0, 0), (40, 0), (40, 10)]


def test_fanout_dot_tracks_shared_branch_and_disappears_with_wire(monkeypatch, six_lane_project):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    from desktop.canvas import Canvas

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    canvas = Canvas()
    try:
        canvas.load(six_lane_project)
        split = canvas.edges["processor_data_out_split_in"]
        reshape = canvas.edges["processor_data_out_reshape_in"]
        junction = split.routed[1]
        assert junction == reshape.routed[1]
        assert canvas.junctions == {junction}
        split.setSelected(True)
        canvas.delete_selected()
        assert not canvas.junctions
        assert canvas.edges["processor_data_out_reshape_in"].routed
    finally:
        canvas.close()


def test_terminal_symbols_keep_existing_socket_positions(monkeypatch, six_lane_project):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication

    from desktop.canvas import Canvas

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    canvas = Canvas()
    design = six_lane_project
    saved_edges = [edge.copy() for edge in design["edges"]]
    try:
        canvas.load(design)
        source = canvas.blocks["din"]
        target = canvas.blocks["bus"]
        processor = canvas.blocks["processor"]
        assert source.body_rect.width() < processor.body_rect.width()
        assert target.body_rect.height() < processor.body_rect.height()
        assert not source.shape().contains(source.body_rect.topRight() + QPointF(-2, 2))
        assert not target.shape().contains(target.body_rect.topLeft() + QPointF(2, 2))
        assert source.ports["out"].anchor() == source.pos() + QPointF(280, 80)
        assert target.ports["in"].anchor() == target.pos() + QPointF(-8, 80)
        assert design["edges"] == saved_edges
        assert all(edge.routed for edge in canvas.edges.values())

        socket = source.ports["out"]
        top = QPointF(source.body_rect.center().x(), source.body_rect.top())
        canvas.move_port(socket, source.mapToScene(top))
        assert socket.port.side == "top"
        assert socket.anchor() == source.mapToScene(top) + QPointF(0, -8)
        assert source.block["portLayout"]["out"] == {"side": "top", "offset": .5}
    finally:
        canvas.close()


def test_shift_port_drag_highlights_and_jumps_over_adjacent_port(monkeypatch):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from desktop.__main__ import component
    from desktop.canvas import Canvas, PORT_LABEL_HEIGHT
    from desktop.placement import LABEL_GAP, PORT_GAP

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    canvas = Canvas()
    canvas.resize(850, 550)
    canvas.show()
    design = component("reshape", "adapter", {"x": 0, "y": 0})
    design["ports"].append({**design["ports"][0], "name": "spare"})
    design["portLayout"] = {"in": {"side": "right", "offset": .61}, "out": {"side": "right", "offset": .85}}
    label_spacing = PORT_LABEL_HEIGHT + LABEL_GAP
    project = {"nodes": [design], "edges": []}
    try:
        assert canvas.load(project, fit=True) == 0
        node = canvas.blocks[design["id"]]
        fixed, moving = node.ports["in"], node.ports["out"]
        cursor = canvas.mapFromScene(moving.scenePos())
        QTest.mouseMove(canvas.viewport(), cursor)
        assert not moving.drag_ready
        QTest.keyPress(canvas, Qt.Key.Key_Shift)
        assert moving.drag_ready and not fixed.drag_ready
        QTest.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, cursor)

        for dy in (5, -5):
            cursor = canvas.mapFromScene(fixed.scenePos() + QPointF(0, dy))
            event = QMouseEvent(QEvent.Type.MouseMove, QPointF(cursor), QPointF(canvas.viewport().mapToGlobal(cursor)),
                                Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier)
            app.sendEvent(canvas.viewport(), event)
            assert moving.port.side == "right"
            assert moving.y() - fixed.y() == pytest.approx(label_spacing if dy > 0 else -label_spacing)
            assert moving.drag_ready

        QTest.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, cursor)
        QTest.keyRelease(canvas, Qt.Key.Key_Shift)
        assert not moving.drag_ready and not fixed.drag_ready
        assert canvas.load(project) == 0

        design["portLayout"]["out"] = design["portLayout"]["in"].copy()
        assert canvas.load(project) == 1
        node = canvas.blocks[design["id"]]
        assert abs(node.ports["in"].y() - node.ports["out"].y()) == pytest.approx(label_spacing)

        design["portLayout"]["in"] = {"side": "top", "offset": .975}
        canvas.load(project)
        node = canvas.blocks[design["id"]]
        fixed, moving = node.ports["in"], node.ports["out"]
        canvas.move_port(moving, node.mapToScene(node.body_rect.topRight() + QPointF(0, 5)))
        gap = moving.pos() - fixed.pos()
        assert gap.x() ** 2 + gap.y() ** 2 >= PORT_GAP ** 2 - 1e-7
    finally:
        canvas.close()


@pytest.mark.parametrize("horizontal", [True, False])
def test_shift_drag_snaps_a_port_to_its_connected_peer(monkeypatch, horizontal):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from desktop.__main__ import component
    from desktop.canvas import Canvas

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    canvas = Canvas()
    canvas.resize(1000, 650)
    canvas.show()
    source = component("input", "source", {"x": 0, "y": 240})
    target = component("output", "target", {"x": 550 if horizontal else 114, "y": 260 if horizontal else 0})
    if not horizontal:
        source["portLayout"] = {"out": {"side": "top", "offset": .62}}
        target["portLayout"] = {"in": {"side": "bottom", "offset": .5}}
    net = {"id": "net", "source": source["id"], "sourcePort": "out",
           "target": target["id"], "targetPort": "in"}
    try:
        project = {"nodes": [source, target], "edges": [net]}
        canvas.load(project, fit=True)
        canvas.resetTransform()
        canvas.centerOn(340, 245)
        edge = canvas.edges["net"]
        moving, fixed = edge.source, edge.target
        coordinate = QPointF.y if horizontal else QPointF.x
        desired = fixed.scenePos()
        destination = QPointF(moving.scenePos().x(), desired.y() - 4) if horizontal else QPointF(desired.x() - 4, moving.scenePos().y())
        cursor = canvas.mapFromScene(destination)
        shift = Qt.KeyboardModifier.ShiftModifier
        QTest.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, shift, canvas.mapFromScene(moving.scenePos()))
        assert canvas.port_drag is moving

        for modifiers in (shift | Qt.KeyboardModifier.AltModifier, shift):
            event = QMouseEvent(QEvent.Type.MouseMove, QPointF(cursor), QPointF(canvas.viewport().mapToGlobal(cursor)),
                                Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, modifiers)
            app.sendEvent(canvas.viewport(), event)
            expected = coordinate(desired) if modifiers == shift else coordinate(destination)
            assert coordinate(moving.scenePos()) == expected
        QTest.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, shift, cursor)
        assert edge.routed is not None and len(edge.routed) == 2

        canvas.load(project)
        assert len(canvas.edges["net"].routed) == 2
    finally:
        canvas.close()


def test_port_label_stays_clear_of_module_headings(monkeypatch, six_lane_project):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication

    from desktop.canvas import Canvas
    from desktop.placement import LABEL_GAP

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    canvas = Canvas()
    design = six_lane_project
    processor = next(block for block in design["nodes"] if block["id"] == "processor")
    processor["portLayout"] = {"clk": {"side": "left", "offset": .23}}
    try:
        assert canvas.load(design) == 1
        node = canvas.blocks["processor"]
        port = node.ports["clk"]

        for pointer in (port.pos(), QPointF(0, 48), node.ports["rst_n"].pos()):
            canvas.move_port(port, node.mapToScene(pointer))
            assert port.port.side == "left"
            label = node.port_label_rect(port.port.side, port.pos())
            assert label.top() >= 56 + LABEL_GAP - 1e-7
            for other in node.ports.values():
                if other is not port:
                    assert not label.intersects(node.port_label_rect(other.port.side, other.pos()))

        canvas.move_port(port, node.mapToScene(QPointF(100, -5)))
        assert port.port.side == "top"
        label = node.port_label_rect(port.port.side, port.pos())
        assert label.bottom() < 0
        assert label.left() > port.x()
        assert canvas.load(design) == 0
    finally:
        canvas.close()


def test_port_labels_clear_generate_rows_and_other_sides(monkeypatch, six_lane_project):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtWidgets import QApplication

    from desktop.__main__ import component
    from desktop.canvas import Canvas
    from desktop.placement import LABEL_GAP

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    canvas = Canvas()
    design = six_lane_project["nodes"][0]
    source = component("input", "clock", {"x": 0, "y": 180})
    source["ports"][0]["shape"] = next(port["shape"] for port in design["analysis"]["ports"] if port["name"] == "clk")
    edge = {"id": "lane_clock", "source": source["id"], "sourcePort": "out",
            "target": design["id"], "targetPort": "clk@0"}
    project = {"nodes": [design, source], "edges": [edge]}
    try:
        assert canvas.load(project) == 0
        node = canvas.blocks[design["id"]]
        assert canvas.edges[edge["id"]].target is node.ports["clk@0"]
        assert canvas.edges[edge["id"]].routed
        output, clock, reset = (node.ports[name] for name in ("data_out", "clk", "rst_n"))
        width = node.body_rect.width()
        _, row_y = node.labels[1]
        canvas.move_port(output, node.mapToScene(QPointF(width, row_y + 10)))
        assert output.port.side == "right"
        row = QRectF(0, row_y, width, 23)
        assert not node.port_label_rect("right", output.pos()).intersects(row)

        for port, x in ((output, 40), (clock, 210)):
            canvas.move_port(port, node.mapToScene(QPointF(x, 0)))
            assert port.port.side == "top"
        assert clock.x() != pytest.approx(210)
        canvas.move_port(reset, node.mapToScene(node.body_rect.bottomLeft() + QPointF(20, 0)))
        assert reset.port.side == "bottom"

        labels = [node.port_label_rect(pin.port.side, pin.pos()) for pin in node.ports.values()]
        for index, label in enumerate(labels):
            margin = LABEL_GAP - 1e-7
            assert not any(label.adjusted(-margin, -margin, margin, margin).intersects(other)
                           for other in labels[index + 1:])
        assert canvas.load(project) == 0
    finally:
        canvas.close()


def test_distinct_wires_keep_separate_tracks_near_ports(monkeypatch):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    from desktop.__main__ import component
    from desktop.canvas import Canvas
    from desktop.libavoid import WIRE_GAP

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    canvas = Canvas()
    sources = [component("input", f"src_{i}", {"x": -360, "y": y}) for i, y in enumerate((-300, -120))]
    target = component("concat", "receiver", {"x": 650, "y": 150})
    edges = [{"id": port, "source": source["id"], "sourcePort": "out", "target": target["id"],
              "targetPort": port, "points": [{"x": 600, "y": source["position"]["y"] + 80}, {"x": 600, "y": y}]}
             for source, port, y in zip(sources, ("high", "low"), (230, 310))]
    try:
        canvas.load({"nodes": [*sources, target], "edges": edges})
        first, second = canvas.edges.values()
        assert first.routed and second.routed
        assert any(a[0] == b[0] == 600 for a, b in pairwise(first.routed))
        for edge in (first, second):
            assert edge.routed[0][1] == edge.routed[1][1]
            assert edge.routed[-2][1] == edge.routed[-1][1]
            assert edge.routed[-2][0] < edge.routed[-1][0]
        for (a, b), (c, d) in product(pairwise(first.routed), pairwise(second.routed)):
            for axis in (0, 1):
                if a[1 - axis] != b[1 - axis] or c[1 - axis] != d[1 - axis]:
                    continue
                low = max(min(a[axis], b[axis]), min(c[axis], d[axis]))
                high = min(max(a[axis], b[axis]), max(c[axis], d[axis]))
                if high > low:
                    assert abs(a[1 - axis] - c[1 - axis]) >= WIRE_GAP
    finally:
        canvas.close()


def test_wire_detours_when_a_block_is_moved_over_it(monkeypatch):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from desktop.__main__ import component
    from desktop.canvas import Canvas
    from desktop.routing import clear

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    canvas = Canvas()
    canvas.resize(980, 430)
    canvas.show()
    source = component("input", "src", {"x": -350, "y": 0})
    target = component("output", "dst", {"x": 400, "y": 0})
    covering = component("reshape", "covering", {"x": 0, "y": 180})
    net = {"id": "net", "source": source["id"], "sourcePort": "out",
           "target": target["id"], "targetPort": "in"}
    try:
        canvas.load({"nodes": [source, target, covering], "edges": [net]}, fit=True)
        edge = canvas.edges["net"]
        blocker = canvas.blocks[covering["id"]]
        assert not edge.bends
        blocker.setPos(0, 0)
        assert len(edge.bends) >= 2 and not edge.blocked
        points = [(p.x(), p.y()) for p in [edge.source.anchor(), *edge.bends, edge.target.anchor()]]
        assert all(clear(a, b, canvas.rectangles) for a, b in pairwise(points))
        assert not edge.shape().intersects(QRectF(20, 20, 230, 100))
        straight_midpoint = QPointF(130, edge.source.anchor().y())
        assert canvas.scene().itemAt(straight_midpoint, canvas.transform()) is blocker

        point = edge.path().pointAtPercent(.5)
        QTest.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton, pos=canvas.mapFromScene(point))
        app.processEvents()
        assert edge.isSelected()
        assert not blocker.isSelected()

        blocker.setPos(-150, 0)
        left = canvas.blocks[source["id"]]
        assert blocker.x() - left.body_bounds()[2] == 48
        assert not edge.blocked
        blocker.setPos(0, 180)
        assert not edge.blocked and not edge.bends
        assert "points" not in net
    finally:
        canvas.close()


def test_module_spacing_clamps_a_group_drag_and_repairs_saved_overlap(monkeypatch):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from desktop.__main__ import component
    from desktop.canvas import Canvas
    from desktop.placement import MODULE_GAP

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    canvas = Canvas()
    canvas.resize(1000, 660)
    canvas.show()
    first = component("input", "first", {"x": 0, "y": 0})
    second = component("input", "second", {"x": 0, "y": 240})
    fixed = component("output", "fixed", {"x": 410, "y": 0})
    project = {"nodes": [first, second, fixed], "edges": []}
    try:
        assert canvas.load(project, fit=True) == 0
        a, b, obstacle = [canvas.blocks[node["id"]] for node in project["nodes"]]
        a.setSelected(True)
        b.setSelected(True)
        offset = a.body_rect.center()
        press = canvas.mapFromScene(a.pos() + offset)
        release = canvas.mapFromScene(a.pos() + offset + QPointF(250, 0))
        QTest.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=press)
        QTest.mouseMove(canvas.viewport(), release, 10)
        QTest.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=release)
        app.processEvents()
        assert obstacle.x() - a.body_bounds()[2] == MODULE_GAP
        assert b.pos() - a.pos() == QPointF(0, 240)

        fixed["position"] = {"x": 350, "y": 0}
        assert canvas.load(project) == 1
        placed = canvas.blocks[fixed["id"]]
        previous = canvas.blocks[first["id"]]
        assert placed.x() - previous.body_bounds()[2] == MODULE_GAP
        assert fixed["position"] == {"x": 410.0, "y": 0.0}
        assert canvas.load(project) == 0
    finally:
        canvas.close()


def test_stacked_generate_uses_outer_layer_for_spacing_and_routing(monkeypatch, six_lane_project):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication

    from desktop.canvas import Canvas
    from desktop.placement import MODULE_GAP

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    canvas = Canvas()
    sample = six_lane_project
    packed, neighbor = [next(node for node in sample["nodes"] if node["id"] == name)
                        for name in ("processor", "reshape")]
    net = next(edge for edge in sample["edges"] if edge["id"] == "processor_data_out_reshape_in")
    packed["view"] = "expanded"
    project = {"nodes": [packed, neighbor], "edges": [net]}
    try:
        canvas.load(project)
        stack, other = (canvas.blocks[node["id"]] for node in project["nodes"])
        assert stack.outer_rect.right() > stack.body_rect.right()
        assert stack.outer_rect.bottom() > stack.body_rect.bottom()
        layer = stack.outer_rect.right() - 2
        assert stack.shape().contains(QPointF(layer, stack.body_rect.center().y()))
        assert stack.body_bounds() in canvas.rectangles

        canvas.move_group((other,), QPointF(-100, 0))
        assert other.body_bounds()[0] - stack.body_bounds()[2] == MODULE_GAP
        edge = canvas.edges[net["id"]]
        assert edge.routed[0][0] == stack.body_bounds()[2] + 8
        face = edge.source.face_anchor()
        assert edge.path().pointAtPercent(0) == face

        neighbor["position"] = {"x": stack.x(), "y": stack.body_bounds()[3] + MODULE_GAP - 8}
        assert canvas.load(project) == 1
        stack, other = (canvas.blocks[node["id"]] for node in project["nodes"])
        assert other.body_bounds()[1] - stack.body_bounds()[3] == MODULE_GAP

        assert "data_out@0" not in stack.ports
    finally:
        canvas.close()


def test_wire_draft_snaps_onto_input_and_removes_short_return(monkeypatch):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from desktop.__main__ import component
    from desktop.canvas import Canvas

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    canvas = Canvas()
    canvas.resize(1000, 550)
    canvas.show()
    start = component("input", "source", {"x": 0, "y": 0})
    end = component("output", "destination", {"x": 600, "y": 120})

    def click(point, modifiers=Qt.KeyboardModifier.NoModifier):
        QTest.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton, modifiers, canvas.mapFromScene(point))

    try:
        for modifiers, zoom in ((Qt.KeyboardModifier.NoModifier, 1), (Qt.KeyboardModifier.AltModifier, 2)):
            project = {"nodes": [start, end], "edges": []}
            canvas.load(project, fit=True)
            canvas.resetTransform()
            canvas.scale(zoom, zoom)
            canvas.centerOn(450, 150)
            source = canvas.blocks[start["id"]].ports["out"]
            target = canvas.blocks[end["id"]].ports["in"]
            turn_x = 440
            near = target.anchor().y() - 4 / zoom
            click(source.scenePos())
            click(QPointF(turn_x, source.anchor().y()))
            click(QPointF(turn_x, near), modifiers)
            assert canvas.draft[1][-1].y() == (near if modifiers else target.anchor().y())
            click(QPointF(turn_x - 40, near), modifiers)
            cursor = canvas.mapFromScene(target.scenePos())
            hover = QMouseEvent(QEvent.Type.MouseMove, QPointF(cursor), QPointF(canvas.viewport().mapToGlobal(cursor)),
                                Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
            app.sendEvent(canvas.viewport(), hover)
            preview = canvas.preview.path()
            click(target.scenePos())

            wire, = canvas.edges.values()
            assert wire.path() == preview
            assert wire.edge["points"] == [{"x": turn_x, "y": source.anchor().y()},
                                           {"x": turn_x, "y": target.anchor().y()}]
            assert all(x >= turn_x for x, y in wire.routed if y == target.anchor().y())
    finally:
        canvas.close()


def test_drag_snaps_connected_ports_to_a_straight_wire(monkeypatch):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from desktop.__main__ import component
    from desktop.canvas import Canvas

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    canvas = Canvas()
    canvas.resize(1000, 600)
    canvas.show()
    source = component("input", "source", {"x": 0, "y": 20})
    destination = component("output", "destination", {"x": 520, "y": 54})
    net = {"id": "net", "source": source["id"], "sourcePort": "out",
           "target": destination["id"], "targetPort": "in"}
    try:
        for modifiers in (Qt.KeyboardModifier.AltModifier, Qt.KeyboardModifier.NoModifier):
            source["position"] = {"x": 0, "y": 20}
            canvas.load({"nodes": [source, destination], "edges": [net]}, fit=True)
            canvas.resetTransform()
            item = canvas.blocks[source["id"]]
            edge = canvas.edges["net"]
            start = canvas.mapFromScene(item.mapToScene(item.body_rect.center()))
            end = start + canvas.mapFromScene(QPointF(20, 29)) - canvas.mapFromScene(QPointF())
            QTest.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, modifiers, start)
            move = QMouseEvent(QEvent.Type.MouseMove, QPointF(end), QPointF(canvas.viewport().mapToGlobal(end)),
                               Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, modifiers)
            app.sendEvent(canvas.viewport(), move)
            QTest.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, modifiers, end)
            if modifiers:
                assert edge.source.anchor().y() == edge.target.anchor().y() - 5
            else:
                assert edge.source.anchor().y() == edge.target.anchor().y()
                assert all(point[1] == edge.routed[0][1] for point in edge.routed)

        source["position"] = {"x": 0, "y": 300}
        destination["position"] = {"x": 240, "y": 0}
        source["portLayout"] = {"out": {"side": "top", "offset": .5}}
        destination["portLayout"] = {"in": {"side": "bottom", "offset": .5}}
        canvas.load({"nodes": [source, destination], "edges": [net]})
        edge = canvas.edges["net"]
        offset = edge.target.anchor().x() - edge.source.anchor().x()
        canvas.move_group((canvas.blocks[source["id"]],), QPointF(offset - 5, -20), snap=True)
        assert edge.source.anchor().x() == edge.target.anchor().x()
        assert all(point[0] == edge.routed[0][0] for point in edge.routed)
    finally:
        canvas.close()


def test_native_routes_survive_repeated_processor_moves(monkeypatch, six_lane_project):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    from desktop.canvas import Canvas
    from desktop.routing import clear, contains

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    canvas = Canvas()
    try:
        canvas.load(six_lane_project)
        processor = canvas.blocks["processor"]
        checked = 0
        for x, y in product(range(280, 701, 25), range(-230, 751, 35)):
            processor.setPos(x, y)
            links = [edge.routing_link() for edge in canvas.edges.values()]
            if any(contains(p, canvas.rectangles) for link in links for p in (link.source, link.target)):
                continue
            checked += 1
            for edge, link in zip(canvas.edges.values(), links):
                assert edge.routed, (x, y, edge.edge["id"])
                assert (edge.routed[0], edge.routed[-1]) == (link.source, link.target)
                assert all(clear(a, b, canvas.rectangles) for a, b in pairwise(edge.routed))
        assert checked >= 300
    finally:
        canvas.close()


def test_data_bus_uses_a_short_route_between_facing_ports(monkeypatch, six_lane_project):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    from desktop.canvas import Canvas

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    canvas = Canvas()
    try:
        canvas.load(six_lane_project)
        bus = canvas.blocks["bus"]
        edge = canvas.edges["reshape_out_bus_in"]
        for x, y in product((1040, 1046, 1050, 1060, 1080, 1120), (420, 460, 470, 475, 480, 485, 490, 510, 550)):
            bus.setPos(x, y)
            path = edge.routed
            assert path, (x, y)
            assert path[0][1] == path[1][1] and path[0][0] < path[1][0]
            assert path[-2][1] == path[-1][1] and path[-2][0] < path[-1][0]
            length = sum(abs(a - c) + abs(b - d) for (a, b), (c, d) in pairwise(path))
            start, end = path[0], path[-1]
            assert length == abs(start[0] - end[0]) + abs(start[1] - end[1]), (x, y, path)
    finally:
        canvas.close()


def test_data_in_keeps_a_short_route_beside_reset_track(monkeypatch, six_lane_project):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    from desktop.canvas import Canvas
    from desktop.libavoid import distance, tracks_too_close

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    canvas = Canvas()
    try:
        canvas.load(six_lane_project)
        data = canvas.blocks["din"]
        edge = canvas.edges["din_out_processor_data_in"]
        reset = canvas.edges["resets_out_processor_rst_n"]
        for x, y in product((60, 70, 75, 80, 110), range(310, 421, 5)):
            data.setPos(x, y)
            path = edge.routed
            assert path and reset.routed, (x, y)
            assert not tracks_too_close(path, reset.routed), (x, y, path, reset.routed)
            assert sum(distance(a, b) for a, b in pairwise(path)) == distance(path[0], path[-1]), (x, y, path)
            assert path[0][1] == path[1][1] and path[0][0] < path[1][0]
            assert path[-2][1] == path[-1][1] and path[-2][0] < path[-1][0]
    finally:
        canvas.close()


def test_desktop_rewire_export_and_reopen(monkeypatch, tmp_path):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFileDialog, QToolButton

    from desktop.__main__ import Window

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    window = Window()
    window.show()

    def wait_for_job():
        for _ in range(2000):
            app.processEvents()
            if window.job is None:
                return
            QTest.qWait(5)
        pytest.fail("Qt worker did not finish")

    def click(point):
        location = window.canvas.mapFromScene(point)
        assert window.canvas.viewport().rect().contains(location)
        QTest.mouseClick(window.canvas.viewport(), Qt.MouseButton.LeftButton, pos=location)
        app.processEvents()

    try:
        examples_button = window.examples_button
        assert examples_button.text() == "示例"
        assert examples_button.popupMode() == QToolButton.ToolButtonPopupMode.InstantPopup
        led_example, = examples_button.menu().actions()
        assert led_example.text() == "LED 闪灯示例"
        led_example.trigger()
        assert not examples_button.isEnabled()
        wait_for_job()
        assert examples_button.isEnabled()
        canvas = window.canvas
        assert set(canvas.blocks) == {"clk", "rst_n", "counter", "led", "led_out"}
        assert len(canvas.edges) == 6 and all(edge.routed for edge in canvas.edges.values())

        canvas.blocks["led_out"].setPos(1300, 240)
        canvas.fit_design()
        edge = canvas.edges["led_led_out_led_out_in"]
        edge.setSelected(True)
        window.redraw_action.trigger()
        click(QPointF(1140, edge.source.anchor().y()))
        click(QPointF(1140, edge.target.anchor().y()))
        click(edge.target.scenePos())
        assert canvas.draft is None
        points = edge.edge["points"]
        assert len(points) == 2
        assert points[-1]["y"] == edge.target.anchor().y()

        path = tmp_path / "qt-project.sv"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(path), ""))
        window.export_action.trigger()
        wait_for_job()
        assert path.is_file(), window.log.toPlainText()
        assert "// verilinx prj begin" in path.read_text(encoding="utf-8")
        assert not window.dirty

        window.restore_file(Path(path))
        wait_for_job()
        assert len(canvas.edges) == 6, window.log.toPlainText()
        restored = canvas.edges["led_led_out_led_out_in"].edge
        assert restored["points"] == points
        assert canvas.blocks["led_out"].pos() == QPointF(1300, 240)
        assert window.current_file == path
    finally:
        window.dirty = False
        window.close()
