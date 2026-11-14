# CALIX 1.1.23

Offline kalistenický trenér: strom dovedností, knihovna cviků, tréninky, plán,
historie, statistiky, hodnosti, úspěchy a **Kouč** — chat, který rozumí psanému
zápisu tréninku a odpovídá na otázky z tvého deníku.

Všechno běží lokálně. Žádný server, cloud, přihlášení ani síťové volání.
Kouč není jazykový model: je to deterministický rule engine nad katalogem cviků
a tvými daty, takže funguje i bez internetu a odpovídá pořád stejně.

V této složce jsou jen nejnovější buildy; staré verze jsou v `~/calix 1.1.2 archiv/`.
Předchozí vzhled zůstal nedotčený v `~/calix 1.1.22/`.

---

## Co tu je

| Cesta | Co to je |
| --- | --- |
| `python/` | **Python desktop** (PySide6) — hlavní edice |
| `rust/` | **Rust desktop** (egui) — port Pythonu, stejná databáze |

V této verzi jsou jen obě desktopové edice. Web (`calix.html`) a Android
(`calix.apk`) se v 1.1.23 nezměnily, takže zůstaly ve starší složce:
`~/calix 1.1.2 archiv/verze-1.1.23/`. Jejich zdrojáky jsou
`~/projects/android/calix/` — `web/` (HTML build) a `app/` (Compose aplikace).

Data aplikací nejsou v této složce a přesouvat se nedají:
`~/.calisthenics_skill_tree/` obsahuje `active_profile.json` a `profile-1..3.db`
(společné pro Python i Rust). HTML si drží stav v `localStorage`, Android
v interní databázi zařízení.

---

## Co je nového v 1.1.23

**Vzhled.** Nová paleta a hierarchie pro obě desktopové edice (Python i Rust):
- hlubší „inkoustové“ pozadí (`#080b11`) s jemně odlišenou lištou a stavovým řádkem,
- navigace jako pilulky — aktivní záložka má akcentový podklad a rámeček místo podtržení,
- karty se zaoblením 16 px a jemnějším okrajem, výraznější sekční popisky s prostrkáním,
- hlavní tlačítka mají akcentový gradient, vedlejší tlumený „ghost“ styl,
- větší vstupy s focus rámem v akcentu, tenčí scrollbary, jemnější progress bary.

**Kouč.** Rozumí víc česky, včetně zdvořilostní konverzace:
- pozdravy: `ahoj`, `ahojky`, `čau`, `čauky`, `čus`, `zdar`, `servus`, `zdravím`,
  `dobré ráno`, `dobrý den`, `dobrý večer`, `hej`,
- `jak se máš`, `jak ti je`, `jak to jde`, `jak se vede`, `co děláš`, `máš se?`,
  `jsi v pohodě` → odpoví podle skutečného stavu (trénink dnes, série dní),
- kombinace typu `ahoj jak se mas` — pozdrav se odřízne a odpoví se na otázku,
- pozdrav je podle denní doby (`Good morning` / `Hey` / `Good evening`),
- `děkuju`, `dík`, `díky moc`, `měj se`, `dobrou noc`, `papa`,
- `kdo jsi`, `jak se jmenuješ`, `jsi robot?` → vysvětlí, že je lokální rule engine.

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
cd python && bash tools/package.sh   # → python/dist (AppImage + složka + .exe přes wine)
cd rust   && bash tools/package.sh   # → rust/dist (AppImage + .exe)
```

Windows .exe pro Python se staví PyInstallerem ve wine (Windows Python 3.12),
postup je v `python/PACKAGING.md`.

---

## Testy

```bash
cd python && python3 test_assistant.py && python3 test_logic.py && python3 test_profiles.py
cd rust && cargo test
```

Kouč má vlastní testy v obou edicích: `python/test_assistant.py` (25 testů)
a `assistant::tests` v Rustu (8 testů).

---

## Poznámky

- Python i Rust používají stejné SQLite schéma, takže oba umí otevřít stejný
  `profile-N.db`; migrace sloupců řeší `ensure_column`.
- Kouč záměrně není LLM — žádná síť, žádné klíče, žádné halucinace.
