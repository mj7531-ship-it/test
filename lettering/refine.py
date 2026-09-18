"""
글자 윤곽선 후처리.

폰트가 그려준 윤곽선을 받아서 세 가지를 한다.

- contrast : 세로 기둥을 불리고 가로획을 깎아 획 대비를 키운다
- sharpen  : 쐐기 세리프와 삐침의 뾰족한 끝을 더 내민다
- oval     : ㅇ 계열의 둥근 속공간을 가로로 좁혀 세로 타원으로 만든다

셋 다 윤곽선의 점을 옮기는 방식이라 원본 폰트 파일은 건드리지 않는다.
좌표는 최종 px 공간(자평까지 먹인, y가 아래로 가는 SVG 좌표계)에서 다룬다.
바깥 방향은 윤곽선 자신의 진행 방향에서 뽑으므로 y축이 뒤집혀 있어도 맞는다.
"""
import math

# 윤곽선은 [(x, y, on_curve), ...] 의 리스트. 닫힌 것으로 본다.


def record_to_contours(recording):
    """RecordingPen 기록을 점 목록으로 편다. glyf(2차 베지어) 전용."""
    contours, cur = [], None
    for op, args in recording:
        if op == "moveTo":
            cur = [(args[0][0], args[0][1], True)]
        elif op == "lineTo":
            cur.append((args[0][0], args[0][1], True))
        elif op == "qCurveTo":
            pts = list(args)
            last = pts[-1]
            if last is None:          # 전부 off-curve 인 닫힌 윤곽선
                pts = pts[:-1]
                cur.extend((p[0], p[1], False) for p in pts)
            else:
                cur.extend((p[0], p[1], False) for p in pts[:-1])
                cur.append((last[0], last[1], True))
        elif op == "closePath":
            if cur and len(cur) >= 2:
                contours.append(cur)
            cur = None
    if cur and len(cur) >= 2:
        contours.append(cur)
    return contours


def signed_area(pts):
    a = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0, _ = pts[i]
        x1, y1, _ = pts[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _orient(pts):
    return 1.0 if signed_area(pts) > 0 else -1.0


def hole_flags(contours):
    """각 윤곽선이 구멍인지 판정한다.

    자기보다 큰 윤곽선 몇 개에 둘러싸여 있는지 세서 홀수면 구멍이다.
    법선은 윤곽선이 감싼 영역의 바깥을 가리키므로, 바깥 윤곽선에서는
    그 방향이 글자를 살찌우지만 구멍에서는 구멍을 키운다. 즉 획을 두껍게
    하려면 구멍에서는 부호를 뒤집어야 한다.
    """
    boxes = [bbox(p) for p in contours]
    areas = [(b[2] - b[0]) * (b[3] - b[1]) for b in boxes]
    flags = []
    for i, bi in enumerate(boxes):
        depth = sum(
            1 for j, bj in enumerate(boxes)
            if j != i and areas[j] > areas[i]
            and bj[0] <= bi[0] and bj[1] <= bi[1]
            and bj[2] >= bi[2] and bj[3] >= bi[3]
        )
        flags.append(depth % 2 == 1)
    return flags


def _normals(pts, s):
    """각 점에서 윤곽선이 감싼 영역의 바깥을 가리키는 단위 법선."""
    n = len(pts)
    out = []
    for i in range(n):
        px, py, _ = pts[(i - 1) % n]
        nx, ny, _ = pts[(i + 1) % n]
        tx, ty = nx - px, ny - py
        L = math.hypot(tx, ty)
        out.append((0.0, 0.0) if L < 1e-9 else (ty / L * s, -tx / L * s))
    return out


def apply_contrast(contours, wx, wy):
    """세로 기둥은 wx 만큼 불리고, 가로획은 wy 만큼 깎는다 (wy 는 보통 음수).

    법선의 x 성분이 큰 점 - 즉 세로획의 옆면 - 만 x 로 밀리고,
    y 성분이 큰 점 - 가로획의 위아래면 - 만 y 로 당겨진다.
    사선 획은 두 성분이 섞여 자연스럽게 중간값을 받는다.
    """
    for pts, is_hole in zip(contours, hole_flags(contours)):
        sign = -1.0 if is_hole else 1.0
        ns = _normals(pts, _orient(pts))
        for i, (x, y, on) in enumerate(pts):
            nx, ny = ns[i]
            pts[i] = (x + wx * nx * sign, y + wy * ny * sign, on)


def apply_sharpen(contours, amount, cos_thr):
    """볼록하고 날카로운 모서리를 바깥으로 더 내밀어 끝을 뾰족하게 만든다.

    cos_thr 보다 완만한 모서리와 오목한 모서리는 건드리지 않는다.
    꺾임이 심할수록 많이 밀리므로 쐐기 세리프의 끝과 삐침이 주로 살아난다.
    """
    moved = 0
    for pts, is_hole in zip(contours, hole_flags(contours)):
        if is_hole:                                 # 삐침과 세리프는 바깥 윤곽선에만 있다
            continue
        s = _orient(pts)
        n = len(pts)
        moves = [(0.0, 0.0)] * n
        for i in range(n):
            if not pts[i][2]:                       # off-curve 점은 제외
                continue
            px, py, _ = pts[(i - 1) % n]
            x, y, _ = pts[i]
            nx, ny, _ = pts[(i + 1) % n]
            ax, ay = x - px, y - py                 # 들어오는 방향
            bx, by = nx - x, ny - y                 # 나가는 방향
            la, lb = math.hypot(ax, ay), math.hypot(bx, by)
            if la < 1e-9 or lb < 1e-9:
                continue
            ax, ay, bx, by = ax / la, ay / la, bx / lb, by / lb
            dot = ax * bx + ay * by
            if dot > cos_thr:                       # 너무 완만하다
                continue
            if (ax * by - ay * bx) * s <= 0:        # 오목한 모서리다
                continue
            ux, uy = ax - bx, ay - by               # 모서리 끝이 향하는 방향
            lu = math.hypot(ux, uy)
            if lu < 1e-9:
                continue
            f = min(1.0, max(0.0, (cos_thr - dot) / (cos_thr + 1.0)))
            moves[i] = (ux / lu * amount * f, uy / lu * amount * f)
        for i, (dx, dy) in enumerate(moves):
            if dx or dy:
                x, y, on = pts[i]
                pts[i] = (x + dx, y + dy, on)
                moved += 1
    return moved


def apply_oval(contours, factor, xscale):
    """둥근 속공간을 가로로 좁혀 세로로 긴 타원으로 만든다.

    다른 윤곽선 안에 완전히 들어있고(= 구멍), 채움률과 가로세로비가 원에
    가까운 것만 고른다. ㅇ 과 ㅎ 의 동그라미가 여기 걸리고, ㅁ ㄹ 같은
    각진 속공간은 채움률이 1 에 가까워서 걸리지 않는다.
    """
    boxes = [bbox(p) for p in contours]
    flags = hole_flags(contours)
    for i, pts in enumerate(contours):
        if not flags[i]:
            continue
        x0, y0, x1, y1 = boxes[i]
        w, h = x1 - x0, y1 - y0
        if w <= 0 or h <= 0:
            continue
        if not 0.68 <= abs(signed_area(pts)) / (w * h) <= 0.95:
            continue
        if not 0.72 <= (w / xscale) / h <= 1.45:    # 자평을 되돌린 기준 비율
            continue
        cx = (x0 + x1) / 2.0
        for k, (x, y, on) in enumerate(pts):
            pts[k] = (cx + (x - cx) * factor, y, on)


def _n(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def contours_to_d(contours):
    """점 목록을 SVG path 의 d 속성으로 되돌린다."""
    out = []
    for pts in contours:
        n = len(pts)
        start = next((i for i in range(n) if pts[i][2]), None)
        if start is None:                            # 전부 off-curve
            x0, y0, _ = pts[0]
            x1, y1, _ = pts[1 % n]
            pts = [((x0 + x1) / 2, (y0 + y1) / 2, True)] + pts[1:] + [pts[0]]
            n, start = len(pts), 0
        pts = pts[start:] + pts[:start]

        d = [f"M{_n(pts[0][0])} {_n(pts[0][1])}"]
        i = 1
        while i <= n:
            x, y, on = pts[i % n]
            if on:
                d.append(f"L{_n(x)} {_n(y)}")
                i += 1
            else:
                nx, ny, non = pts[(i + 1) % n]
                if non:
                    ex, ey = nx, ny
                    i += 2
                else:
                    ex, ey = (x + nx) / 2.0, (y + ny) / 2.0
                    i += 1
                d.append(f"Q{_n(x)} {_n(y)} {_n(ex)} {_n(ey)}")
        d.append("Z")
        out.append("".join(d))
    return "".join(out)
