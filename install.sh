#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="$HOME/.local/share/applications"
BIN_DIR="$HOME/.local/bin"

chmod +x "$APP_DIR/kyobo_viewer.py"
mkdir -p "$DESKTOP_DIR" "$BIN_DIR"

ln -sf "$APP_DIR/kyobo_viewer.py" "$BIN_DIR/kyobo-webviewer"

cat > "$DESKTOP_DIR/kyobo-webviewer.desktop" <<EOF
[Desktop Entry]
Name=교보 eBook 웹뷰어
Comment=교보문고 eBook 및 전자도서관 리눅스 전용 웹뷰어
Exec=/usr/bin/env python3 "$APP_DIR/kyobo_viewer.py" %u
Icon=$APP_DIR/icon.svg
Terminal=false
Type=Application
Categories=Office;Education;Viewer;
StartupWMClass=kyobo_viewer.py
EOF

chmod +x "$DESKTOP_DIR/kyobo-webviewer.desktop"
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo "설치 완료:"
echo "  - 실행 명령: kyobo-webviewer"
echo "  - 데스크톱 앱 등록: $DESKTOP_DIR/kyobo-webviewer.desktop"
