#!/usr/bin/env python3
"""Build offline.html: index.html with its web fonts embedded, so it works without a network.

Only the glyphs the page actually uses are kept, then each subset is written as WOFF2 and
inlined as a data: URI. Subsets are Modified Versions under the SIL OFL, and IBM Plex has the
Reserved Font Name "Plex", so every embedded font is renamed to "Nakseo ..." and the licence
travels with the file.

    pip install fonttools brotli
    python3 tools/build_offline.py
"""
import base64
import io
import pathlib
import re
import urllib.request

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / "tools" / ".font-cache"
RAW = "https://raw.githubusercontent.com/google/fonts/main/"

# (source path in google/fonts, CSS family, weight, (old name, new name) pairs, ascii only?)
FONTS = [
    ("ofl/gaegu/Gaegu-Bold.ttf", "Nakseo Hand", 700, [("Gaegu", "Nakseo Hand")], False),
    ("ofl/ibmplexsanskr/IBMPlexSansKR-Regular.ttf", "Nakseo Sans", 400,
     [("IBM Plex Sans KR", "Nakseo Sans"), ("IBMPlexSansKR", "NakseoSans")], False),
    ("ofl/ibmplexsanskr/IBMPlexSansKR-SemiBold.ttf", "Nakseo Sans", 600,
     [("IBM Plex Sans KR", "Nakseo Sans"), ("IBMPlexSansKR", "NakseoSans")], False),
    ("ofl/ibmplexmono/IBMPlexMono-Medium.ttf", "Nakseo Mono", 500,
     [("IBM Plex Mono", "Nakseo Mono"), ("IBMPlexMono", "NakseoMono")], True),
]
LICENSES = ["ofl/gaegu/OFL.txt", "ofl/ibmplexsanskr/OFL.txt"]

# CSS/JS font references in index.html -> embedded family names
RENAMES = [
    ("'Gaegu'", "'Nakseo Hand'"),
    ('"Gaegu, ', "\"'Nakseo Hand', "),
    ("'IBM Plex Sans KR'", "'Nakseo Sans'"),
    ("'IBM Plex Mono'", "'Nakseo Mono'"),
]


def fetch(path):
    dest = CACHE / path
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(RAW + path, timeout=60) as r:
            dest.write_bytes(r.read())
    return dest


def subset_woff2(src, text, renames):
    font = TTFont(src)
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    opts.name_languages = ["*"]
    opts.notdef_outline = True
    sub = subset.Subsetter(options=opts)
    sub.populate(text=text)
    sub.subset(font)
    for rec in font["name"].names:
        s = rec.toUnicode()
        for old, new in renames:
            s = s.replace(old, new)
        rec.string = s
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    return buf.getvalue()


def main():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    ascii_chars = "".join(chr(c) for c in range(0x20, 0x7F))
    page_chars = "".join(sorted(set(html) | set(ascii_chars)))

    faces = []
    for path, family, weight, renames, ascii_only in FONTS:
        data = subset_woff2(fetch(path), ascii_chars if ascii_only else page_chars, renames)
        uri = "data:font/woff2;base64," + base64.b64encode(data).decode("ascii")
        faces.append(
            f"@font-face {{ font-family: '{family}'; font-style: normal; font-weight: {weight};"
            f" font-display: swap; src: url({uri}) format('woff2'); }}"
        )
        print(f"{family} {weight}: {len(data) / 1024:.0f} KB")

    out = re.sub(r'<link rel="(?:preconnect|stylesheet)" href="https://fonts\.(?:googleapis|gstatic)\.com[^>]*>\n', "", html)
    for old, new in RENAMES:
        assert old in out, old
        out = out.replace(old, new)
    assert "Gaegu" not in out and "Plex" not in out and "fonts.googleapis" not in out

    licence = "\n".join(fetch(p).read_text(encoding="utf-8").strip().splitlines()[0] for p in LICENSES)
    ofl = fetch(LICENSES[1]).read_text(encoding="utf-8").split("\n", 1)[1].strip()
    notice = (
        "<!--\nEmbedded fonts: subsets of Gaegu Bold, IBM Plex Sans KR (Regular, SemiBold) and IBM Plex Mono Medium,\n"
        "renamed to Nakseo Hand / Nakseo Sans / Nakseo Mono as Modified Versions under the SIL Open Font License 1.1.\n"
        + licence + "\n\n" + ofl.replace("--", "- -") + "\n-->\n"
    )
    out = out.replace("<head>\n", "<head>\n" + notice, 1)
    out = out.replace("<style>\n", "<style>\n" + "\n".join(faces) + "\n", 1)
    (ROOT / "offline.html").write_text(out, encoding="utf-8")
    print(f"offline.html: {len(out.encode('utf-8')) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
