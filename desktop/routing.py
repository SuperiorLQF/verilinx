"""Geometry checks for paths returned by the native router."""

from itertools import pairwise


def point_between(a, b, point):
    return (min(a[0], b[0]) <= point[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= point[1] <= max(a[1], b[1]))


def overlap_end(a, b, c, d):
    """Last point on c→d shared by an earlier segment a→b."""
    horizontal = a[1] == b[1]
    if horizontal != (c[1] == d[1]):
        point = (c[0], a[1]) if horizontal else (a[0], c[1])
        return point if point_between(a, b, point) and point_between(c, d, point) else None
    axis = 0 if horizontal else 1
    if a[1 - axis] != c[1 - axis]:
        return None
    low = max(min(a[axis], b[axis]), min(c[axis], d[axis]))
    high = min(max(a[axis], b[axis]), max(c[axis], d[axis]))
    if low > high:
        return None
    value = high if c[axis] < d[axis] else low
    return (value, c[1]) if horizontal else (c[0], value)


def simple_path(points):
    """Erase self-intersections and immediate reversals from the drawn path."""
    result = [points[0]]
    for end in points[1:]:
        start = result[-1]
        if start == end:
            continue
        cut = None
        for i, (a, b) in enumerate(pairwise(result)):
            point = overlap_end(a, b, start, end)
            if point is None or point == start and i == len(result) - 2:
                continue
            distance = abs(end[0] - point[0]) + abs(end[1] - point[1])
            if cut is None or distance < cut[0]:
                cut = distance, i, point
        if cut is not None:
            _, i, point = cut
            result = result[:i + 1]
            if point != result[-1]:
                result.append(point)
        if end != result[-1]:
            result.append(end)
    return result


def branch_points(paths):
    """Find places where routes of one signal share a node with three or more arms."""
    if len(paths) < 2:
        return set()
    terminals = {point for path in paths for point in (path[0], path[-1])}
    candidates = {point for path in paths for point in path[1:-1]} - terminals
    segments = [segment for path in paths for segment in pairwise(path)]
    junctions = set()
    for x, y in candidates:
        directions = set()
        for a, b in segments:
            if not point_between(a, b, (x, y)):
                continue
            for ex, ey in (a, b):
                if ex != x:
                    directions.add((ex > x, 0))
                elif ey != y:
                    directions.add((ey > y, 1))
        if len(directions) >= 3:
            junctions.add((x, y))
    return junctions


def contains(point, rectangles):
    x, y = point
    return any(left < x < right and top < y < bottom for left, top, right, bottom in rectangles)


def clear(start, end, rectangles):
    x, y = start
    ex, ey = end
    if y == ey:
        low, high = sorted((x, ex))
        return not any(top < y < bottom and left < high and low < right
                       for left, top, right, bottom in rectangles)
    if x != ex:
        return False
    low, high = sorted((y, ey))
    return not any(left < x < right and top < high and low < bottom
                   for left, top, right, bottom in rectangles)
