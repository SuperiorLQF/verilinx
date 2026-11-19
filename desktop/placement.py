"""Keep an orthogonal routing channel between rectangular node bodies."""

from math import sqrt

MODULE_GAP = 48
PORT_GAP = 28
LABEL_GAP = 3
EPSILON = 1e-8


def axis_size(rect, axis):
    return rect[axis], rect[axis + 2]


def crosses_channel(a, b, axis):
    return (a[axis] < b[axis + 2] + MODULE_GAP - EPSILON
            and b[axis] < a[axis + 2] + MODULE_GAP - EPSILON)


def bounds_at(rect, dx, dy):
    left, top, right, bottom = rect
    return left + dx, top + dy, right + dx, bottom + dy


def nearest_free(value, intervals, low=float("-inf"), high=float("inf")):
    """Find the nearest legal boundary of the union of open intervals."""
    merged = []
    for start, end in sorted(intervals):
        if merged and start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    for start, end in merged:
        if start < value < end:
            return min((point for point in (end, start) if low <= point <= high),
                       key=lambda point: abs(value - point), default=None)
    return value


def port_location(body, pointer, neighbors, *, label_slots=None, occupied=()):
    """Project onto the nearest open slot, even across a neighbor's keepout."""
    left, top, right, bottom = body
    choices = []
    for side, axis, fixed in (("left", 1, left), ("right", 1, right),
                              ("top", 0, top), ("bottom", 0, bottom)):
        first, last = axis_size(body, axis)
        length = last - first
        intervals = []
        cross_axis = 1 - axis
        edge_distance = (fixed - pointer[cross_axis]) ** 2
        along_edge = min(last, max(first, pointer[axis]))
        # Keep the pin on the edge the pointer is targeting while it has space.
        edge_cost = edge_distance + (along_edge - pointer[axis]) ** 2 if label_slots else 0
        for neighbor in neighbors:
            cross = abs(neighbor[cross_axis] - fixed)
            if cross < PORT_GAP:
                radius = sqrt(PORT_GAP ** 2 - cross ** 2)
                intervals.append((neighbor[axis] - radius, neighbor[axis] + radius))
        slots = label_slots[side] if label_slots else ((.025, .975, None),)
        for min_offset, max_offset, label in slots:
            low, high = first + min_offset * length, first + max_offset * length
            value = min(high, max(low, pointer[axis]))
            blocked = intervals
            if label is not None:
                blocked = intervals + [
                    (other[axis] - label[axis + 2] - LABEL_GAP, other[axis + 2] - label[axis] + LABEL_GAP)
                    for other in occupied
                    if label[cross_axis] < other[cross_axis + 2] + LABEL_GAP
                    and other[cross_axis] < label[cross_axis + 2] + LABEL_GAP
                ]
            position = nearest_free(value, blocked, low, high)
            if position is not None:
                cost = (edge_cost, (position - pointer[axis]) ** 2 + edge_distance)
                choices.append((cost, side, (position - first) / length))
    if not choices:
        return None
    _, side, offset = min(choices, key=lambda candidate: candidate[0])
    return side, offset


def separate(rect, neighbors):
    """Move a newly placed rectangle the shortest distance along either axis."""
    shifts = []
    for axis in (0, 1):
        start, end = axis_size(rect, axis)
        intervals = ((neighbor[axis] - (end - start) - MODULE_GAP, neighbor[axis + 2] + MODULE_GAP)
                     for neighbor in neighbors if crosses_channel(rect, neighbor, 1 - axis))
        shifts.append(nearest_free(start, intervals) - start)
    dx, dy = shifts
    return (dx, 0) if abs(dx) <= abs(dy) else (0, dy)


def limit_motion(moving, fixed, dx, dy):
    """Slide a group along obstacles without crossing them or opening the group."""
    amount = [dx, dy]
    applied = [0, 0]
    first = int(abs(dy) > abs(dx))
    for axis in (first, 1 - first):
        step = amount[axis]
        if not step:
            continue
        for original in moving:
            rect = bounds_at(original, *applied)
            start, end = axis_size(rect, axis)
            for neighbor in fixed:
                if not crosses_channel(rect, neighbor, 1 - axis):
                    continue
                other_start, other_end = axis_size(neighbor, axis)
                if step > 0 and end + MODULE_GAP <= other_start + EPSILON:
                    step = min(step, max(0, other_start - end - MODULE_GAP))
                elif step < 0 and start >= other_end + MODULE_GAP - EPSILON:
                    step = max(step, min(0, other_end + MODULE_GAP - start))
        applied[axis] = step
    return tuple(applied)
