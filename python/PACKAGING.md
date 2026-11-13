# Building CALIX (Python) as an AppImage / Windows exe

`./tools/package.sh` builds the Linux side:

* `dist/CALIX/` – PyInstaller folder build, start it with `dist/CALIX/CALIX`
* `dist/CALIX-1.1.0-x86_64.AppImage` – single-file portable Linux build

Needs `python3` with **PySide6** already installed (the script borrows it via a
venv with `--system-site-packages`), plus `pyinstaller`, `mksquashfs` and
ImageMagick. The AppImage is a type-2 runtime followed by an xz squashfs of the
AppDir — no FUSE-2 needed; if mounting fails, run
`APPIMAGE_EXTRACT_AND_RUN=1 ./CALIX-*.AppImage`.

## Windows exe

PyInstaller cannot cross-compile, so the exe is built by running Windows Python
inside wine:

```bash
# once: Windows Python 3.12 + build tools inside wine
cd /tmp && curl -sLO https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe
wine python-3.12.8-amd64.exe /quiet InstallAllUsers=0 TargetDir=C:\\Python312 \
     PrependPath=0 Shortcuts=0 Include_test=0 Include_launcher=0
wine C:/Python312/python.exe -m pip install pyside6 pyinstaller
```

Then, from a copy of `python/` (paths without spaces are safest):

```bash
cp *.py /tmp/calix-win-src/ && cd /tmp/calix-win-src
wine C:/Python312/python.exe -m PyInstaller --noconfirm --clean --windowed \
     --onefile --name CALIX --distpath Z:/tmp/calix-win-src/dist \
     --workpath Z:/tmp/calix-win-src/build --specpath Z:/tmp/calix-win-src/build main.py
cp dist/CALIX.exe "/path/to/python/dist/CALIX-1.1.0-windows-x86_64.exe"
```

The result is a single self-contained `CALIX.exe` (~55 MB) with Qt inside.

## Notes

* Data, settings and generated audio still live in `~/.calisthenics_skill_tree`,
  so the packaged build shares its progress with the source checkout.
* `main.py` knows when it is frozen (`sys.frozen`) so switching profile slots
  re-launches the executable instead of passing a script path.
* The app builds its own audio/pattern assets at runtime; nothing is bundled.
