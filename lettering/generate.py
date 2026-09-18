#!/usr/bin/env python3
"""
한글 레터링 시트 생성기 — 추석 / 할인 / 주유 / 연휴

2048x2048, 순흑 배경에 순백 글자, 2x2 그리드.

한 시트 안의 네 단어는 글자 높이, 획 굵기, 자간, 전체 폭, 베이스라인이 전부
동일하다. 같은 폰트를 같은 크기, 같은 피치로 조판하므로 구조적으로 보장된다.
자음의 위치별 변형(초성/종성)과 모음 삐침도 폰트가 설계한 한 벌을 그대로
쓰므로 단어끼리 어긋나지 않는다.

글자 높이는 시안(폰트) 사이에서도 같게 정규화한다. 여덟 음절 전체의 잉크
높이를 재서 LETTER_HEIGHT 에 맞추므로, 세 시안을 나란히 놓고 자평만 비교할
수 있다.

`refined_*` 시안은 여기에 윤곽선 후처리(refine.py)를 더 얹은 것이다. 획 대비를
키우고, 쐐기 세리프 끝을 내밀고, ㅇ 의 속공간을 세로 타원으로 좁힌다.

SVG 가 원본이고 PNG 는 그 SVG 를 래스터화한 결과라 둘의 기하는 동일하다.
"""
import os

import cairosvg
from PIL import Image
from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

import refine

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
OUT_DIR = os.path.join(HERE, "out")

CANVAS = 2048
WORDS = ["추석", "할인", "주유", "연휴"]   # 좌상, 우상, 좌하, 우하
ALL_CHARS = "".join(WORDS)

LETTER_HEIGHT = 330.0    # 여덟 음절 전체의 잉크 높이(px). 모든 시안 공통
INK_GAP = 0.060          # 음절 사이 잉크 간격 (글자 높이 대비)
COL_TIGHTEN = 1.00       # 1.0 = 바깥 여백과 가운데 여백이 같아지는 균형점
ROW_TIGHTEN = 1.00       # 1.0 미만이면 두 행이 서로 가까워진다

FACES = {
    "hahmlet":   ("Hahmlet-700.ttf",       "함렛 Bold — 고대비 모던 레트로"),
    "nanum":     ("NanumMyeongjo-800.ttf", "나눔명조 ExtraBold — 정통 견출명조"),
    "songmyung": ("SongMyung.ttf",         "송명 — 옛 활판, 가는 획"),
}

# 윤곽선 후처리 값. 길이는 전부 em 단위라 글자 크기를 바꿔도 비율이 유지된다.
REFINE = {
    "contrast_x":  0.009,   # 세로 기둥을 양옆으로 이만큼 불린다
    "contrast_y": -0.009,   # 가로획을 위아래로 이만큼 깎는다
    "sharpen":     0.014,   # 날카로운 모서리를 바깥으로 이만큼 더 내민다
    "sharpen_cos": 0.35,    # 이보다 완만한 모서리는 건드리지 않는다 (약 70도)
    "oval":        0.90,    # ㅇ 속공간의 가로 배율
}

# (파일 이름, 폰트 키, 자평, 후처리 여부)
VARIANTS = (
    [(f"lettering_{k}_{x}", k, int(x) / 100, False)
     for k in FACES for x in ("110", "120")]
    + [(f"refined_hahmlet_{x}", "hahmlet", int(x) / 100, True)
       for x in ("120", "125", "130")]
)


def face_metrics(path):
    """여덟 음절 합집합의 잉크 박스를 em 단위로 잰다."""
    tt = TTFont(path, lazy=True)
    upem = tt["head"].unitsPerEm
    cmap = tt.getBestCmap()
    glyphset = tt.getGlyphSet()

    xs, ys = [], []
    for ch in ALL_CHARS:
        pen = BoundsPen(glyphset)
        glyphset[cmap[ord(ch)]].draw(pen)
        if pen.bounds:
            x0, y0, x1, y1 = pen.bounds
            xs += [x0, x1]
            ys += [y0, y1]

    return {
        "upem": upem, "cmap": cmap, "glyphset": glyphset,
        "ink_x0": min(xs) / upem, "ink_x1": max(xs) / upem,
        "ink_y0": min(ys) / upem, "ink_y1": max(ys) / upem,
    }


def layout(m, xscale):
    """폰트 크기, 음절 피치, 단어 폭, 네 단어의 중심 좌표를 px 로 계산한다."""
    size = LETTER_HEIGHT / (m["ink_y1"] - m["ink_y0"])      # px per em
    ink_w = (m["ink_x1"] - m["ink_x0"]) * size * xscale
    pitch = ink_w + INK_GAP * LETTER_HEIGHT
    word_w = pitch + ink_w

    # 바깥 여백과 가운데 여백이 같아지는 지점에서 열/행을 잡는다
    cx = (CANVAS - word_w / 2.0) / 3.0
    cy = (CANVAS - LETTER_HEIGHT / 2.0) / 3.0
    half = CANVAS / 2.0
    cx = half - (half - cx) * COL_TIGHTEN
    cy = half - (half - cy) * ROW_TIGHTEN

    return {
        "size": size, "pitch": pitch, "word_w": word_w,
        "col_x": (cx, CANVAS - cx),
        "row_y": (cy, CANVAS - cy),
        "ink_left": m["ink_x0"] * size * xscale,
        "ink_top": m["ink_y1"] * size,
    }


def build_svg(face_key, xscale, refined):
    fname, _ = FACES[face_key]
    m = face_metrics(os.path.join(FONT_DIR, fname))
    L = layout(m, xscale)
    unit = L["size"] / m["upem"]        # 폰트 유닛 -> px

    paths = []
    for i, word in enumerate(WORDS):
        cx, cy = L["col_x"][i % 2], L["row_y"][i // 2]
        word_left = cx - L["word_w"] / 2.0
        baseline = cy - LETTER_HEIGHT / 2.0 + L["ink_top"]
        for j, ch in enumerate(word):
            ox = word_left + j * L["pitch"] - L["ink_left"]
            # y축 뒤집고, 가로만 자평 배율을 먹인다
            t = Transform(unit * xscale, 0, 0, -unit, ox, baseline)
            rec = RecordingPen()
            m["glyphset"][m["cmap"][ord(ch)]].draw(TransformPen(rec, t))
            contours = refine.record_to_contours(rec.value)

            if refined:
                px = L["size"]          # em -> px 환산 계수
                refine.apply_oval(contours, REFINE["oval"], xscale)
                refine.apply_contrast(contours,
                                      REFINE["contrast_x"] * px,
                                      REFINE["contrast_y"] * px)
                refine.apply_sharpen(contours,
                                     REFINE["sharpen"] * px,
                                     REFINE["sharpen_cos"])

            paths.append(f'    <path d="{refine.contours_to_d(contours)}"/>')

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS}" height="{CANVAS}" '
        f'viewBox="0 0 {CANVAS} {CANVAS}">\n'
        f'  <rect width="{CANVAS}" height="{CANVAS}" fill="#000000"/>\n'
        f'  <g fill="#ffffff" fill-rule="nonzero">\n'
        + "\n".join(paths)
        + "\n  </g>\n</svg>\n"
    )
    return svg, L


def contact_sheet(stems, path_out, cols, tile=660, pad=10):
    rows = (len(stems) + cols - 1) // cols
    sheet = Image.new("RGB", (pad + cols * (tile + pad),
                              pad + rows * (tile + pad)), (32, 32, 32))
    for n, stem in enumerate(stems):
        im = Image.open(os.path.join(OUT_DIR, stem + ".png"))
        im = im.convert("RGB").resize((tile, tile), Image.LANCZOS)
        sheet.paste(im, (pad + (n % cols) * (tile + pad),
                         pad + (n // cols) * (tile + pad)))
    sheet.save(path_out)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"{'시안':26s} {'폰트크기':>9s} {'피치':>8s} {'단어폭':>8s} "
          f"{'바깥여백':>8s} {'가운데여백':>9s}")

    for stem, face_key, xscale, refined in VARIANTS:
        svg, L = build_svg(face_key, xscale, refined)
        with open(os.path.join(OUT_DIR, stem + ".svg"), "w", encoding="utf-8") as f:
            f.write(svg)
        cairosvg.svg2png(bytestring=svg.encode("utf-8"),
                         write_to=os.path.join(OUT_DIR, stem + ".png"),
                         output_width=CANVAS, output_height=CANVAS)

        margin = L["col_x"][0] - L["word_w"] / 2
        gutter = (L["col_x"][1] - L["word_w"] / 2) - (L["col_x"][0] + L["word_w"] / 2)
        print(f"{stem:26s} {L['size']:8.2f}px {L['pitch']:7.1f}px "
              f"{L['word_w']:7.1f}px {margin:7.1f}px {gutter:8.1f}px")

    base = [v[0] for v in VARIANTS if not v[3]]
    ref = [v[0] for v in VARIANTS if v[3]]
    contact_sheet(base, os.path.join(OUT_DIR, "_contact_base.png"), cols=3)
    contact_sheet(ref, os.path.join(OUT_DIR, "_contact_refined.png"), cols=3)
    print("\n_contact_base.png     기본 시안 (가로: 폰트 3종, 세로: 자평 110 / 120)")
    print("_contact_refined.png  후처리 시안 (함렛, 자평 120 / 125 / 130)")


if __name__ == "__main__":
    main()
