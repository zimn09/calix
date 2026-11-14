# CALIX – Rust desktop edition

A port of the CALIX 1.1 PC app (Python + PySide6) to Rust, built with
[egui/eframe](https://github.com/emilk/egui) and SQLite (rusqlite, bundled).

The Python edition in `../calix 1.1/` is untouched; this is a separate project.

## Run it

```bash
cargo run --release          # first build compiles egui + bundled SQLite
```

Nothing else is needed: the GUI, the data and the database are all local.

* Data lives in `~/.calisthenics_skill_tree/progress.db` (override the folder with
  `SKILLTREE_DATA=/some/dir`). It is the **same schema as the Python app**, so both
  editions can open the same file.
* If the Python app's `active_profile.json` points at profile slot 2 or 3, the
  active `profile-N.db` is opened instead, so both apps show the same history.
* Older databases are upgraded on open: any column added since (for example
  `sessions.distance_m`) is patched in with `ALTER TABLE` before use.
* First launch seeds the built-in exercise library and the six example workouts
  (Push Day, Pull Day, Legs & Core, Cardio, Run, Skill Training).

## What the port does

| Area | State |
| --- | --- |
| Skill tree | Pan/zoom canvas, prerequisite edges, four states, hover/selection, tier pips, rank badges, per-category lanes, detail panel with steps, training, regressions, benchmark, record logging and status changes |
| Workouts | List, create, edit (name/note/style, sets, reps/hold, rest), delete, start; active session runner with per-set ticking, live clock, rest countdown, finish/discard |
| Exercise library | Search, category filter, full sheet (muscles, technique, mistakes, cues, prescription, easier/harder/related) |
| Running | Distance + time with live pace, average/best pace tiles, run history, delete; runs count as finishing sessions |
| History | Completed sessions and runs, set/reps/hold totals, weekly count, streak, delete |
| Dashboard | Level, XP curve, tiles, category progress, next unlocked skills, XP breakdown, personal records |
| Ranks | Per-exercise ladders and progression lines, best values, progress to the next rank |
| Achievements | Full catalogue with live progress, rarity colours and unlock dates |
| Coach | Local rule-based assistant (no model, no network): logs sets, holds and runs from plain text, answers totals/bests/streaks, suggests the next skill, explains catalogue entries, handles small talk (`hey`, `thanks`, `how are you`). Writes are previewed and need a Save. Understands English and Czech slang, typos and number words |
| XP / achievements | Same rules as Python: qualifying workouts (2 min, half the sets, 3 per day), sets, PRs, ranks, skill unlocks/completions, achievements; idempotent ledger keyed by activity |
| Settings | Accent, background preset, corner style, font size, tree grid/effects, data folder, XP recompute |

## Building the distributables

```bash
./tools/package.sh
```

writes into `dist/`:

| File | What it is |
| --- | --- |
| `CALIX-1.1.0-x86_64.AppImage` | portable Linux build (single file, `chmod +x` and run) |
| `calix-linux-x86_64` | the bare Linux executable |
| `CALIX-1.1.0-windows-x86_64.exe` | 64-bit Windows build, C runtime linked in statically (no VC++ redistributable needed) |

The AppImage is assembled from a type-2 runtime plus an xz squashfs of the
AppDir; the Windows build uses `cargo xwin` (install it once with
`cargo install cargo-xwin && rustup target add x86_64-pc-windows-msvc`).

The AppImage needs the usual desktop libraries present on any normal desktop
(GL, xkbcommon); no FUSE-2 is required for it to run on most systems, but if
mounting is unavailable use `APPIMAGE_EXTRACT_AND_RUN=1 ./CALIX-*.AppImage`.

## Layout

```
src/main.rs          entry point + window
src/app.rs           shell: navigation, status bar, shared state
src/data.rs          embedded catalogue (skills, exercises, details, achievements, ranks, progression)
src/logic.rs         pure logic: graph layout, skill states, level curve, rank ladders
src/db.rs            SQLite schema (v6, Python-compatible), store, stats, XP + achievements, tests
src/theme.rs         palette, egui style, shared widgets (cards, tiles, chips, bars)
src/assistant.rs     the coach: normaliser, vocabulary matching, intents, database actions, tests
src/pages/*.rs       one file per page
data/*.json          generated catalogue data (embedded with include_str!)
tools/export_data.py re-generates data/ from the Python modules
```

Regenerate the catalogue after changing the Python data:

```bash
python3 tools/export_data.py
```

## Not ported (yet)

The Python edition still has these; they are the natural next step:

* generated audio (button pops, event sounds, four music tracks)
* avatars, cosmetics and the profile identity (name, aura, frame, outfit, titles)
* weekly schedule planning and schedule adherence
* multiple local profiles (one database per profile)
* the animated 2D exercise figures (the Rust app shows text sheets instead)
* backup/restore, CSV/JSON export and the welcome tour

## Tests

```bash
cargo test
```

`cargo test` covers the coach (`assistant::tests::coach_understands_notes_and_questions`)
plus the store tests: schema + seeding + run logging/pace, a full session
lifecycle (start → tick sets → finish → XP), and the graph layout, rank ladders
and level curve.
