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
| XP / achievements | Same rules as Python: qualifying workouts (2 min, half the sets, 3 per day), sets, PRs, ranks, skill unlocks/completions, achievements; idempotent ledger keyed by activity |
| Settings | Accent, background preset, corner style, font size, tree grid/effects, data folder, XP recompute |

## Layout

```
src/main.rs          entry point + window
src/app.rs           shell: navigation, status bar, shared state
src/data.rs          embedded catalogue (skills, exercises, details, achievements, ranks, progression)
src/logic.rs         pure logic: graph layout, skill states, level curve, rank ladders
src/db.rs            SQLite schema (v6, Python-compatible), store, stats, XP + achievements, tests
src/theme.rs         palette, egui style, shared widgets (cards, tiles, chips, bars)
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

Three tests cover the store: schema + seeding + run logging/pace, a full session
lifecycle (start → tick sets → finish → XP), and the graph layout, rank ladders
and level curve.
