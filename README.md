# CALIX 1.1.2

Offline kalistenický trenér: strom dovedností, knihovna cviků, tréninky, plán,
historie, statistiky, hodnosti, úspěchy a **Kouč** — chat, který rozumí psanému
zápisu tréninku a odpovídá na otázky z tvého deníku.

Všechno běží lokálně. Žádný server, cloud, přihlášení ani síťové volání.
Kouč není jazykový model: je to deterministický rule engine nad katalogem cviků
a tvými daty, takže funguje i bez internetu a odpovídá pořád stejně.

V této složce jsou jen nejnovější buildy; staré verze jsou v `~/calix 1.1.2 archiv/`.

---

## Co tu je

| Cesta | Co to je |
| --- | --- |
| `python/` | **Python desktop** (PySide6) — hlavní edice |
| `rust/` | **Rust desktop** (egui) — port Pythonu, stejná databáze |
| `calix.html` | **Web / HTML edice** — celá aplikace v jednom souboru |
| `calix.apk` | **Android** (Kotlin + Compose), podepsaný release |

Zdrojáky webu a Androidu jsou mimo tuto složku:
`~/projects/android/calix/` — `web/` (HTML build) a `app/` (Compose aplikace).

Data aplikací nejsou v této složce a přesouvat se nedají:
`~/.calisthenics_skill_tree/` obsahuje `active_profile.json` a `profile-1..3.db`
(společné pro Python i Rust). HTML si drží stav v `localStorage`, Android
v interní databázi zařízení.

---

## Kouč

Ikona muže, bubliny, chipy s častými příkazy a potvrzovací kartička před zápisem.
Rozumí (česky i anglicky):

- zápis sérií — `3x12 kliky`, `plank 1:30`, `běh 5 km za 26:30`
- navázání — `a ještě 10`, `ne, 15` (oprava posledního zápisu), `undo`
- čísla — `kolik kliků tento týden?`, `můj rekord v shybech`, `jak jsem na tom oproti minulému týdnu?`
- úroveň a plán — `kolik XP do další úrovně`, `co mám dnes trénovat?`, `sestav mi pull trénink`

Zapsané série jdou do normálního dokončeného tréninku (`Coach log` v Pythonu
a Rustu, `Kouč` v Androidu), takže je vidí historie, statistiky, XP, hodnosti
i úspěchy. Web je zapisuje do tréninku `Coach log`.

---

## Spuštění

**Python desktop** (vyžaduje PySide6):

```bash
cd python
python3 main.py
```

**Rust desktop:**

```bash
cd rust
cargo run --release
```

**Web:** otevři `calix.html` v prohlížeči (funguje i z `file://`).

**Android:** nainstaluj `calix.apk` (Android 8+).

---

## Hotové buildy (dist/)

| Soubor | Co to je |
| --- | --- |
| `python/dist/CALIX-1.1.0-x86_64.AppImage` | Python edice, přenosný Linux build (~110 MB) |
| `python/dist/CALIX-1.1.0-windows-x86_64.exe` | Python edice pro Windows, onefile (~55 MB) |
| `python/dist/CALIX/` | Python edice jako složka (`CALIX/CALIX`) |
| `rust/dist/CALIX-1.1.0-x86_64.AppImage` | Rust edice, přenosný Linux build (~6 MB) |
| `rust/dist/CALIX-1.1.0-windows-x86_64.exe` | Rust edice pro Windows, statický CRT (~8 MB) |
| `rust/dist/calix-linux-x86_64` | Rust edice bez AppImage |

AppImage je type-2 runtime + xz squashfs, takže nepotřebuje FUSE 2; když přesto
nejde spustit, použij `APPIMAGE_EXTRACT_AND_RUN=1 ./CALIX-*.AppImage`.

## Nové buildy

```bash
python3 ~/projects/android/calix/web/build.py    # → tato složka/calix.html
cd python && bash tools/package.sh               # → python/dist (AppImage + složka)
cd rust   && bash tools/package.sh               # → rust/dist (AppImage + .exe)
cd ~/projects/android/calix
JAVA_HOME=~/tools/jdk-21 ./gradlew :app:assembleRelease
# → app/build/outputs/apk/release/app-release.apk, zkopíruj sem jako calix.apk
```

Release build používá `keystore/calix-release.jks` z repozitáře Androidu a
potřebuje JDK 21 (`~/tools/jdk-21`); se systémovým JDK 27 Gradle neproběhne.

---

## Testy

```bash
cd python && python3 test_assistant.py && python3 test_logic.py && python3 test_profiles.py
cd rust && cargo test
cd ~/projects/android/calix && JAVA_HOME=~/tools/jdk-21 ./gradlew :app:testDebugUnitTest
```

Kouč má vlastní testy ve všech třech kódových základnách:
`python/test_assistant.py`, `assistant::tests` v Rustu a `CoachTest.kt` v Androidu.

---

## Poznámky

- Python i Rust používají stejné SQLite schéma, takže oba umí otevřít stejný
  `profile-N.db`; migrace sloupců řeší `ensure_column`.
- Kouč záměrně není LLM — žádná síť, žádné klíče, žádné halucinace.
