{ pkgs, ... }:

{

  # https://devenv.sh/packages/
  packages = [
    pkgs.git
    pkgs.poetry
  ];

  # https://devenv.sh/languages/
  languages.nix.enable = true;

  # See full reference at https://devenv.sh/reference/options/
}
