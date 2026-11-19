"""Batch and incremental orthogonal routing through Adaptagrams libavoid."""

import ctypes as C
from dataclasses import dataclass, replace
from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from weakref import finalize

from .routing import clear, contains, simple_path

LIBRARY = Path(__file__).resolve().parents[1] / ".runtime/libavoid/build/libverilinx_avoid.so"
DIRECTION = {"top": 1, "bottom": 2, "left": 4, "right": 8, None: 15}
OUTWARD = {"top": (0, -1), "bottom": (0, 1), "left": (-1, 0), "right": (1, 0)}
WIRE_GAP = 12


def distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def compact(path):
    result = [path[0]]
    for point in path[1:]:
        if len(result) >= 2:
            a, b = result[-2:]
            if a[0] == b[0] == point[0] or a[1] == b[1] == point[1]:
                result.pop()
        result.append(point)
    return result


def has_port_lead(anchor, adjacent, side):
    if side is None:
        return True
    dx, dy = OUTWARD[side]
    x, y = adjacent[0] - anchor[0], adjacent[1] - anchor[1]
    return x * dy == y * dx and x * dx + y * dy > 0


def route_cost(path):
    return sum(distance(a, b) for a, b in pairwise(path)) + 12 * len(compact(path))


def conflicting_segments(first, second):
    for a, b in pairwise(first):
        axis = 0 if a[1] == b[1] else 1
        for c, d in pairwise(second):
            if c[1 - axis] != d[1 - axis] or abs(a[1 - axis] - c[1 - axis]) >= WIRE_GAP - 1e-7:
                continue
            end = min(max(a[axis], b[axis]), max(c[axis], d[axis]))
            start = max(min(a[axis], b[axis]), min(c[axis], d[axis]))
            if end - start > 1e-7:
                yield a, b
                break


def tracks_too_close(first, second):
    return next(conflicting_segments(first, second), None) is not None


class Connection(C.Structure):
    _fields_ = [("sx", C.c_double), ("sy", C.c_double), ("tx", C.c_double), ("ty", C.c_double),
                ("source_direction", C.c_uint), ("target_direction", C.c_uint),
                ("checkpoint_offset", C.c_size_t), ("checkpoint_count", C.c_size_t)]


@dataclass(frozen=True)
class Link:
    source: tuple
    target: tuple
    source_side: str | None
    target_side: str | None
    checkpoints: tuple = ()


@lru_cache(maxsize=1)
def library():
    try:
        native = C.CDLL(str(LIBRARY))
    except OSError as exc:
        raise RuntimeError("无法加载 libavoid。请在仓库根目录运行 ./scripts/build_libavoid.sh。") from exc
    doubles = C.POINTER(C.c_double)
    native.vlx_avoid_new.argtypes = [C.c_double]
    native.vlx_avoid_new.restype = C.c_void_p
    native.vlx_avoid_free.argtypes = [C.c_void_p]
    native.vlx_avoid_free.restype = None
    native.vlx_avoid_route.argtypes = [C.c_void_p, C.c_size_t, doubles, C.c_size_t,
                                      C.POINTER(Connection), doubles]
    native.vlx_avoid_route.restype = C.c_int
    native.vlx_avoid_path.argtypes = [C.c_void_p, C.c_size_t, doubles, C.c_size_t]
    native.vlx_avoid_path.restype = C.c_size_t
    return native


class NativeRouter:
    def __init__(self, clearance):
        self.native = library()
        self.handle = self.native.vlx_avoid_new(clearance)
        if not self.handle:
            raise RuntimeError("无法初始化 libavoid。")
        self._release = finalize(self, self.native.vlx_avoid_free, self.handle)

    def routes(self, boxes, links):
        shapes = (C.c_double * (4 * len(boxes)))(*(value for box in boxes for value in box))
        connections = (Connection * len(links))()
        checkpoints = []
        for index, link in enumerate(links):
            connections[index] = Connection(*link.source, *link.target,
                                            DIRECTION[link.source_side], DIRECTION[link.target_side],
                                            len(checkpoints) // 2, len(link.checkpoints))
            checkpoints.extend(value for point in link.checkpoints for value in point)
        waypoints = (C.c_double * len(checkpoints))(*checkpoints)
        if not self.native.vlx_avoid_route(self.handle, len(boxes), shapes, len(links), connections, waypoints):
            raise RuntimeError("libavoid 未能完成布线事务。")
        result = []
        read = self.native.vlx_avoid_path
        for index in range(len(links)):
            count = read(self.handle, index, None, 0)
            path = (C.c_double * (count * 2))()
            read(self.handle, index, path, count)
            result.append(list(zip(path[::2], path[1::2])))
        return result


class DiagramRouter:
    def __init__(self):
        self.primary = NativeRouter(6)
        self.tight = None
        self.with_leads = {}
        self.with_reserved_tracks = None

    @staticmethod
    def valid(path, link, boxes):
        return (len(path) >= 2 and path[0] == link.source and path[-1] == link.target
                and all(clear(a, b, boxes) for a, b in pairwise(path)))

    def routes(self, boxes, links):
        active = [(index, replace(link, checkpoints=tuple(
            p for p in link.checkpoints if p not in (link.source, link.target) and not contains(p, boxes)
        ))) for index, link in enumerate(links)
                  if link.source != link.target and not any(contains(p, boxes) for p in (link.source, link.target))]
        results = [None] * len(links)
        if not active:
            return results

        def calculate(router, options):
            paths = router.routes(boxes, options)
            missing = []
            for (index, _), link, path in zip(active, options, paths):
                if self.valid(path, link, boxes):
                    results[index] = simple_path(path)
                else:
                    missing.append(index)
            return set(missing)

        options = [link for _, link in active]
        missing = calculate(self.primary, options)
        conflicts = set()
        for i, (index, link) in enumerate(active):
            if index in missing:
                continue
            for j, (other_index, other) in enumerate(active[:i]):
                if ((options[i].checkpoints or options[j].checkpoints)
                        and other_index not in missing and link.source != other.source
                        and tracks_too_close(results[index], results[other_index])):
                    if options[i].checkpoints:
                        conflicts.add(index)
                    elif options[j].checkpoints:
                        conflicts.add(other_index)
        if conflicts:
            options = [replace(link, checkpoints=()) if index in conflicts else link
                       for (index, _), link in zip(active, options)]
            missing = calculate(self.primary, options)
        if any(index in missing and link.checkpoints for (index, _), link in zip(active, options)):
            options = [replace(link, checkpoints=()) if index in missing else link for index, link in active]
            missing = calculate(self.primary, options)
        if missing:
            if self.tight is None:
                self.tight = NativeRouter(0)
            options = [replace(link, checkpoints=()) if index in missing else link
                       for (index, _), link in zip(active, options)]
            missing = calculate(self.tight, options)
            if missing:
                # In a narrow space the pin anchor can still be reachable
                # from the side even when its preferred launch is obstructed.
                options = [replace(link, source_side=None, target_side=None) if index in missing else link
                           for (index, _), link in zip(active, options)]
                calculate(self.tight, options)
        self.shorten_terminal_detours(boxes, active, options, results)
        self.separate_parallel_routes(boxes, active, options, results)
        return results

    def separate_parallel_routes(self, boxes, active, options, results):
        for (index, link), option in zip(active, options):
            current = results[index]
            if not current:
                continue
            neighbors = [(other, results[other]) for other, peer in active
                         if other != index and peer.source != link.source and results[other]]
            reservations = set()
            for other, path in neighbors:
                if other >= index:
                    continue
                for (x, y), (ex, ey) in conflicting_segments(path, current):
                    if y == ey:
                        reservations.add((min(x, ex), y - WIRE_GAP, max(x, ex), y + WIRE_GAP))
                    else:
                        reservations.add((x - WIRE_GAP, min(y, ey), x + WIRE_GAP, max(y, ey)))
            if not reservations:
                continue
            obstacles = (*boxes, *sorted(reservations))
            if any(contains(point, obstacles) for point in (link.source, link.target, *option.checkpoints)):
                continue
            if self.with_reserved_tracks is None:
                self.with_reserved_tracks = NativeRouter(6)
            path, = self.with_reserved_tracks.routes(obstacles, [option])
            if self.valid(path, link, obstacles):
                path = simple_path(path)
                if not any(tracks_too_close(path, neighbor) for _, neighbor in neighbors):
                    results[index] = path

    def shorten_terminal_detours(self, boxes, active, options, results):
        def has_detour(path, link):
            return path is None or sum(distance(a, b) for a, b in pairwise(path)) > distance(link.source, link.target) + 1e-7

        candidates = set()
        for (index, link), option in zip(active, options):
            # A native route may make an otherwise unnecessary return trip
            # just to meet a free-point endpoint with a strict direction.
            if not option.checkpoints and has_detour(results[index], link):
                candidates.add(index)
        if not candidates:
            return

        def lead(anchor, side, limit):
            if side is None:
                return anchor
            dx, dy = OUTWARD[side]
            for length in (limit, limit / 2, limit / 4):
                point = (anchor[0] + dx * length, anchor[1] + dy * length)
                if clear(anchor, point, boxes) and not contains(point, boxes):
                    return point
            return anchor

        def with_leads(link, option, source_limit, target_limit):
            if link.source_side is not None and link.target_side is not None:
                x, y = OUTWARD[link.source_side]
                if OUTWARD[link.target_side] == (-x, -y):
                    span = (link.target[0] - link.source[0]) * x + (link.target[1] - link.source[1]) * y
                    if span > 0:
                        source_limit = min(source_limit, span / 2)
                        target_limit = min(target_limit, span / 2)
            return replace(option, source=lead(link.source, link.source_side, source_limit),
                           target=lead(link.target, link.target_side, target_limit),
                           source_side=None, target_side=None)

        # Different lengths let libavoid enter on either side of an existing
        # track in a tight channel. Keep earlier routes until a shorter
        # candidate is also safe alongside the current neighboring routes.
        for lengths in ((8, 8), (4, 4), (2, 2), (8, 2), (2, 8)):
            if not candidates:
                break
            if lengths not in self.with_leads:
                self.with_leads[lengths] = NativeRouter(6)
            alternate = [with_leads(link, option, *lengths) for (_, link), option in zip(active, options)]
            paths = self.with_leads[lengths].routes(boxes, alternate)
            for (index, link), path in zip(active, paths):
                if index not in candidates or not path:
                    continue
                path = [link.source, *path, link.target]
                if not self.valid(path, link, boxes):
                    continue
                path = compact(simple_path(path))
                if (len(path) < 2 or not has_port_lead(path[0], path[1], link.source_side)
                        or not has_port_lead(path[-1], path[-2], link.target_side)):
                    continue
                current = results[index]
                if current is not None:
                    if route_cost(path) >= route_cost(current):
                        continue
                    if any(other != index and neighbor.source != link.source and results[other]
                           and tracks_too_close(path, results[other]) and not tracks_too_close(current, results[other])
                           for other, neighbor in active):
                        continue
                results[index] = path
                if not has_detour(path, link):
                    candidates.remove(index)
