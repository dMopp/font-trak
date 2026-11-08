{
  description = "Size-dependent tracking (AAT trak) for HarfBuzz on Linux";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});

      mkTool = pkgs:
        let python = pkgs.python3.withPackages (p: [ p.fonttools ]);
        in pkgs.runCommand "font-trak" { meta.mainProgram = "font-trak"; } ''
          install -Dm755 ${./font_trak.py} $out/libexec/font_trak.py
          mkdir -p $out/bin
          cat > $out/bin/font-trak <<EOF
          #!${pkgs.runtimeShell}
          exec ${python}/bin/python3 -I $out/libexec/font_trak.py "\$@"
          EOF
          chmod +x $out/bin/font-trak
        '';
    in
    {
      packages = forAll (pkgs: rec {
        font-trak = mkTool pkgs;
        default = font-trak;
      });

      # Run font-trak over every .otf/.ttf of a font package:
      #   font-trak.lib.patchFonts pkgs { fonts = pkgs.inter; args = [ "formula" "--preset" "inter" ]; }
      #   font-trak.lib.patchFonts pkgs { fonts = my-sf-pro; args = [ "remap" ]; }
      # Files that the command does not change are copied as they are.
      lib.patchFonts = pkgs: { fonts, args, name ? "${if builtins.isAttrs fonts then fonts.name else "fonts"}-trak", skip ? [ ] }:
        pkgs.runCommand name { nativeBuildInputs = [ (mkTool pkgs) ]; } ''
          cp -r --no-preserve=mode ${fonts} $out
          find $out -type f \( -name '*.otf' -o -name '*.ttf' \) | while read -r f; do
            case "$(basename "$f")" in
              ${if skip == [ ] then "__none__" else pkgs.lib.concatStringsSep "|" skip}) continue ;;
            esac
            font-trak ${pkgs.lib.escapeShellArg (builtins.head args)} "$f" "$f.new" ${pkgs.lib.escapeShellArgs (builtins.tail args)}
            mv "$f.new" "$f"
          done
        '';

      checks = forAll (pkgs: {
        default =
          let python = pkgs.python3.withPackages (p: [ p.fonttools p.uharfbuzz ]);
          in pkgs.runCommand "font-trak-test" { } ''
            cp -r ${./.} src && chmod -R u+w src
            ${python}/bin/python3 -I src/tests/test_trak.py ${pkgs.inter.src}/extras/otf/Inter-Regular.otf
            touch $out
          '';
      });
    };
}
