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

SVG 가 원본이고 PNG 는 그 SVG 를 래스터화한 결과라 둘의 기하는 동일하다.
"""
import os

import cairosvg
from PIL import Image
from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
OUT_DIR = os.path.join(HERE, "out")

CANVAS = 2048
WORDS = ["추석", "할인", "주유", "연휴"]   # 좌상, 우상, 좌하, 우하
ALL_CHARS = "".join(WORDS)

LETTER_HEIGHT = 300.0    # 여덟 음절 전체의 잉크 높이(px). 모든 시안 공통
INK_GAP = 0.085          # 음절 사이 잉크 간격 (글자 높이 대비)
COL_X = (560, 1488)      # 좌/우 단어의 중심 x
ROW_Y = (620, 1428)      # 상/하 행의 중심 y

# 시안: 키 -> (폰트 파일, 설명)
FACES = {
    "hahmlet":   ("Hahmlet-700.ttf",       "함렛 Bold — 고대비 모던 레트로"),
    "nanum":     ("NanumMyeongjo-800.ttf", "나눔명조 ExtraBold — 정통 견출명조"),
    "songmyung": ("SongMyung.ttf",         "송명 — 옛 활판, 가는 획"),
}
XSCALES = {"110": 1.10, "120": 1.20}   # 자평(가로 장평)


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
    """폰트 크기, 음절 피치, 단어 폭을 px 로 계산한다."""
    size = LETTER_HEIGHT / (m["ink_y1"] - m["ink_y0"])      # px per em
    ink_w = (m["ink_x1"] - m["ink_x0"]) * size * xscale
    pitch = ink_w + INK_GAP * LETTER_HEIGHT
    return {
        "size": size,
        "pitch": pitch,
        "word_w": pitch + ink_w,
        "ink_left": m["ink_x0"] * size * xscale,
        "ink_top": m["ink_y1"] * size,
    }


def build_svg(face_key, xkey):
    fname, _ = FACES[face_key]
    m = face_metrics(os.path.join(FONT_DIR, fname))
    xscale = XSCALES[xkey]
    L = layout(m, xscale)
    unit = L["size"] / m["upem"]        # 폰트 유닛 -> px

    paths = []
    for i, word in enumerate(WORDS):
        cx, cy = COL_X[i % 2], ROW_Y[i // 2]
        word_left = cx - L["word_w"] / 2.0
        baseline = cy - LETTER_HEIGHT / 2.0 + L["ink_top"]
        for j, ch in enumerate(word):
            ox = word_left + j * L["pitch"] - L["ink_left"]
            # y축 뒤집고, 가로만 자평 배율을 먹인다
            t = Transform(unit * xscale, 0, 0, -unit, ox, baseline)
            spen = SVGPathPen(m["glyphset"])
            m["glyphset"][m["cmap"][ord(ch)]].draw(TransformPen(spen, t))
            paths.append(f'    <path d="{spen.getCommands()}"/>')

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS}" height="{CANVAS}" '
        f'viewBox="0 0 {CANVAS} {CANVAS}">\n'
        f'  <rect width="{CANVAS}" height="{CANVAS}" fill="#000000"/>\n'
        f'  <g fill="#ffffff" fill-rule="nonzero">\n'
        + "\n".join(paths)
        + "\n  </g>\n</svg>\n"
    )
    return svg, L


def contact_sheet(path_out, tile=660, pad=10):
    """여섯 시안을 한 장에 모아 비교용 시트를 만든다 (가로: 시안, 세로: 자평)."""
    faces, xs = list(FACES), list(XSCALES)
    w = pad + len(faces) * (tile + pad)
    h = pad + len(xs) * (tile + pad)
    sheet = Image.new("RGB", (w, h), (32, 32, 32))
    for c, face_key in enumerate(faces):
        for r, xkey in enumerate(xs):
            src = os.path.join(OUT_DIR, f"lettering_{face_key}_{xkey}.png")
            im = Image.open(src).convert("RGB").resize((tile, tile), Image.LANCZOS)
            sheet.paste(im, (pad + c * (tile + pad), pad + r * (tile + pad)))
    sheet.save(path_out)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"{'시안':26s} {'폰트크기':>9s} {'피치':>8s} {'단어폭':>8s} "
          f"{'바깥여백':>8s} {'가운데여백':>9s}")
    for face_key in FACES:
        for xkey in XSCALES:
            stem = f"lettering_{face_key}_{xkey}"
            svg, L = build_svg(face_key, xkey)

            svg_path = os.path.join(OUT_DIR, stem + ".svg")
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(svg)

            cairosvg.svg2png(
                bytestring=svg.encode("utf-8"),
                write_to=os.path.join(OUT_DIR, stem + ".png"),
                output_width=CANVAS, output_height=CANVAS,
            )

            margin = COL_X[0] - L["word_w"] / 2
            gutter = (COL_X[1] - L["word_w"] / 2) - (COL_X[0] + L["word_w"] / 2)
            print(f"{stem:26s} {L['size']:8.2f}px {L['pitch']:7.1f}px "
                  f"{L['word_w']:7.1f}px {margin:7.1f}px {gutter:8.1f}px")

    contact_sheet(os.path.join(OUT_DIR, "_contact_sheet.png"))
    print("\n_contact_sheet.png (가로: 시안 3종, 세로: 자평 110 / 120)")


if __name__ == "__main__":
    main()
