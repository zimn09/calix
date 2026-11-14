#!/usr/bin/env bash
# Builds the distributables:
#   dist/CALIX-1.1.0-x86_64.AppImage   portable Linux build (bundled executable)
#   dist/calix-linux-x86_64             bare Linux executable
#   dist/CALIX-1.1.0-windows-x86_64.exe Windows build (statically linked CRT)
#
# Linux needs: cargo, ImageMagick (`magick`), appimagetool (downloaded below).
# Windows needs: `cargo install cargo-xwin` and `rustup target add x86_64-pc-windows-msvc`.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="1.1.0"
DIST="dist"
APPID="calix"

mkdir -p "$DIST"

echo "==> Linux release build"
cargo build --release
cp target/release/calix "$DIST/calix-linux-x86_64"

echo "==> Windows release build"
if command -v cargo-xwin >/dev/null 2>&1; then
    RUSTFLAGS="-C target-feature=+crt-static" \
        cargo xwin build --release --target x86_64-pc-windows-msvc
    cp target/x86_64-pc-windows-msvc/release/calix.exe \
        "$DIST/CALIX-$VERSION-windows-x86_64.exe"
else
    echo "    skipped: cargo-xwin not installed"
fi

echo "==> AppImage"
# appimagetool's own AppImage is flaky here, so assemble the image directly:
# a type-2 runtime followed by a squashfs image of the AppDir.
if [ ! -x "$DIST/runtime-x86_64" ]; then
    curl -sL -o "$DIST/runtime-x86_64" \
        https://github.com/AppImage/AppImageKit/releases/download/continuous/runtime-x86_64
    chmod +x "$DIST/runtime-x86_64"
fi

APPDIR="$DIST/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/512x512/apps"
cp target/release/calix "$APPDIR/usr/bin/$APPID"
chmod +x "$APPDIR/usr/bin/$APPID"

magick -size 512x512 xc:none \
    -fill '#0b1017' -draw "roundrectangle 0,0 511,511 110,110" \
    -fill '#1b2430' -draw "roundrectangle 40,40 471,471 84,84" \
    -stroke '#4dabf7' -strokewidth 14 -fill none -draw "circle 256,256 256,96" \
    -stroke none -fill '#e9f2ff' -pointsize 210 -gravity center \
    -font "DejaVu-Sans-Bold" -annotate +0+6 "C" \
    "$APPDIR/$APPID.png"
cp "$APPDIR/$APPID.png" "$APPDIR/.DirIcon"
cp "$APPDIR/$APPID.png" "$APPDIR/usr/share/icons/hicolor/512x512/apps/"

cat > "$APPDIR/$APPID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=CALIX
Comment=Calisthenics progression trainer
Exec=$APPID
Icon=$APPID
Categories=Health;Sports;Education;
Terminal=false
StartupWMClass=calix
EOF
cp "$APPDIR/$APPID.desktop" "$APPDIR/usr/share/applications/"

cat > "$APPDIR/AppRun" <<EOF
#!/bin/sh
HERE="\$(dirname "\$(readlink -f "\$0")")"
exec "\$HERE/usr/bin/$APPID" "\$@"
EOF
chmod +x "$APPDIR/AppRun"

rm -f "$DIST/appimage.squashfs" "$DIST/CALIX-$VERSION-x86_64.AppImage"
# the runtime only understands xz/zlib squashfs, and 128 KiB blocks
mksquashfs "$APPDIR" "$DIST/appimage.squashfs" \
    -root-owned -noappend -comp xz -b 131072 -no-progress -quiet
cat "$DIST/runtime-x86_64" "$DIST/appimage.squashfs" \
    > "$DIST/CALIX-$VERSION-x86_64.AppImage"
chmod +x "$DIST/CALIX-$VERSION-x86_64.AppImage"
rm -f "$DIST/appimage.squashfs"

echo "==> done"
ls -la "$DIST"/*.AppImage "$DIST"/*.exe "$DIST"/calix-linux-x86_64
