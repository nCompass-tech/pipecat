{
  description = "Benchmarking tool";

  inputs = { nixpkgs.url = "github:NixOS/nixpkgs"; };

  outputs = { self, nixpkgs } :
    let
      python_pkgs = pkgs : (with pkgs.python311Packages; [
            pip
          ]);

      system_pkgs = pkgs : (with pkgs; [
          pyright
        ]);

      venv_name="venv-lsp";
      venv_pip_pkgs = ''
          set -e
          python3 -m venv ${venv_name}
          source ${venv_name}/bin/activate
          pip install uv
          uv pip install docker
          uv pip install -r dev-requirements.txt
          set +e
          '';

      free_pkgs_linux = import nixpkgs {
        system = "x86_64-linux";
        config.allowUnfree = true;
        config.nvidia.acceptLicense = true;
      };
      
      free_pkgs_osx = import nixpkgs {
        system = "aarch64-darwin";
        config.allowUnfree = true;
      };
      
      linuxNixEnvPackages = pkgs : 
        pkgs.mkShell {
          buildInputs = (python_pkgs pkgs) ++ (system_pkgs pkgs);
          shellHook = 
          ''
            export PS1="$( [[ -z $IN_NIX_SHELL ]] && echo "" || echo "[$name]" ) $PS1"
            export LD_LIBRARY_PATH=${pkgs.lib.makeLibraryPath [ 
                                        pkgs.stdenv.cc.cc 
                                    ]}:$LD_LIBRARY_PATH
          '' + venv_pip_pkgs;
        };
      
      osxNixEnvPackages = pkgs : 
        pkgs.mkShell {
          buildInputs = (python_pkgs pkgs) ++ (system_pkgs pkgs);
          shellHook = 
          ''
            export PS1="$( [[ -z $IN_NIX_SHELL ]] && echo "" || echo "[$name]" ) $PS1"
          '' + venv_pip_pkgs;
        };
    
    in {
      devShell.aarch64-darwin = osxNixEnvPackages free_pkgs_osx;
      devShell.x86_64-linux = linuxNixEnvPackages free_pkgs_linux;
    };
}

