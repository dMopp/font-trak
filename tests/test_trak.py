"""Checks against a real static font without STAT (Inter-Regular.otf from the Inter release).

Run: python3 tests/test_trak.py path/to/Inter-Regular.otf
"""
import math
import os
import sys
import tempfile

import uharfbuzz as hb
from fontTools.ttLib import TTFont

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import font_trak  # noqa: E402

TEXT = "nnnn"


def advance(path, ptem):
    face = hb.Face(hb.Blob.from_file_path(path))
    font = hb.Font(face)
    font.ptem = ptem
    buf = hb.Buffer()
    buf.add_str(TEXT)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    return buf.glyph_positions[0].x_advance


def run(cmd, src, dst, *extra):
    assert font_trak.main([cmd, src, dst, *extra]) == 0


def main():
    src = sys.argv[1]
    tmp = tempfile.mkdtemp()
    plain = advance(src, 10)
    assert "STAT" not in TTFont(src), "test font must not have STAT"

    # trak without STAT is ignored by HarfBuzz -> the reason this tool exists
    no_stat = os.path.join(tmp, "no-stat.otf")
    font = TTFont(src)
    font_trak.formula(font, *font_trak.PRESETS["inter"], font_trak.DEFAULT_SIZES, font_trak.LINUX_TO_APPLE)
    font.save(no_stat)
    assert advance(no_stat, 10) == plain, "HarfBuzz applied trak without STAT; condition changed upstream?"

    # formula + STAT: tracking applied with the expected value at 10 pt (13.33 px)
    tracked = os.path.join(tmp, "formula.otf")
    run("formula", src, tracked, "--preset", "inter")
    upem = TTFont(src)["head"].unitsPerEm
    a, b, c = font_trak.PRESETS["inter"]
    expected = round((a + b * math.exp(c * 10 * 4 / 3)) * upem)
    got = advance(tracked, 10) - plain
    assert got == expected, f"formula: expected {expected}, got {got}"

    # remap: a table keyed by Apple points (px) is moved to 96-dpi points
    apple = os.path.join(tmp, "apple.otf")
    run("formula", src, apple, "--preset", "inter", "--scale", "1")
    remapped = os.path.join(tmp, "remapped.otf")
    run("remap", apple, remapped)
    apple_13 = advance(apple, 13) - plain
    linux_975 = advance(remapped, 9.75) - plain
    assert apple_13 == linux_975 != 0, f"remap: Apple 13 pt {apple_13} != Linux 9.75 pt {linux_975}"

    print(f"ok: plain={plain} formula@10pt={got} apple@13={apple_13} remapped@9.75={linux_975}")


if __name__ == "__main__":
    main()
