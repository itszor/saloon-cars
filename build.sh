#!/bin/sh
# Build Saloon Cars from your own copy of the game:
#     ./build.sh "Saloon Cars ()(Fourth Dimension).zip"    (or a directory holding !Saloon)
# then: cd recomp && ./salooncars
# The steps are recipe.json's "build", run by SuperSpider's tools/weave.py.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SUPERSPIDER="${SUPERSPIDER:-$HOME/stuff/superspider}"
[ $# -gt 0 ] || { echo "usage: $0 GAME.zip | DIRECTORY" >&2; exit 2; }
(cd "$SUPERSPIDER" && dune build)
WEAVE_RECIPES="$HERE" exec python3 -I "$SUPERSPIDER/tools/weave.py" build "$@"
