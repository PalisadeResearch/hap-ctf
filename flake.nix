{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      uv2nix,
      pyproject-nix,
      pyproject-build-systems,
      ...
    }:
    let
      inherit (nixpkgs) lib;

      inherit (pkgs.callPackages pyproject-nix.build.util { }) mkApplication;
      hacks = pyproject-nix.build.hacks { inherit pkgs lib; };

      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

      overlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; };

      pyprojectOverrides = _final: _prev: {
        hap-ctf = _prev.hap-ctf.overrideAttrs (old: {
          passthru = old.passthru // {
            dependencies = old.passthru.dependencies // {
              seccomp = [ ];
            };
          };
        });
        seccomp = hacks.nixpkgsPrebuilt {
          from = pkgs.python313Packages.seccomp;
          prev = {
            drvPath = pkgs.python313Packages.seccomp.drvPath;
            nativeBuildInputs = [
              (pyproject-nix.build.packages {
                inherit pkgs python;
                stdenv = pkgs.stdenv;
                newScope = pkgs.newScope;
                buildPackages = pkgs.buildPackages;
              }).hooks.pyprojectHook
            ];
            passthru = { };
          };
        };
      };

      pkgs = nixpkgs.legacyPackages.x86_64-linux;
      python = pkgs.python313;

      pythonSet =
        (pkgs.callPackage pyproject-nix.build.packages {
          inherit python;
        }).overrideScope
          (
            lib.composeManyExtensions [
              pyproject-build-systems.overlays.default
              overlay
              pyprojectOverrides
            ]
          );

      venv = pythonSet.mkVirtualEnv "venv" workspace.deps.default;
    in
    {
      inherit pythonSet;
      packages.x86_64-linux.default = mkApplication ({
        inherit venv;
        package = pythonSet.hap-ctf;
      });

      apps.x86_64-linux = {
        default = {
          type = "app";
          program = "${self.packages.x86_64-linux.default}/bin/api";
        };
      };

      devShells.x86_64-linux = {
        default =
          let
            editableOverlay = workspace.mkEditablePyprojectOverlay { root = "$REPO_ROOT"; };

            editablePythonSet = pythonSet.overrideScope (
              lib.composeManyExtensions [
                editableOverlay
                (final: prev: {
                  hap-ctf = prev.hap-ctf.overrideAttrs (old: {
                    src = lib.fileset.toSource {
                      root = old.src;
                      fileset = lib.fileset.unions [
                        (old.src + "/pyproject.toml")
                        (lib.fileset.fileFilter (file: file.hasExt "py") (old.src + "/src"))
                      ];
                    };

                    nativeBuildInputs =
                      old.nativeBuildInputs
                      ++ final.resolveBuildSystem {
                        # Hatchling depends on `editables` (PEP-660)
                        editables = [ ];
                      };
                  });

                })
              ]
            );

            virtualenv = editablePythonSet.mkVirtualEnv "dev-venv" workspace.deps.all;

          in
          pkgs.mkShell {
            packages = [
              virtualenv
              pkgs.uv
              pkgs.nil
              pkgs.nixfmt-rfc-style
              pkgs.ninja
              pkgs.entr
            ];

            env = {
              UV_NO_SYNC = "1"; # Don't create venv using uv
              UV_PYTHON = "${virtualenv}/bin/python"; # Force uv to use Python interpreter from venv
              UV_PYTHON_DOWNLOADS = "never"; # Prevent uv from downloading managed Pythons
            };

            shellHook = ''
              unset PYTHONPATH # Undo dependency propagation by nixpkgs.
              export REPO_ROOT=$(git rev-parse --show-toplevel)
            '';
          };
      };
    };
}
