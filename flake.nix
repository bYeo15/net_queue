{
    description = "RottnestPy Flake";

    inputs = {
        nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
        flake-utils.url = "github:numtide/flake-utils";
    };

    outputs = { self, nixpkgs, flake-utils, ... }@inputs:
        flake-utils.lib.eachDefaultSystem (system:
            let
                pkgs = import nixpkgs { 
                    inherit system; 
                };
                python = pkgs.python311;
                pythonPkgs = pkgs.python311Packages;
            in rec {
                devShell = pkgs.mkShell {
                    packages = with pkgs; [
                        python
                        pythonPkgs.numpy
                        pythonPkgs.pytest
                        pythonPkgs.ipdb
                    ];

                    shellHook = ''
                        export PYTHONPATH="$PYTHONPATH:$(pwd)/src/worker_demo":
                    '';

                    # Disable Nix wrapper features
                    NIX_HARDENING_ENABLE = "";
                    NIX_ENFORCE_NO_NATIVE = "";
                };
            }
        );
}
