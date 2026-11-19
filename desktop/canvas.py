"""Graphics View scene for the shared Verilinx project model."""

from dataclasses import dataclass
from math import ceil, floor, isfinite
from uuid import uuid4

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPainterPathStroker, QPen, QPolygonF
from PySide6.QtWidgets import QApplication, QGraphicsItem, QGraphicsPathItem, QGraphicsScene, QGraphicsView

from backend.engine import endpoint_shape
from .libavoid import DiagramRouter, Link
from .placement import LABEL_GAP, MODULE_GAP, bounds_at, limit_motion, port_location, separate
from .routing import branch_points, clear, contains

WIDTH = 272
TERMINAL_WIDTH = 158
TERMINAL_HEIGHT = 48
TERMINAL_TIP = 16
MAX_BENDS = 256
STRAIGHT_SNAP_PIXELS = 9
HORIZONTAL = ("left", "right")
BORDER = {"left": (-1, 0), "right": (1, 0), "top": (0, -1), "bottom": (0, 1)}
SOURCE = QColor("#456f93")
TARGET = QColor("#128470")
PORT_READY = QColor("#de7625")
PORT_LABEL_HEIGHT = 28
TOP_LABEL_Y = -37
STACK_LAYER_OFFSET = 12


def terminal_rect(kind):
    # Keep the default socket at the location used by existing project files.
    return QRectF(WIDTH - TERMINAL_WIDTH if kind == "input" else 0,
                  80 - TERMINAL_HEIGHT / 2, TERMINAL_WIDTH, TERMINAL_HEIGHT)


def project_point(point):
    return {"x": point.x(), "y": point.y()}


def rect_bounds(rect):
    return rect.left(), rect.top(), rect.right(), rect.bottom()


def line_pen(color, width):
    return QPen(QBrush(color), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)


def finite(value, default):
    return value if isinstance(value, (int, float)) and abs(value) <= 10_000_000 and isfinite(value) else default


def points_path(points):
    path = QPainterPath(points[0])
    for point in points[1:]:
        path.lineTo(point)
    return path


def route(start, bends, end, source_side, target_side):
    """Rectify the supplied waypoints and trim any segments that double back."""
    source_x = source_side in HORIZONTAL
    target_x = target_side in HORIZONTAL
    if not bends and start.x() != end.x() and start.y() != end.y():
        if source_x and target_x:
            x = (start.x() + end.x()) / 2
            bends = [QPointF(x, start.y()), QPointF(x, end.y())]
        elif not source_x and not target_x:
            y = (start.y() + end.y()) / 2
            bends = [QPointF(start.x(), y), QPointF(end.x(), y)]
        else:
            bends = [QPointF(end.x(), start.y()) if source_x else QPointF(start.x(), end.y())]

    vertices = [start]
    for point in bends:
        previous = vertices[-1]
        if point.x() != previous.x() and point.y() != previous.y():
            corner = QPointF(point.x(), previous.y()) if source_x else QPointF(previous.x(), point.y())
            vertices.append(corner)
            previous = corner
        if point != previous:
            source_x = point.y() == previous.y()
            vertices.append(point)
    last = vertices[-1]
    if last.x() != end.x() and last.y() != end.y():
        vertices.append(QPointF(last.x(), end.y()) if target_x else QPointF(end.x(), last.y()))

    clean = [start]
    for point in [*vertices[1:], end]:
        while len(clean) > 1:
            first, tip = clean[-2:]
            reverse_x = first.y() == tip.y() == point.y() and (tip.x() - first.x()) * (point.x() - tip.x()) < 0
            reverse_y = first.x() == tip.x() == point.x() and (tip.y() - first.y()) * (point.y() - tip.y()) < 0
            if not (reverse_x or reverse_y):
                break
            clean.pop()
        if point != clean[-1]:
            clean.append(point)
    return clean[1:-1]


def snap_wire_end(start, bends, end, side, tolerance):
    """Align the last run with the input while leaving the source anchored."""
    horizontal = side in HORIZONTAL
    coordinate = QPointF.y if horizontal else QPointF.x
    row = coordinate(bends[-1])
    delta = coordinate(end) - row
    if not 0 < abs(delta) <= tolerance:
        return bends
    first = len(bends) - 1
    while first and coordinate(bends[first - 1]) == row:
        first -= 1
    if first == 0 and coordinate(start) == row:
        return bends
    shift = QPointF(0, delta) if horizontal else QPointF(delta, 0)
    return [*bends[:first], *(point + shift for point in bends[first:])]


def move_bend(vertices, index, destination):
    original = [(point.x(), point.y()) for point in vertices]
    moved = [list(point) for point in original]
    for axis, coordinate in enumerate((destination.x(), destination.y())):
        left = right = index
        while left > 0 and original[left - 1][axis] == original[left][axis]:
            left -= 1
        while right < len(vertices) - 1 and original[right + 1][axis] == original[right][axis]:
            right += 1
        if left == 0:
            coordinate = original[0][axis]
        elif right == len(vertices) - 1:
            coordinate = original[-1][axis]
        for i in range(left, right + 1):
            moved[i][axis] = coordinate
    return [QPointF(*point) for point in moved[1:-1]]


@dataclass
class Port:
    name: str
    role: str
    shape: dict
    side: str
    offset: float


class PortItem(QGraphicsItem):
    def __init__(self, port, node):
        super().__init__(node)
        self.port = port
        self.drag_ready = False
        self.setZValue(2)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setToolTip(f"{node.block['name']}.{port.name} · {self.shape_text()}")
        self.place()

    def place(self):
        self.setPos(self.position_at(self.port.side, self.port.offset))

    def position_at(self, side, offset):
        body = self.parentItem().body_rect
        if side in HORIZONTAL:
            return QPointF(body.left() if side == "left" else body.right(), body.top() + offset * body.height())
        return QPointF(body.left() + offset * body.width(), body.top() if side == "top" else body.bottom())

    def shape_text(self):
        shape = self.port.shape
        packed = "".join(f"[{a}:{b}]" for a, b in shape.get("packed", []))
        arrays = "".join(f"[{a}:{b}]" for a, b in shape.get("unpacked", []))
        return (f"{arrays} × " if arrays else "") + (packed or str(shape.get("atom_width", 1)))

    def anchor(self):
        return self.anchor_at(self.port.side, self.scenePos())

    def anchor_at(self, side, scene_position):
        dx, dy = BORDER[side]
        depth = self.parentItem().stack_depth if dx > 0 or dy > 0 else 0
        return scene_position + QPointF((8 + depth) * dx, (8 + depth) * dy)

    def face_anchor(self):
        x, y = BORDER[self.port.side]
        return self.scenePos() + QPointF(8 * x, 8 * y)

    def boundingRect(self):
        radius = 25 if self.parentItem().is_terminal else 16
        return QRectF(-radius, -radius, radius * 2, radius * 2)

    def shape(self):
        path = QPainterPath()
        path.addRect(QRectF(-16, -16, 32, 32))
        return path

    def paint(self, painter, option, widget=None):
        node = self.parentItem()
        color = PORT_READY if self.drag_ready else (SOURCE if self.port.role == "source" else TARGET)
        if node.is_terminal:
            dx, dy = BORDER[self.port.side]
            inset = node.terminal_inset(self.port.side, self.port.offset)
            end = QPointF(dx * 8, dy * 8)
            painter.setPen(line_pen(color, 2.5 if self.drag_ready else 1.7))
            painter.drawLine(QLineF(QPointF(-dx * inset, -dy * inset), end))
            return
        angle = {"right": 0, "bottom": 90, "left": 180, "top": 270}[self.port.side]
        painter.rotate(angle + (180 if self.port.role == "target" else 0))
        painter.setPen(QPen(QColor("white"), 1))
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in
                                       [(-9, -4), (0, -4), (0, -8), (10, 0), (0, 8), (0, 4), (-9, 4)]]))


class BlockItem(QGraphicsItem):
    def __init__(self, block, canvas, *, has_lane_wires=False):
        super().__init__()
        self.block = block
        self.canvas = canvas
        self.setFlags(self.GraphicsItemFlag.ItemIsMovable | self.GraphicsItemFlag.ItemIsSelectable
                      | self.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setZValue(1)
        position = block.get("position")
        position = position if isinstance(position, dict) else {}
        self.setPos(finite(position.get("x"), 0), finite(position.get("y"), 0))
        analysis = block.get("analysis") or {}
        self.count = analysis.get("count", 1)
        homogeneous = analysis.get("homogeneous", True)
        self.show_lanes = self.count > 1 and (has_lane_wires or not homogeneous)
        self.stack_depth = 2 * STACK_LAYER_OFFSET if self.count > 1 and not self.show_lanes else 0
        if block["kind"] == "module":
            base = analysis.get("ports", [])
            aggregate = [(p["name"], *endpoint_shape(block, p["name"])) for p in base
                         if homogeneous and p["direction"] in ("In", "Out")]
        else:
            base = []
            aggregate = [(p["name"], p["shape"], p["role"]) for p in block.get("ports", [])]

        groups = []
        if aggregate:
            groups.append(("聚合端口" if self.show_lanes else "", aggregate))
        if self.show_lanes:
            variants = analysis.get("variants", [])
            for index in range(self.count):
                ports = variants[index]["ports"] if index < len(variants) else base
                lane = [(f"{p['name']}@{index}", p["shape"], "source" if p["direction"] == "Out" else "target")
                        for p in ports if p["direction"] in ("In", "Out")]
                groups.append((f"lane {index}", lane))
        cursor = 58 + (28 if self.count > 1 else 0)
        entries = []
        self.labels = []
        for label, ports in groups:
            if label:
                self.labels.append((label, cursor))
                cursor += 25
            for role, side in (("target", "left"), ("source", "right")):
                role_ports = [(name, shape) for name, shape, direction in ports if direction == role]
                for index, (name, shape) in enumerate(role_ports):
                    entries.append((name, role, shape, side, cursor + 22 + index * 34))
            cursor += max(1, sum(p[2] == "source" for p in ports), sum(p[2] == "target" for p in ports)) * 34 + 15
        self.height = max(cursor + 30, 140)
        self.is_terminal = block["kind"] in ("input", "output") and len(entries) == 1
        self.body_rect = terminal_rect(block["kind"]) if self.is_terminal else QRectF(0, 0, WIDTH, self.height)
        self.outer_rect = self.body_rect.adjusted(0, 0, self.stack_depth, self.stack_depth)
        if self.is_terminal:
            body = self.body_rect
            left, right, top, bottom, mid = body.left(), body.right(), body.top(), body.bottom(), body.center().y()
            if block["kind"] == "input":
                vertices = [(left, top), (right - TERMINAL_TIP, top), (right, mid),
                            (right - TERMINAL_TIP, bottom), (left, bottom)]
            else:
                vertices = [(left, mid), (left + TERMINAL_TIP, top), (right, top),
                            (right, bottom), (left + TERMINAL_TIP, bottom)]
            self.terminal_outline = QPolygonF([QPointF(x, y) for x, y in vertices])
            self.setToolTip(block["name"])
        self.ports = {}
        for name, role, shape, side, y in entries:
            layout = block.get("portLayout")
            anchor = layout.get(name) if isinstance(layout, dict) else None
            if not isinstance(anchor, dict):
                anchor = {}
            custom_side = anchor.get("side")
            if isinstance(custom_side, str) and custom_side in BORDER:
                side = custom_side
            default_offset = .5 if self.is_terminal else y / self.height
            offset = min(.975, max(.025, finite(anchor.get("offset"), default_offset)))
            self.ports[name] = PortItem(Port(name, role, shape, side, offset), self)
        self.ports_repaired = self.separate_visible_ports()

    def boundingRect(self):
        top = -4 if self.is_terminal else TOP_LABEL_Y - 2
        return self.outer_rect.adjusted(-4, top, 4, 4)

    def shape(self):
        path = QPainterPath()
        if self.is_terminal:
            path.addPolygon(self.terminal_outline)
            path.closeSubpath()
        else:
            path.addRect(self.body_rect.adjusted(-4, -4, 4, 4))
            if self.stack_depth:
                path.setFillRule(Qt.FillRule.WindingFill)
                for offset in (STACK_LAYER_OFFSET, self.stack_depth):
                    path.addRoundedRect(self.body_rect.translated(offset, offset), 7, 7)
        return path

    def body_bounds(self):
        return rect_bounds(self.outer_rect.translated(self.pos()))

    def store_port(self, item, side, offset):
        item.port.side, item.port.offset = side, offset
        if not isinstance(self.block.get("portLayout"), dict):
            self.block["portLayout"] = {}
        self.block["portLayout"][item.port.name] = {"side": side, "offset": offset}
        item.place()

    def separate_visible_ports(self):
        saved = self.block.get("portLayout")
        if not isinstance(saved, dict) or not saved:
            return False
        # Keep the default pins in place when opening an older custom layout.
        placed = []
        changed = False
        for item in sorted(self.ports.values(), key=lambda item: item.port.name in saved):
            if item.port.name in saved:
                location = self.available_port_location(item.pos(), placed)
                if location is not None and (location[0] != item.port.side or abs(location[1] - item.port.offset) > 1e-7):
                    self.store_port(item, *location)
                    changed = True
            placed.append(item)
        return changed

    def port_label_rect(self, side, point, top_right=None):
        if side == "left":
            return QRectF(17, point.y() - PORT_LABEL_HEIGHT / 2, 111, PORT_LABEL_HEIGHT)
        if side == "right":
            return QRectF(WIDTH - 128, point.y() - PORT_LABEL_HEIGHT / 2, 111, PORT_LABEL_HEIGHT)
        if side == "top":
            right = point.x() <= WIDTH / 2 if top_right is None else top_right
            return QRectF(point.x() + (12 if right else -102), TOP_LABEL_Y, 90, PORT_LABEL_HEIGHT)
        return QRectF(point.x() - 45, self.height - 36, 90, PORT_LABEL_HEIGHT)

    def available_port_location(self, pointer, neighbors):
        bounds = rect_bounds(self.body_rect)
        locations = [(pin.x(), pin.y()) for pin in neighbors]
        point = (pointer.x(), pointer.y())
        if self.is_terminal:
            return port_location(bounds, point, locations)
        vertical_margin = max(.025, (PORT_LABEL_HEIGHT / 2 + LABEL_GAP) / self.height)
        horizontal_margin = (45 + LABEL_GAP) / WIDTH
        slots = {side: ((vertical_margin, 1 - vertical_margin, rect_bounds(self.port_label_rect(side, QPointF()))),)
                 for side in HORIZONTAL}
        slots["bottom"] = ((horizontal_margin, 1 - horizontal_margin,
                            rect_bounds(self.port_label_rect("bottom", QPointF()))),)
        slots["top"] = (
            (.025, .5, rect_bounds(self.port_label_rect("top", QPointF(), True))),
            (.500000001, .975, rect_bounds(self.port_label_rect("top", QPointF(), False))),
        )
        occupied = [(0, 0, WIDTH, 84 if self.show_lanes else 56)]
        occupied.extend((0, y, WIDTH, y + 23) for _, y in self.labels)
        occupied.extend(rect_bounds(self.port_label_rect(pin.port.side, pin.pos())) for pin in neighbors)
        return port_location(bounds, point, locations, label_slots=slots, occupied=occupied)

    def terminal_inset(self, side, offset):
        tip_side = "right" if self.block["kind"] == "input" else "left"
        if side in HORIZONTAL:
            return TERMINAL_TIP * abs(2 * offset - 1) if side == tip_side else 0
        distance = TERMINAL_WIDTH * (1 - offset if tip_side == "right" else offset)
        return TERMINAL_HEIGHT / 2 * max(0, 1 - distance / TERMINAL_TIP)

    def itemChange(self, change, value):
        if self.scene() is not None and not self.canvas.moving_group:
            if change == self.GraphicsItemChange.ItemPositionChange:
                dx, dy = self.canvas.block_delta((self,), value - self.pos())
                return self.pos() + QPointF(dx, dy)
            if change == self.GraphicsItemChange.ItemPositionHasChanged:
                self.canvas.blocks_moved((self,))
        return super().itemChange(change, value)

    def paint(self, painter, option, widget=None):
        if self.is_terminal:
            self.paint_terminal(painter)
            return
        if self.stack_depth:
            for offset, fill, outline in ((self.stack_depth, "#afc3c4", "#8aa7ab"),
                                          (STACK_LAYER_OFFSET, "#d4e1e1", "#a3babc")):
                painter.setPen(QPen(QColor(outline), 1))
                painter.setBrush(QColor(fill))
                layer = self.body_rect.translated(offset, offset).adjusted(.5, .5, -.5, -.5)
                painter.drawRoundedRect(layer, 7, 7)
        painter.setPen(QPen(QColor("#168470" if self.isSelected() else "#b9c9cd"), 2 if self.isSelected() else 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRoundedRect(self.body_rect, 7, 7)
        accent = QColor("#128470" if self.block["kind"] == "module" else "#64829d")
        painter.fillRect(QRectF(13, 14, 4, 29), accent)
        painter.setPen(QColor("#233338"))
        painter.setFont(QFont("Sans Serif", 11, QFont.Weight.DemiBold))
        count_text = f"×{self.count}"
        count_width = painter.fontMetrics().horizontalAdvance(count_text) if self.stack_depth else 0
        title_width = WIDTH - 42 - (count_width + 12 if count_width else 0)
        painter.drawText(QRectF(25, 12, title_width, 23), Qt.AlignmentFlag.AlignVCenter,
                         painter.fontMetrics().elidedText(self.block["name"], Qt.TextElideMode.ElideRight, title_width))
        if self.stack_depth:
            painter.setPen(QColor("#346c5b"))
            painter.drawText(QRectF(WIDTH - 17 - count_width, 12, count_width, 23),
                             Qt.AlignmentFlag.AlignVCenter, count_text)
        painter.setPen(QColor("#557073"))
        painter.setFont(QFont("Sans Serif", 9))
        painter.drawText(25, 47, self.block.get("module", self.block["kind"].upper()))
        painter.setPen(QPen(QColor("#e2e8e8")))
        painter.drawLine(QLineF(0, 56, WIDTH, 56))
        if self.show_lanes:
            painter.fillRect(QRectF(1, 57, WIDTH - 2, 27), QColor("#edf5f1"))
            painter.setPen(QColor("#346c5b"))
            painter.drawText(14, 74, f"generate × {self.count}")
        for label, y in self.labels:
            painter.setPen(QColor("#6d8285"))
            painter.drawText(QRectF(0, y, WIDTH, 23), Qt.AlignmentFlag.AlignCenter, label)
        for item in self.ports.values():
            port = item.port
            rect = self.port_label_rect(port.side, item.pos())
            align = {"left": Qt.AlignmentFlag.AlignLeft, "right": Qt.AlignmentFlag.AlignRight}.get(
                port.side, Qt.AlignmentFlag.AlignHCenter) | Qt.AlignmentFlag.AlignVCenter
            line_height = rect.height() / 2
            rect.setHeight(line_height)
            painter.setFont(QFont("Monospace", 9))
            painter.setPen(QColor("#2f454a"))
            painter.drawText(rect, align, painter.fontMetrics().elidedText(port.name, Qt.TextElideMode.ElideRight, int(rect.width())))
            painter.setPen(QColor("#72888b"))
            painter.setFont(QFont("Monospace", 8))
            painter.drawText(rect.translated(0, line_height), align,
                             painter.fontMetrics().elidedText(item.shape_text(), Qt.TextElideMode.ElideRight, int(rect.width())))

    def paint_terminal(self, painter):
        incoming = self.block["kind"] == "input"
        border = "#168470" if self.isSelected() else ("#7296b4" if incoming else "#62a393")
        painter.setPen(line_pen(QColor(border), 2 if self.isSelected() else 1.3))
        painter.setBrush(QColor("#edf4fa" if incoming else "#eaf5f0"))
        painter.drawPolygon(self.terminal_outline)
        body = self.body_rect.adjusted(10 + (0 if incoming else TERMINAL_TIP), 0,
                                      -10 - (TERMINAL_TIP if incoming else 0), 0)
        align = Qt.AlignmentFlag.AlignCenter
        painter.setPen(QColor("#233338"))
        painter.setFont(QFont("Sans Serif", 11, QFont.Weight.DemiBold))
        painter.drawText(QRectF(body.left(), body.top() + 5, body.width(), 22), align,
                         painter.fontMetrics().elidedText(self.block["name"], Qt.TextElideMode.ElideRight, int(body.width())))
        painter.setPen(QColor("#58747d"))
        painter.setFont(QFont("Monospace", 9))
        port = next(iter(self.ports.values()))
        painter.drawText(QRectF(body.left(), body.top() + 26, body.width(), 15), align,
                         painter.fontMetrics().elidedText(port.shape_text(), Qt.TextElideMode.ElideRight, int(body.width())))


class EdgeItem(QGraphicsPathItem):
    def __init__(self, edge, source, target, canvas):
        super().__init__()
        self.edge = edge
        self.source = source
        self.target = target
        self.canvas = canvas
        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable)
        self.setZValue(2)
        self.setPen(line_pen(SOURCE, 1.7))

    def routing_link(self):
        return self.canvas.routing_link(self.source, self.target,
                                        [QPointF(p["x"], p["y"]) for p in self.edge.get("points", [])])

    def refresh(self, path):
        start, end = self.source.anchor(), self.target.anchor()
        self.routed = path
        self.blocked = self.routed is None
        self.setToolTip("没有满足布线间距的路径。移开挡路的模块或调整连线后可恢复。" if self.blocked else "")
        if self.blocked:
            self.bends = []
            markers = QPainterPath()
            for point in (start, end):
                for sign in (-1, 1):
                    markers.moveTo(point + QPointF(-4, -4 * sign))
                    markers.lineTo(point + QPointF(4, 4 * sign))
            self.setPath(markers)
        else:
            points = [QPointF(x, y) for x, y in self.routed]
            self.bends = points[1:-1]
            self.setPath(points_path([self.source.face_anchor(), *points, self.target.face_anchor()]))

    def set_bends(self, bends):
        points = [project_point(point) for point in bends]
        if len(points) <= MAX_BENDS:
            self.edge["points"] = points
            self.canvas.reroute_edges()

    def insert_bend(self, position):
        if self.blocked or len(self.bends) >= MAX_BENDS:
            return False
        vertices = [self.source.anchor(), *self.bends, self.target.anchor()]
        candidates = []
        for index, (start, end) in enumerate(zip(vertices, vertices[1:])):
            direction = end - start
            length = QPointF.dotProduct(direction, direction)
            if length:
                t = min(1, max(0, QPointF.dotProduct(position - start, direction) / length))
                point = start + direction * t
                delta = position - point
                candidates.append((QPointF.dotProduct(delta, delta), index, point))
        if not candidates:
            return False
        _, index, point = min(candidates, key=lambda candidate: candidate[0])
        if point in vertices:
            return False
        self.set_bends([*self.bends[:index], point, *self.bends[index:]])
        return True

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(12)
        return stroker.createStroke(self.path())

    def boundingRect(self):
        return super().boundingRect().adjusted(-6, -6, 6, 6)

    def paint(self, painter, option, widget=None):
        if self.blocked:
            painter.setPen(line_pen(QColor("#b34c3d"), 2.0))
        else:
            painter.setPen(line_pen(TARGET, 2.5) if self.isSelected() else self.pen())
        painter.drawPath(self.path())
        if self.isSelected():
            painter.setBrush(QColor("white"))
            for point in self.bends:
                painter.drawRect(QRectF(point.x() - 3, point.y() - 3, 6, 6))


class Canvas(QGraphicsView):
    modified = Signal()
    message = Signal(str)
    edit_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("designCanvas")
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor("#f0f5f4"))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(self.DragMode.RubberBandDrag)
        self.setTransformationAnchor(self.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)
        self.project = None
        self.blocks = {}
        self.edges = {}
        self.junctions = set()
        self.rectangles = ()
        self.router = DiagramRouter()
        self.draft_router = None
        self.draft = None
        self.preview = None
        self.redrawing = None
        self.port_drag = None
        self.highlighted_port = None
        self.port_pointer = None
        self.bend_drag = None
        self.block_drag = None
        self.moving_group = False
        self.pan_start = None

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        scale = self.transform().m11()
        step = 20 if scale >= .4 else 80
        painter.setPen(QPen(QColor("#c9d8d6"), 0))
        for y in range(floor(rect.top() / step) * step, ceil(rect.bottom()), step):
            painter.drawPoints(QPolygonF([QPointF(x, y) for x in
                                         range(floor(rect.left() / step) * step, ceil(rect.right()), step)]))

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(SOURCE)
        for x, y in self.junctions:
            point = QPointF(x, y)
            if rect.adjusted(-4, -4, 4, 4).contains(point):
                painter.drawEllipse(point, 3.4, 3.4)
        painter.restore()

    def load(self, project, *, fit=False):
        self.cancel_wire()
        self.port_drag = None
        self.highlight_port(None)
        self.port_pointer = None
        self.bend_drag = None
        self.block_drag = None
        self.scene().clear()
        self.blocks.clear()
        self.edges.clear()
        self.junctions.clear()
        self.project = project
        if project is None:
            self.rectangles = ()
            return 0
        placed = []
        shifted = 0
        lane_nodes = {edge[end] for edge in project["edges"] for end in ("source", "target")
                      if "@" in edge[end + "Port"]}
        for block in project["nodes"]:
            item = BlockItem(block, self, has_lane_wires=block["id"] in lane_nodes)
            dx, dy = separate(item.body_bounds(), placed)
            if dx or dy:
                item.moveBy(dx, dy)
                block["position"] = project_point(item.pos())
            shifted += bool(dx or dy or item.ports_repaired)
            placed.append(item.body_bounds())
            self.blocks[block["id"]] = item
            self.scene().addItem(item)
        self.update_obstacles()
        for edge in project["edges"]:
            self.add_edge_item(edge)
        self.reroute_edges()
        if fit:
            self.fit_design()
            saved = project.get("viewport")
            if isinstance(saved, dict) and saved.get("saved") and self.blocks:
                zoom = min(2, max(.08, finite(saved.get("zoom"), 1)))
                viewport = self.viewport().rect().center()
                center = QPointF((viewport.x() - finite(saved.get("x"), 0)) / zoom,
                                 (viewport.y() - finite(saved.get("y"), 0)) / zoom)
                area = QRectF(center.x() - 2000, center.y() - 2000, 4000, 4000)
                self.setSceneRect(self.sceneRect().united(area))
                self.resetTransform()
                self.scale(zoom, zoom)
                self.centerOn(center)
        return shifted

    def fit_design(self):
        bounds = self.scene().itemsBoundingRect()
        if bounds.isEmpty():
            self.setSceneRect(-2000, -2000, 4000, 4000)
            self.resetTransform()
            self.centerOn(0, 0)
            return
        bounds = bounds.adjusted(-80, -80, 80, 80)
        self.setSceneRect(bounds.adjusted(-2000, -2000, 2000, 2000))
        self.fitInView(bounds, Qt.AspectRatioMode.KeepAspectRatio)
        zoom = self.transform().m11()
        if zoom > 1:
            self.scale(1 / zoom, 1 / zoom)

    def saved_viewport(self):
        transform = self.viewportTransform()
        origin = transform.map(QPointF())
        return {**project_point(origin), "zoom": transform.m11(), "saved": True}

    def update_obstacles(self):
        self.rectangles = tuple(block.body_bounds() for block in self.blocks.values())

    @staticmethod
    def routing_link(source, target, bends):
        start = source.anchor()
        end = target.anchor() if isinstance(target, PortItem) else target
        side = target.port.side if isinstance(target, PortItem) else None
        return Link((start.x(), start.y()), (end.x(), end.y()), source.port.side, side,
                    tuple((point.x(), point.y()) for point in bends))

    def reroute_edges(self):
        items = list(self.edges.values())
        nets = {}
        for edge, path in zip(items, self.router.routes(self.rectangles, [e.routing_link() for e in items])):
            edge.refresh(path)
            if path:
                key = (edge.edge["source"], edge.edge["sourcePort"])
                nets.setdefault(key, []).append(path)
        self.junctions = {point for paths in nets.values() for point in branch_points(paths)}
        self.viewport().update()

    def route_candidate(self, source, target, bends):
        if self.draft_router is None:
            self.draft_router = DiagramRouter()
        items = list(self.edges.values())
        index = items.index(self.redrawing) if self.redrawing is not None else len(items)
        links = [item.routing_link() for item in items if item is not self.redrawing]
        links.insert(index, self.routing_link(source, target, bends))
        return self.draft_router.routes(self.rectangles, links)[index]

    def add_edge_item(self, edge):
        source, target = (self.blocks.get(edge[k]) for k in ("source", "target"))
        if source is None or target is None:
            return
        source_port, target_port = source.ports.get(edge["sourcePort"]), target.ports.get(edge["targetPort"])
        if source_port is None or target_port is None:
            return
        item = EdgeItem(edge, source_port, target_port, self)
        self.scene().addItem(item)
        self.edges[edge["id"]] = item

    def block_delta(self, items, requested):
        moving = set(items)
        fixed = [item.body_bounds() for item in self.blocks.values() if item not in moving]
        return limit_motion([item.body_bounds() for item in items], fixed, requested.x(), requested.y())

    def straight_snap(self, items, requested, delta):
        moving = set(items)
        tolerance = STRAIGHT_SNAP_PIXELS / self.transform().m11()
        options = []
        for edge in self.edges.values():
            if edge.edge.get("points"):
                continue
            source, target = edge.source, edge.target
            source_moves = source.parentItem() in moving
            target_moves = target.parentItem() in moving
            if source_moves == target_moves or source.port.side == target.port.side:
                continue
            horizontal = source.port.side in HORIZONTAL
            if horizontal != (target.port.side in HORIZONTAL):
                continue
            moving_port, fixed_port = (source, target) if source_moves else (target, source)
            anchor, fixed = moving_port.anchor(), fixed_port.anchor()
            axis = 1 if horizontal else 0
            shift = fixed.y() - anchor.y() if horizontal else fixed.x() - anchor.x()
            difference = abs(shift - (requested.y() if horizontal else requested.x()))
            if difference <= tolerance:
                options.append((difference, axis, shift, moving_port, fixed_port))

        for _, axis, shift, moving_port, fixed_port in sorted(options, key=lambda option: option[:2]):
            candidate = list(delta)
            candidate[axis] = shift
            wanted = QPointF(*candidate)
            dx, dy = self.block_delta(items, wanted)
            if QPointF(dx, dy) != wanted:
                continue
            start = moving_port.anchor() + wanted
            end = fixed_port.anchor()
            if axis == 1:
                start.setY(end.y())
                separation = end.x() - start.x()
            else:
                start.setX(end.x())
                separation = end.y() - start.y()
            if separation * BORDER[moving_port.port.side][1 - axis] <= 0:
                continue
            bodies = [bounds_at(item.body_bounds(), dx, dy) if item in moving else item.body_bounds()
                      for item in self.blocks.values()]
            if clear((start.x(), start.y()), (end.x(), end.y()), bodies):
                return dx, dy
        return delta

    def move_group(self, items, requested, *, snap=False):
        delta = self.block_delta(items, requested)
        if QPointF(*delta) != requested:
            self.message.emit(f"模块之间预留 {MODULE_GAP} 个画布单位用于走线。")
        dx, dy = self.straight_snap(items, requested, delta) if snap else delta
        if not (dx or dy):
            return
        self.moving_group = True
        try:
            for item in items:
                item.moveBy(dx, dy)
        finally:
            self.moving_group = False
        self.blocks_moved(items)

    def blocks_moved(self, items):
        for item in items:
            item.block["position"] = project_point(item.pos())
        self.update_obstacles()
        self.reroute_edges()
        self.modified.emit()

    def delete_selected(self):
        if self.project is None or self.draft is not None:
            return
        selected = self.scene().selectedItems()
        nodes = {item.block["id"] for item in selected if isinstance(item, BlockItem)}
        edges = {item.edge["id"] for item in selected if isinstance(item, EdgeItem)}
        if not nodes and not edges:
            return
        self.project["nodes"] = [node for node in self.project["nodes"] if node["id"] not in nodes]
        self.project["edges"] = [edge for edge in self.project["edges"] if edge["id"] not in edges
                                 and edge["source"] not in nodes and edge["target"] not in nodes]
        self.load(self.project)
        self.modified.emit()

    def selected_block(self):
        selected = [item for item in self.scene().selectedItems() if isinstance(item, BlockItem)]
        return selected[0] if len(selected) == 1 else None

    def start_wire(self, source, edge=None):
        self.cancel_wire()
        self.redrawing = edge
        if edge:
            edge.setOpacity(.3)
        self.draft = (source, [])
        self.preview = QGraphicsPathItem()
        self.preview.setPen(QPen(TARGET, 1.7, Qt.PenStyle.DashLine))
        self.preview.setZValue(3)
        self.scene().addItem(self.preview)
        self.message.emit("单击画布放转折点，单击输入端口完成。Esc 取消，退格撤回。")

    def redraw_wire(self):
        if self.draft:
            return
        edges = [item for item in self.scene().selectedItems() if isinstance(item, EdgeItem)]
        if len(edges) == 1:
            self.start_wire(edges[0].source, edges[0])

    def cancel_wire(self):
        if self.redrawing is not None:
            self.redrawing.setOpacity(1)
        if self.preview is not None:
            self.scene().removeItem(self.preview)
        self.draft = self.preview = self.redrawing = None

    def place_leg(self, position, modifiers):
        source, bends = self.draft
        origin = bends[-1] if bends else source.anchor()
        horizontal = abs(position.x() - origin.x()) >= abs(position.y() - origin.y())
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            horizontal = not horizontal
        point = QPointF(position.x(), origin.y()) if horizontal else QPointF(origin.x(), position.y())
        if modifiers & Qt.KeyboardModifier.AltModifier:
            return point

        coordinate = QPointF.x if horizontal else QPointF.y
        value = coordinate(point)
        tolerance = STRAIGHT_SNAP_PIXELS / self.transform().m11()
        candidates = [coordinate(anchor) for anchor in (source.anchor(), *bends)]
        ports = ((self.redrawing.target,) if self.redrawing else
                 (port for node in self.blocks.values() for port in node.ports.values()))
        for port in ports:
            if port.port.role != "target" or (port.port.side in HORIZONTAL) == horizontal:
                continue
            anchor = port.anchor()
            along = coordinate(anchor)
            if abs(along - value) > tolerance:
                continue
            snapped = QPointF(along, point.y()) if horizontal else QPointF(point.x(), along)
            dx, dy = BORDER[port.port.side]
            outside = QPointF.dotProduct(snapped - anchor, QPointF(dx, dy))
            if outside > 0 and clear((snapped.x(), snapped.y()), (anchor.x(), anchor.y()), self.rectangles):
                candidates.append(along)
        closest = min(candidates, key=lambda candidate: abs(candidate - value))
        if abs(closest - value) <= tolerance:
            return QPointF(closest, point.y()) if horizontal else QPointF(point.x(), closest)
        return point

    def wire_bends(self, target, modifiers):
        source, bends = self.draft
        if not bends:
            return []
        start, end = source.anchor(), target.anchor()
        side = target.port.side
        if not modifiers & Qt.KeyboardModifier.AltModifier:
            bends = snap_wire_end(start, bends, end, side, STRAIGHT_SNAP_PIXELS / self.transform().m11())
        return route(start, bends, end, source.port.side, side)

    def update_preview(self, point=None, target=None, modifiers=Qt.KeyboardModifier.NoModifier):
        source, bends = self.draft
        destination = target if target is not None else point
        if target is not None:
            bends = self.wire_bends(target, modifiers)
        if destination is None and bends:
            destination, bends = bends[-1], bends[:-1]
        path = self.route_candidate(source, destination, bends) if destination is not None else None
        vertices = [source.face_anchor(), *(QPointF(x, y) for x, y in path or ())]
        if path and target is not None:
            vertices.append(target.face_anchor())
        self.preview.setPath(points_path(vertices))

    def finish_wire(self, target, modifiers=Qt.KeyboardModifier.NoModifier):
        source, _ = self.draft
        source_node = source.parentItem().block["id"]
        target_node = target.parentItem().block["id"]
        name = target.port.name
        existing = self.redrawing
        if existing and target is not existing.target:
            self.message.emit("重画时请点击原输入端口。")
            return
        base, _, lane = name.partition("@")
        for edge in self.project["edges"]:
            if edge["target"] != target_node or (existing and edge is existing.edge):
                continue
            other_base, _, other_lane = edge["targetPort"].partition("@")
            if base == other_base and (not lane or not other_lane or lane == other_lane):
                self.message.emit("该输入已有驱动，聚合端口和单路端口不能重叠连接。")
                return
        dimensions = lambda shape: (shape.get("packed", []), shape.get("unpacked", []), shape.get("atom_width", 1))
        if dimensions(source.port.shape) != dimensions(target.port.shape):
            self.message.emit("端口位宽或数组形状不一致。")
            return
        points = self.wire_bends(target, modifiers)
        if len(points) > MAX_BENDS:
            self.message.emit("转折点超过上限，请撤回部分点。")
            return
        if self.route_candidate(source, target, points) is None:
            self.message.emit("找不到满足线路间距的路径，请留出布线空间。")
            return
        geometry = [project_point(point) for point in points]
        if existing:
            existing.edge["points"] = geometry
        else:
            edge = {"id": str(uuid4()), "source": source_node, "sourcePort": source.port.name,
                    "target": target_node, "targetPort": name, "points": geometry}
            self.project["edges"].append(edge)
            self.add_edge_item(edge)
        self.reroute_edges()
        self.cancel_wire()
        self.modified.emit()
        self.message.emit("连线已保存。")

    def snap_port_location(self, item, pointer, neighbors, location):
        node = item.parentItem()
        side, offset = location
        horizontal = side in HORIZONTAL
        coordinate = QPointF.y if horizontal else QPointF.x
        tolerance = STRAIGHT_SNAP_PIXELS / self.transform().m11()
        dx, dy = BORDER[side]
        face = item.position_at(side, offset)
        options = []
        for edge in self.edges.values():
            if edge.edge.get("points") or item not in (edge.source, edge.target):
                continue
            peer = edge.target if edge.source is item else edge.source
            if BORDER[peer.port.side] != (-dx, -dy):
                continue
            anchor = peer.anchor()
            along = coordinate(node.mapFromScene(anchor))
            distance = abs(along - coordinate(pointer))
            if distance > tolerance:
                continue
            aligned = QPointF(face.x(), along) if horizontal else QPointF(along, face.y())
            candidate = node.available_port_location(aligned, neighbors)
            if candidate is None or candidate[0] != side:
                continue
            if abs(coordinate(item.position_at(*candidate)) - along) > 1e-7:
                continue
            start = item.anchor_at(side, node.mapToScene(aligned))
            if horizontal:
                start.setY(anchor.y())
            else:
                start.setX(anchor.x())
            if (QPointF.dotProduct(anchor - start, QPointF(dx, dy)) > 0
                    and clear((start.x(), start.y()), (anchor.x(), anchor.y()), self.rectangles)):
                options.append((distance, candidate))
        return min(options, key=lambda option: option[0])[1] if options else location

    def move_port(self, item, scene_point, *, snap=False):
        node = item.parentItem()
        point = node.mapFromScene(scene_point)
        neighbors = [p for p in node.ports.values() if p is not item]
        location = node.available_port_location(point, neighbors)
        if snap and location is not None:
            location = self.snap_port_location(item, point, neighbors, location)
        if location is None or location == (item.port.side, item.port.offset):
            return
        node.store_port(item, *location)
        node.update()
        self.reroute_edges()
        self.modified.emit()

    def port_at(self, position):
        if position is None:
            return None
        return min((item for item in self.items(position) if isinstance(item, PortItem)),
                   key=lambda item: (self.mapFromScene(item.scenePos()) - position).manhattanLength(), default=None)

    def highlight_port(self, port):
        if self.highlighted_port is port:
            return
        if self.highlighted_port is not None:
            self.highlighted_port.drag_ready = False
            self.highlighted_port.update()
        self.highlighted_port = port
        if port is not None:
            port.drag_ready = True
            port.update()

    def update_port_highlight(self, shift):
        available = shift and self.isEnabled() and not (self.draft or self.pan_start is not None
                                                        or self.bend_drag or self.block_drag)
        self.highlight_port(self.port_drag or (self.port_at(self.port_pointer) if available else None))

    def mousePressEvent(self, event):
        position = event.position().toPoint()
        self.port_pointer = position
        if event.button() == Qt.MouseButton.MiddleButton:
            self.pan_start = position
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            items = self.items(position)
            port = self.port_at(position)
            if self.draft:
                if port and port.port.role == "target":
                    self.finish_wire(port, event.modifiers())
                elif not any(isinstance(item, (BlockItem, PortItem)) for item in items):
                    source, bends = self.draft
                    point = self.place_leg(self.mapToScene(position), event.modifiers())
                    if len(bends) < MAX_BENDS and point != (bends[-1] if bends else source.anchor()):
                        if not contains((point.x(), point.y()), self.rectangles):
                            bends.append(point)
                            self.update_preview()
                event.accept()
                return
            if port:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.port_drag = port
                    self.highlight_port(port)
                elif port.port.role == "source":
                    self.start_wire(port)
                else:
                    self.message.emit("请先点击输出端口。")
                event.accept()
                return
            for edge in self.scene().selectedItems():
                if isinstance(edge, EdgeItem):
                    for index, point in enumerate(edge.bends, start=1):
                        if (self.mapFromScene(point) - position).manhattanLength() <= 9:
                            vertices = [edge.source.anchor(), *edge.bends, edge.target.anchor()]
                            self.bend_drag = (edge, vertices, index)
                            event.accept()
                            return
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.scene().mouseGrabberItem()
            if isinstance(item, BlockItem):
                offset = item.pos() - self.mapToScene(position)
                self.block_drag = (item, offset, position)

    def mouseMoveEvent(self, event):
        position = event.position().toPoint()
        self.port_pointer = position
        self.update_port_highlight(bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
        if self.pan_start is not None:
            delta = position - self.pan_start
            self.pan_start = position
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
        elif self.port_drag:
            self.move_port(self.port_drag, self.mapToScene(position),
                           snap=not bool(event.modifiers() & Qt.KeyboardModifier.AltModifier))
        elif self.bend_drag:
            edge, vertices, index = self.bend_drag
            edge.set_bends(move_bend(vertices, index, self.mapToScene(position)))
        elif self.draft:
            port = self.port_at(position)
            target = port if port and port.port.role == "target" else None
            point = None if target else self.place_leg(self.mapToScene(position), event.modifiers())
            self.update_preview(point, target, event.modifiers())
        elif self.block_drag is not None:
            item, offset, origin = self.block_drag
            if origin is None or (position - origin).manhattanLength() >= QApplication.startDragDistance():
                self.block_drag = (item, offset, None)
                others = [node for node in self.scene().selectedItems() if isinstance(node, BlockItem)]
                group = others if item in others else [item]
                self.move_group(group, self.mapToScene(position) + offset - item.pos(),
                                snap=not bool(event.modifiers() & Qt.KeyboardModifier.AltModifier))
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.block_drag = None
        if event.button() == Qt.MouseButton.MiddleButton and self.pan_start is not None:
            self.pan_start = None
            self.unsetCursor()
        elif event.button() == Qt.MouseButton.LeftButton and self.port_drag:
            self.port_drag = None
        elif event.button() == Qt.MouseButton.LeftButton and self.bend_drag:
            edge, vertices, _ = self.bend_drag
            self.bend_drag = None
            if edge.bends != vertices[1:-1]:
                self.modified.emit()
        else:
            super().mouseReleaseEvent(event)
        self.update_port_highlight(bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))

    def leaveEvent(self, event):
        self.port_pointer = None
        self.highlight_port(self.port_drag)
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.draft:
            item = self.itemAt(event.position().toPoint())
            if isinstance(item, BlockItem):
                self.edit_requested.emit(item.block["id"])
                event.accept()
                return
            if isinstance(item, EdgeItem) and item.insert_bend(self.mapToScene(event.position().toPoint())):
                item.setSelected(True)
                self.modified.emit()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        factor = 1.17 ** (event.angleDelta().y() / 120)
        zoom = self.transform().m11()
        factor = min(2 / zoom, max(.08 / zoom, factor))
        self.scale(factor, factor)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Shift:
            self.update_port_highlight(True)
            super().keyPressEvent(event)
            return
        if self.draft and event.key() == Qt.Key.Key_Escape:
            self.cancel_wire()
            self.message.emit("已取消布线。")
        elif self.draft and event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            _, bends = self.draft
            if bends:
                bends.pop()
            self.update_preview()
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Shift:
            self.update_port_highlight(False)
        super().keyReleaseEvent(event)
