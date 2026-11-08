# font-trak

Size-dependent tracking for Linux, the way macOS does it: small text a little looser,
large text a little tighter.

Apple's fonts (SF Pro, SF Pro Display, SF Pro Rounded, …) carry this in an AAT `trak`
table, and Core Text applies it automatically. On Linux the same fonts render with no
tracking at all, even though HarfBuzz can apply `trak`. Two things stand in the way:

1. **HarfBuzz only applies `trak` when the font also has a `STAT` table**
   ([`hb-ot-shape.cc`](https://github.com/harfbuzz/harfbuzz/blob/main/src/hb-ot-shape.cc):
   `apply_trak = has trak && has STAT`). The static SF Pro `.otf` files have no `STAT`,
   so the table is ignored.
2. **Different points.** HarfBuzz picks the value by point size (`hb_font_set_ptem`).
   Pango (GTK) and Qt pass points at 96 dpi, while Apple's table is keyed by 72-dpi points,
   which equal pixels at 1x. A 13 px label is 9.75 pt on Linux and would get Apple's value
   for 9.75 px instead of 13 px.

`font-trak` fixes both in the font file: it adds a minimal `STAT` table and rescales the
size axis of `trak`. For fonts without a `trak` table it can generate one from a formula,
with a preset for [Inter's Dynamic Metrics](https://rsms.me/inter/dynmetrics/).

Nothing changes at runtime: there is no daemon or patched library, only modified font
files. Every app that shapes text with HarfBuzz and passes the point size (GTK/Pango, Qt)
picks the tracking up after a restart.

## Usage

```sh
font-trak info  SF-Pro-Text-Regular.otf
font-trak remap SF-Pro-Text-Regular.otf out/SF-Pro-Text-Regular.otf    # fonts with trak (Apple)
font-trak formula Inter-Regular.otf out/Inter-Regular.otf --preset inter
font-trak formula Some-Font.otf out/Some-Font.otf --abc -0.02 0.18 -0.17
```

- `remap --scale` (default `4/3`): Apple points per font point the app passes. 4/3 fits
  GTK and Qt at their usual 96 dpi.
- `formula`: `tracking_em = a + b * exp(c * px)`, with `px = pt * scale`.
  `--sizes` sets the points that get an entry (HarfBuzz interpolates between them).

Run it with Nix:

```sh
nix run github:dMopp/font-trak -- info SF-Pro-Text-Regular.otf
```

Without Nix, you need Python 3 and `fonttools`: `python3 font_trak.py …`.

## NixOS

`lib.patchFonts` runs the tool over every `.otf`/`.ttf` of a font package:

```nix
# flake inputs: font-trak.url = "github:dMopp/font-trak";
fonts.packages = [
  (inputs.font-trak.lib.patchFonts pkgs { fonts = my-sf-pro; args = [ "remap" ]; })
  (inputs.font-trak.lib.patchFonts pkgs {
    fonts = pkgs.source-sans;
    args = [ "formula" "--abc" "-0.02" "0.18" "-0.17" ];
  })
];
```

`skip = [ "InterDisplay*" ]` leaves matching files untouched, e.g. the display cuts of a
family, which are already drawn tighter.

## Optical sizes

macOS also switches from SF Pro Text to SF Pro Display at 20 px. On Linux, a fontconfig rule
can do that for apps that pass the size to fontconfig (GTK/Pango). Qt resolves family names
itself and ignores it. 20 px is 15 pt at 96 dpi:

```xml
<match target="pattern">
  <test name="family"><string>SF Pro Text</string></test>
  <test name="size" compare="more_eq"><double>15</double></test>
  <edit name="family" mode="assign" binding="strong"><string>SF Pro Display</string></edit>
</match>
```

## Limits

- Chromium/Electron are untested.
- The Inter preset is the published formula for Inter 3. Inter 4 has no official values,
  so treat it as a close approximation.
- This repository contains no fonts. Apple's font license only covers mock-ups for Apple
  platforms. Whether you use SF Pro on Linux anyway is your call.

## Tests

```sh
nix flake check
```

The tests run against Inter from nixpkgs. They check that HarfBuzz ignores `trak` without
`STAT`, that the formula produces the expected value, and that `remap` moves Apple's 13 pt
value to 9.75 pt.

Written with help from Claude Code.

## License

MIT
