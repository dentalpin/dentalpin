#!/usr/bin/env bash
# Vendor the pinned OHIF viewer build next to ohif-config.js.
# Pinned: OHIF/Viewers v3.12.14 (MIT — notice preserved in module NOTICE.md).
# OHIF publishes no static dist asset, so this builds from source (needs
# node >= 22 + yarn). The dist/ output (~tens of MB) is a BUILD ARTIFACT:
# never commit it — only ohif-config.js + this script are tracked.
set -euo pipefail

PIN="v3.12.14"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"

git clone --depth 1 --branch "$PIN" https://github.com/OHIF/Viewers.git "$WORK/viewers"
cd "$WORK/viewers"
yarn install --frozen-lockfile
yarn build

rm -rf "$HERE/dist"
cp -r platform/viewer/dist "$HERE/dist"
cp "$HERE/ohif-config.js" "$HERE/dist/ohif-config.js"
echo "vendored OHIF $PIN -> $HERE/dist (untracked build output)"
