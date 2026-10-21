#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "=========================================================="
echo "  NEXUS — Building Production macOS App & DMG Installer"
echo "=========================================================="

TARGET_TRIPLE="$(rustc -vV | sed -n 's|host: ||p')"
if [ -z "$TARGET_TRIPLE" ]; then
  TARGET_TRIPLE="aarch64-apple-darwin"
fi

SIDECAR_BINARY="apps/ambient/src-tauri/binaries/nexus-engine-${TARGET_TRIPLE}"

if [ ! -f "$SIDECAR_BINARY" ]; then
  echo "--> Standalone engine binary not found. Compiling now..."
  ./scripts/build_engine_sidecar.sh
else
  echo "--> Found existing engine sidecar: $SIDECAR_BINARY"
fi

echo "--> Building production Ambient frontend..."
npm --workspace=@nexus/ambient run build

echo "--> Running Tauri 2.0 DMG & APP Packager..."
npm --workspace=@nexus/ambient exec -- tauri build --bundles app,dmg --no-sign

echo "=========================================================="
echo "  Build Completed Successfully!"
echo "=========================================================="
find apps/ambient/src-tauri/target/release/bundle -maxdepth 3 -type f \( -name "*.dmg" -o -name "Info.plist" \) -exec ls -lh {} +
