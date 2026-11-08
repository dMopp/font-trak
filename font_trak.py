#!/usr/bin/env python3
"""Make size-dependent tracking (the AAT 'trak' table) work with HarfBuzz on Linux.

HarfBuzz applies 'trak' with its OpenType shaper only when the font also has a 'STAT'
table (hb-ot-shape.cc: apply_trak = has trak && has STAT). Static fonts often lack STAT,
so their tracking is silently ignored.

HarfBuzz looks up the track value by the font's point size (hb_font_set_ptem). Pango and
Qt pass points at 96 dpi, while Apple's tables are keyed by 72-dpi points (= pixels at 1x).
Without correction a 13 px label gets the value Apple uses for 9.75 px.

Commands:
  info     show trak and STAT of a font
  remap    rescale the size axis of an existing trak table, add STAT
  formula  create trak from tracking_em = a + b * exp(c * px), add STAT
"""
import argparse
import math
import sys

from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._t_r_a_k import TrackData, TrackTableEntry

# Points at 96 dpi -> points at 72 dpi
LINUX_TO_APPLE = 96 / 72

# Inter's published "Dynamic Metrics" (https://rsms.me/inter/dynmetrics/, Inter 3.x)
PRESETS = {"inter": (-0.0223, 0.185, -0.1745)}

DEFAULT_SIZES = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 24, 32, 48]


def add_stat(font):
    """Add a minimal STAT table (one weight axis value) if the font has none."""
    if "STAT" in font:
        return False
    weight = font["OS/2"].usWeightClass
    style = font["name"].getBestSubFamilyName() or "Regular"
    buildStatTable(font, [dict(tag="wght", name="Weight", values=[dict(value=weight, name=style)])])
    return True


def remap(font, scale):
    """Divide every size of the trak table by scale (Apple pt -> Linux pt with 4/3)."""
    if "trak" not in font:
        return False
    for entry in font["trak"].horizData.values():
        old = dict(entry)
        entry.clear()
        for size, value in old.items():
            entry[round(size / scale, 4)] = value
    return True


def formula(font, a, b, c, sizes, scale):
    """Build a trak table from tracking_em = a + b * exp(c * px), keyed by font points."""
    upem = font["head"].unitsPerEm
    entry = TrackTableEntry(nameIndex=font["name"].addName("Normal"))
    for pt in sizes:
        px = pt * scale
        entry[float(pt)] = round((a + b * math.exp(c * px)) * upem)
    trak = newTable("trak")
    trak.version = 1.0
    trak.format = 0
    trak.horizData = TrackData({0.0: entry})
    trak.vertData = TrackData()
    font["trak"] = trak
    return True


def info(path):
    font = TTFont(path)
    print(f"{path}: STAT={'STAT' in font} trak={'trak' in font} upem={font['head'].unitsPerEm}")
    if "trak" in font:
        for track, entry in sorted(font["trak"].horizData.items()):
            values = ", ".join(f"{s:g}:{v}" for s, v in sorted(entry.items()))
            print(f"  track {track:g}: {values}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("info", help="show trak and STAT")
    pi.add_argument("fonts", nargs="+")

    pr = sub.add_parser("remap", help="rescale an existing trak table and add STAT")
    pr.add_argument("input")
    pr.add_argument("output")
    pr.add_argument("--scale", type=float, default=LINUX_TO_APPLE,
                    help="Apple-pt per font-pt the app passes (default 4/3 for 96 dpi)")

    pf = sub.add_parser("formula", help="create trak from a + b*exp(c*px) and add STAT")
    pf.add_argument("input")
    pf.add_argument("output")
    pf.add_argument("--preset", choices=sorted(PRESETS))
    pf.add_argument("--abc", type=float, nargs=3, metavar=("A", "B", "C"))
    pf.add_argument("--sizes", type=float, nargs="+", default=DEFAULT_SIZES, help="font sizes in points")
    pf.add_argument("--scale", type=float, default=LINUX_TO_APPLE, help="px per point (default 4/3 for 96 dpi)")

    args = p.parse_args(argv)

    if args.cmd == "info":
        for path in args.fonts:
            info(path)
        return 0

    font = TTFont(args.input)
    if args.cmd == "remap":
        changed = remap(font, args.scale)
        if not changed:
            print(f"{args.input}: no trak table, copied unchanged", file=sys.stderr)
    else:
        if bool(args.preset) == bool(args.abc):
            p.error("formula needs exactly one of --preset or --abc")
        a, b, c = PRESETS[args.preset] if args.preset else args.abc
        changed = formula(font, a, b, c, args.sizes, args.scale)
    if changed:
        add_stat(font)
    font.save(args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
