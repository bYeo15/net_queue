{
    description = "net_queue flake";

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
                    ];

                    # Add src folder to local python path (not how it should be done long-term)
                    shellHook = ''
                        export PYTHONPATH="$PYTHONPATH:$(pwd)/src/net_queue":
                    '';
                };
            }
        );
}
