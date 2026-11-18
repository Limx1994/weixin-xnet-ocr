#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detector post-processing: score_map -> text boxes.

The detector follows the DBNet design (probability map plus progressive
kernel maps). This implementation applies the standard DB-style recovery:
threshold the probability map, dilate with the smallest progressive kernel,
extract connected components, fit quadrilaterals, then restore coordinates to
the source image.
"""
import numpy as np


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def recover_quads(score_map, kernel_map=None, thresh=0.3, min_area=100,
                  box_thresh=0.5, unclip_ratio=2.0):
    """Return boxes in score-map coordinates.

    Each box is [x0, y0, x1, y1, x2, y2, x3, y3] (clockwise from top-left).
    """
    prob = _sigmoid(score_map) if score_map.min() < 0 else score_map.astype(np.float64)
    binary = (prob > thresh).astype(np.uint8)

    # Progressive kernel: DBNet++ shrinks the text region with each kernel so
    # adjacent lines separate. When the model reports no usable kernel (all
    # zeros) fall back to the raw threshold map, which still separates lines
    # that do not touch.
    if kernel_map is not None and kernel_map.ndim >= 3:
        k = kernel_map[0] if kernel_map.ndim == 3 else kernel_map
        if k.shape[0] > 0:
            k0 = (k[0] > 0.5).astype(np.uint8)
            if k0.sum() > 0:
                binary = _bitwise_and(binary, k0)

    labels, count = _label(binary)
    boxes = []
    for i in range(1, count + 1):
        ys, xs = np.nonzero(labels == i)
        area = len(xs)
        if area < min_area:
            continue
        # A component taller than it is wide usually merges several lines.
        # Split it on blank row bands so each text line becomes its own box.
        h = int(ys.max() - ys.min() + 1)
        w = int(xs.max() - xs.min() + 1)
        pieces = [(ys, xs)]
        if h > 1.3 * max(1, w) and h > 20:
            pieces = _split_on_blank_rows(labels, i, ys, xs)
        for pys, pxs in pieces:
            if len(pxs) < min_area:
                continue
            quad = _fit_quad(pxs, pys, prob, unclip_ratio)
            if quad is None:
                continue
            if _quad_score(prob, quad) < box_thresh:
                continue
            boxes.append(quad)
    return prob, boxes


def _split_on_blank_rows(labels, label_id, ys, xs, min_gap=3):
    """Split a component into row bands separated by empty rows."""
    y0, y1 = int(ys.min()), int(ys.max())
    rows = (labels[y0:y1 + 1] == label_id).sum(axis=1)
    bands = []
    start = None
    gap = 0
    for idx, v in enumerate(rows):
        if v > 0:
            if start is None:
                start = idx
            gap = 0
        elif start is not None:
            gap += 1
            if gap >= min_gap:
                bands.append((start, idx - gap))
                start = None
    if start is not None:
        bands.append((start, len(rows) - 1))
    if not bands:
        return [(ys, xs)]
    out = []
    for b0, b1 in bands:
        mask = (ys >= y0 + b0) & (ys <= y0 + b1)
        if mask.sum() > 0:
            out.append((ys[mask], xs[mask]))
    return out or [(ys, xs)]


def _bitwise_and(a, b):
    h = min(a.shape[0], b.shape[0])
    w = min(a.shape[1], b.shape[1])
    return a[:h, :w] & b[:h, :w]


def _label(binary):
    """4-connected component labelling (iterative, no external deps)."""
    h, w = binary.shape
    labels = np.zeros((h, w), dtype=np.int32)
    parent = [0]

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    next_label = 1
    for y in range(h):
        row = binary[y]
        for x in range(w):
            if row[x] == 0:
                continue
            up = labels[y - 1, x] if y > 0 else 0
            left = labels[y, x - 1] if x > 0 else 0
            if up == 0 and left == 0:
                parent.append(next_label)
                labels[y, x] = next_label
                next_label += 1
            elif up != 0 and left == 0:
                labels[y, x] = up
            elif up == 0 and left != 0:
                labels[y, x] = left
            else:
                labels[y, x] = min(up, left)
                union(up, left)

    # Flatten union-find roots.
    remap = {}
    out = np.zeros_like(labels)
    nxt = 1
    for y in range(h):
        for x in range(w):
            v = labels[y, x]
            if v == 0:
                continue
            root = find(v)
            if root not in remap:
                remap[root] = nxt
                nxt += 1
            out[y, x] = remap[root]
    return out, nxt - 1


def _fit_quad(xs, ys, prob, unclip_ratio):
    """Minimum-area rectangle around a component, then unclip."""
    if len(xs) < 5:
        return None
    pts = np.stack([xs.astype(np.float64), ys.astype(np.float64)], axis=1)
    try:
        rect = _min_area_rect(pts)
    except Exception:
        return None
    if rect is None:
        return None
    w = _dist(rect[0], rect[1])
    h = _dist(rect[1], rect[2])
    if w * h <= 0:
        return None
    delta = unclip_ratio * (w + h) / 2.0
    quad = []
    for p in rect:
        d = _unit(_centroid(rect) - p)
        quad.append(p + d * delta)
    return [float(v) for p in quad for v in p]


def _min_area_rect(pts):
    """Rotating-calipers minimum-area rectangle over the convex hull."""
    hull = _convex_hull(pts)
    if len(hull) < 3:
        return None
    best = None
    best_area = None
    n = len(hull)
    for i in range(n):
        a = hull[i]
        b = hull[(i + 1) % n]
        edge = b - a
        elen = np.hypot(edge[0], edge[1])
        if elen < 1e-9:
            continue
        u = edge / elen
        v = np.array([-u[1], u[0]])
        proj_u = hull @ u
        proj_v = hull @ v
        u0, u1 = proj_u.min(), proj_u.max()
        v0, v1 = proj_v.min(), proj_v.max()
        area = (u1 - u0) * (v1 - v0)
        if best_area is None or area < best_area:
            best_area = area
            corners = [
                u0 * u + v0 * v,
                u1 * u + v0 * v,
                u1 * u + v1 * v,
                u0 * u + v1 * v,
            ]
            best = np.array(corners)
    return best


def _convex_hull(pts):
    p = pts[np.lexsort((pts[:, 1], pts[:, 0]))]
    if len(p) <= 3:
        return p

    def half(points):
        stack = []
        for q in points:
            while len(stack) >= 2 and _cross(stack[-2], stack[-1], q) <= 0:
                stack.pop()
            stack.append(q)
        return stack

    lower = half(p)
    upper = half(p[::-1])
    return np.array(lower[:-1] + upper[:-1])


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _dist(a, b):
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def _unit(v):
    n = np.hypot(v[0], v[1])
    if n < 1e-9:
        return np.array([0.0, 0.0])
    return v / n


def _centroid(quad):
    return np.mean(np.asarray(quad), axis=0)


def _quad_score(prob, quad):
    """Mean probability inside the quadrilateral."""
    h, w = prob.shape
    poly = np.asarray(quad, dtype=np.float64).reshape(4, 2)
    x0 = max(0, int(np.floor(poly[:, 0].min())))
    x1 = min(w, int(np.ceil(poly[:, 0].max())) + 1)
    y0 = max(0, int(np.floor(poly[:, 1].min())))
    y1 = min(h, int(np.ceil(poly[:, 1].max())) + 1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    total = 0.0
    count = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            if _point_in_quad(np.array([x + 0.5, y + 0.5]), poly):
                total += float(prob[y, x])
                count += 1
    return total / count if count else 0.0


def _point_in_quad(p, quad):
    sign = 0
    for i in range(4):
        a = quad[i]
        b = quad[(i + 1) % 4]
        c = _cross(a, b, p)
        if abs(c) < 1e-9:
            continue
        s = 1 if c > 0 else -1
        if sign == 0:
            sign = s
        elif s != sign:
            return False
    return True


def scale_boxes(quads, src_hw, dst_hw):
    """Map boxes from score-map coordinates back to source-image pixels."""
    sh, sw = src_hw
    dh, dw = dst_hw
    sx = sw / float(dw)
    sy = sh / float(dh)
    out = []
    for q in quads:
        pts = np.asarray(q, dtype=np.float64).reshape(4, 2).copy()
        pts[:, 0] *= sx
        pts[:, 1] *= sy
        out.append([float(v) for v in pts.reshape(-1)])
    return out
