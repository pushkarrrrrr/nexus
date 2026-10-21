#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "=========================================================="
echo "  NEXUS — Building Standalone Engine Sidecar (PyInstaller)"
echo "=========================================================="

if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

# Ensure pyinstaller is available
if ! command -v pyinstaller &> /dev/null; then
  echo "--> Installing PyInstaller..."
  pip install pyinstaller
fi

TARGET_TRIPLE="$(rustc -vV | sed -n 's|host: ||p')"
if [ -z "$TARGET_TRIPLE" ]; then
  TARGET_TRIPLE="aarch64-apple-darwin"
fi

OUTPUT_NAME="nexus-engine-${TARGET_TRIPLE}"
DIST_DIR="apps/ambient/src-tauri/binaries"
BUILD_DIR="build/pyinstaller"

mkdir -p "$DIST_DIR"
mkdir -p "$BUILD_DIR"

echo "--> Target Triple: $TARGET_TRIPLE"
echo "--> Output Binary: $DIST_DIR/$OUTPUT_NAME"

PYTHONPATH=. pyinstaller \
  --noconfirm \
  --clean \
  --onefile \
  --name "$OUTPUT_NAME" \
  --distpath "$DIST_DIR" \
  --workpath "$BUILD_DIR" \
  --paths . \
  --collect-all packages.config \
  --collect-all packages.shared \
  --collect-all packages.types \
  --collect-all services.api \
  --collect-all pydantic \
  --collect-all pydantic_settings \
  --collect-all sqlalchemy \
  --collect-all aiosqlite \
  --collect-all uvicorn \
  --collect-all fastapi \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols \
  --hidden-import uvicorn.protocols.http \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan \
  --hidden-import uvicorn.lifespan.on \
  --hidden-import sqlalchemy.dialects.sqlite \
  --hidden-import sqlalchemy.dialects.sqlite.aiosqlite \
  --hidden-import aiosqlite \
  --hidden-import greenlet \
  --hidden-import anyio \
  --hidden-import anyio._backends._asyncio \
  services/api/nexus_api/cli_engine.py

chmod +x "$DIST_DIR/$OUTPUT_NAME"

echo "==> Build Completed Successfully!"
ls -lh "$DIST_DIR/$OUTPUT_NAME"
