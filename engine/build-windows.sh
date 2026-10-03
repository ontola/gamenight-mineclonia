#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")/.." && pwd)
cache=${1:?Usage: engine/build-windows.sh NEW_BUILD_DIRECTORY}
mkdir -p "$cache"
cache=$(cd "$cache" && pwd)
test ! -e "$cache/source"
revision=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["engine"]["revision"])' "$here/sources.lock.json")
git clone --no-checkout https://github.com/ontola/luanti.git "$cache/source"
git -C "$cache/source" checkout --detach "$revision"
bash "$cache/source/gamenight/build-windows.sh" "$cache/windows"
