#!/bin/sh
# Adds MouseMe to the applications menu, running it from this folder
set -e

dir="$(cd "$(dirname "$0")" && pwd)"
target="${XDG_DATA_HOME:-$HOME/.local/share}/applications/mouseme.desktop"

mkdir -p "$(dirname "$target")"
cat > "$target" <<EOF
[Desktop Entry]
Type=Application
Name=MouseMe
Comment=Record and replay mouse clicks
Exec=python3 -m mouseme
Path=$dir
Icon=$dir/mouseme/icon.png
Terminal=false
Categories=Utility;
StartupWMClass=MouseMe
EOF

echo "Installed $target"
