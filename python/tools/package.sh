#!/usr/bin/env bash
# Builds the distributables for the Python edition:
#   dist/CALIX-1.1.0-x86_64.AppImage      portable Linux build
#   dist/CALIX/                           PyInstaller folder build (run dist/CALIX/CALIX)
#   dist/CALIX-1.1.0-windows-x86_64.exe   Windows build, made with wine (see PACKAGING.md)
#
# Needs: python3 with PySide6 installed, ImageMagick (`magick`), pyinstaller
# (installed into a throw-away venv below), mksquashfs for the AppImage.
set -euo pipefail
cd "$(dirname "$0")/.."
NAME="CALIX"
VERSION="1.1.0"
VENV="${PYI_VENV:-/tmp/calix-pyi-venv}"

if [ ! -x "$VENV/bin/pyinstaller" ]; then
    echo "==> installing pyinstaller into $VENV"
    python3 -m venv --system-site-packages "$VENV"
    "$VENV/bin/pip" install -q --upgrade pip pyinstaller
fi

echo "==> PyInstaller (Linux)"
"$VENV/bin/pyinstaller" --noconfirm --clean --windowed --onedir \
    --name "$NAME" --distpath dist --workpath build --specpath build main.py

echo "==> AppImage"
if [ ! -x dist/runtime-x86_64 ]; then
    curl -sL -o dist/runtime-x86_64 \
        https://github.com/AppImage/AppImageKit/releases/download/continuous/runtime-x86_64
    chmod +x dist/runtime-x86_64
fi

APPDIR="dist/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib/$NAME" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/512x512/apps"
cp -a "dist/$NAME/." "$APPDIR/usr/lib/$NAME/"

magick -size 512x512 xc:none \
    -fill '#0b1017' -draw "roundrectangle 0,0 511,511 110,110" \
    -fill '#1b2430' -draw "roundrectangle 40,40 471,471 84,84" \
    -stroke '#4dabf7' -strokewidth 14 -fill none -draw "circle 256,256 256,96" \
    -stroke none -fill '#e9f2ff' -pointsize 210 -gravity center \
    -font "DejaVu-Sans-Bold" -annotate +0+6 "C" \
    "$APPDIR/calix.png"
cp "$APPDIR/calix.png" "$APPDIR/.DirIcon"
cp "$APPDIR/calix.png" "$APPDIR/usr/share/icons/hicolor/512x512/apps/"

cat > "$APPDIR/calix.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$NAME
Comment=Calisthenics progression trainer
Exec=calix
Icon=calix
Categories=Health;Sports;Education;
Terminal=false
StartupWMClass=$NAME
EOF
cp "$APPDIR/calix.desktop" "$APPDIR/usr/share/applications/"

cat > "$APPDIR/AppRun" <<EOF
#!/bin/sh
HERE="\$(dirname "\$(readlink -f "\$0")")"
exec "\$HERE/usr/lib/$NAME/$NAME" "\$@"
EOF
chmod +x "$APPDIR/AppRun"

rm -f dist/appimage.squashfs "dist/$NAME-$VERSION-x86_64.AppImage"
mksquashfs "$APPDIR" dist/appimage.squashfs \
    -root-owned -noappend -comp xz -b 131072 -no-progress -quiet
cat dist/runtime-x86_64 dist/appimage.squashfs \
    > "dist/$NAME-$VERSION-x86_64.AppImage"
chmod +x "dist/$NAME-$VERSION-x86_64.AppImage"
rm -f dist/appimage.squashfs

echo "==> done"
ls -lh "dist/$NAME-$VERSION-x86_64.AppImage" "dist/$NAME-$VERSION-windows-x86_64.exe" 2>/dev/null || true
