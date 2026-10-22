# CALIX: Calisthenics Skill Tree, Exercise Library & Training Platform

An RPG-style skill tree for calisthenics with a full training system: a rich **exercise library** with
offline **technique animations**, a **local player profile** with avatar and cosmetic unlocks, a
**progress dashboard** built from real stored data, **generated sound effects and background music**,
plus the original skill tree, workout builder, schedule, session tracking, ranks, XP and achievements.

Python 3 + PySide6 + SQLite. **Completely offline** – no account, no email, no network call, no
external assets. Every avatar, every animation, every font and every sound is produced by the app
itself.

---

## Rychlé spuštění (CachyOS / Arch / Linux)

```bash
# 1. systémový Python
sudo pacman -S --needed python python-pip

# 2. aplikace
cd ~/projects/python/calix4
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. spuštění
python main.py
```

Volitelné: vytvoření systémové instalace do `~/.local/bin` viz sekce *Spuštění bez konzoly*.

Zvuky i hudba se generují přímo v aplikaci (nic se nestahuje). Hudbu a hlasitosti změníš v
**Settings → Sound & Music**, klávesa **Ctrl+M** ztlumí nebo vrátí všechen zvuk.

**Požadavky:** Python 3.10+ (doporučeno 3.12+), PySide6 6.5+ včetně Qt Multimedia (standardní `pip install PySide6` ho obsahuje), ~200 MB místa. Bez internetu po instalaci.

---

## Install & run

### Linux (CachyOS / Arch / Fedora / Debian)

```bash
# CachyOS / Arch
sudo pacman -S --needed python python-pip
# Fedora: sudo dnf install python3 python3-pip
# Debian/Ubuntu: sudo apt install python3 python3-venv python3-pip

cd calix4
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

`requirements.txt` contains a single dependency:

```
PySide6>=6.5
```

If your distribution splits PySide6 into smaller packages, you need both the widgets and the
multimedia part (`pyside6-essentials` + `pyside6-addons` on Arch, `python3-pyside6.qtwidgets` +
`python3-pyside6.qtmultimedia` on Debian). The standard `pip install PySide6` wheel already contains
everything. If Qt Multimedia is missing, the app simply runs without sound – nothing else changes.

### Windows

```powershell
cd calix4
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Running without a console (Linux)

```bash
mkdir -p ~/.local/bin
cat > ~/.local/bin/calix <<'EOF'
#!/usr/bin/env bash
cd "$HOME/projects/python/calix4"   # change to your folder
exec "$HOME/projects/python/calix4/.venv/bin/python" main.py "$@"
EOF
chmod +x ~/.local/bin/calix
```

Then run `calix` from anywhere (add `~/.local/bin` to your `PATH`).

### Tests

```bash
python test_logic.py      # 39 headless tests, no GUI needed
```

---

## Where the data lives

| What | Where |
|---|---|
| Database | `~/.calisthenics_skill_tree/progress.db` |
| Override the folder | `export SKILLTREE_DATA=/path/to/folder` |
| Automatic backups | `progress.db.bak-v<N>` next to the database, written before every migration |
| Generated audio cache | `<data>/audio/` (`sfx-*.wav`, `music-*.wav`, a few MB) – safe to delete, rebuilt on demand |
| Animations, avatars, fonts, sounds | produced by the source code, nothing is downloaded |

The database is created on the first launch and migrated automatically. Migrations never delete
existing data – they only add tables and columns (see *Database & migrations*).

---

## What's new in this version

### 1. Exercise library with 89 exercises in 8 categories

| Category | Colour | Content |
|---|---|---|
| **Push** | red | push-ups, dips, handstand push-ups |
| **Pull** | blue | rows, pull-ups, muscle-up transitions |
| **Core** | yellow | planks, leg raises, L-sit, dragon flag |
| **Legs** | orange | squats, lunges, pistols, nordic curls |
| **Static holds** | green | planks, levers, flags, wall sits |
| **Handstand & balance** | cyan | handstands, crow pose, skin the cat |
| **Skill progressions** | violet | front/back lever, planche, human flag |
| **Explosive movements** | pink | jump squats, box jumps, burpees, clap push-ups |

Every exercise carries full metadata: **name, difficulty, main muscle groups, step-by-step
technique, recommended sets × reps-or-hold, recommended rest, common mistakes, training tips,
easier variants, harder variants, prerequisites and related exercises.** The data lives in
`exercise_details_data.py` and is mirrored into the `exercise_details` table on every start.

**Library page** (2nd tab in the top navigation):

* full-text search over name, instructions and muscle groups,
* filter by category (colour chips), difficulty, muscle group,
* *Favourites only* toggle,
* detail panel with technique, prescription, muscles, mistakes, tips and clickable progressions,
* an embedded **animation player** with play/pause, restart, speed and a phase list,
* **★ Favourite** and **Add to workout →** buttons.

### 2. Offline 2D technique animations

`animations.py` contains a small forward-kinematic skeleton (13 joints, 2-bone IK) and **74
animation clips** that are drawn with `QPainter` – no images, no video, no API, no network.

* Every one of the 89 exercises has an animation – 74 distinct clips, variations of the same
  movement share a clip (a generic fallback is used for custom exercises you create yourself).
* Every clip shows the **start position and the end position** and interpolates smoothly
  (eased) between the keyframes.
* The player can be **paused, restarted, slowed down (0.25× – 2×)** and clicked through the
  **phase list** (each phase has a title and a technique note).
* Complex skills have a **phase breakdown**: *muscle-up* (hang → pull → transition → lockout →
  lower), *front lever* (tuck → advanced tuck → straddle → full) and *planche* (lean → tuck →
  advanced tuck → straddle → full), plus the handstand, dragon flag and human flag lines.
* A geometry validator checks every clip (bone lengths, joints inside the canvas):
  **0 of 74 clips have any issue.**

### 3. Local player profile

* **First run** shows a full-screen welcome dialog: pick one of **10 fighters** and type your
  name, then *Enter the arena* → the dashboard.
* The profile is stored in the `profiles` table (id 1) – the schema is already built for several
  local profiles, the app currently uses one. **No email, no password, no registration.**
* The profile is loaded automatically on every start; the welcome screen only appears once.
* Everything is editable later in **Profile → Overview**: name, avatar (10 presets) and the
  accent colour (8 palettes). Changing the name or the avatar never touches your history,
  workouts, records or XP.

### 4. Profile page

Four tabs:

| Tab | Content |
|---|---|
| **Overview** | big avatar with the equipped cosmetics, name (editable), level, title, total XP, achievements, workouts, personal records, ranks, completed skills, and the list of your unlocked achievements |
| **Progress** | the progress dashboard (see below) |
| **Cosmetics** | auras, frames, outfits and titles – locked ones show the exact unlock condition, unlocked ones can be equipped |
| **Ranks & achievements** | the best rank per group, and the full rank list with goals |

### 5. Progress dashboard (real data only)

Inside the profile page (tab *Progress*), built from real stored data:

* **level and XP**, with a progress bar towards the next level and the next title,
* tiles for total XP, workouts, achievements, ranked exercises, personal records and skills,
* **performance over time**: reps, hold seconds and workouts per calendar week (last 12 weeks),
* **current performance vs. personal record** side by side – *now* is the most recent confirmed
  value, *PR* is the best value that was ever recorded for that exercise (a later, weaker set
  never overwrites it),
* **recent milestones** from the XP ledger,
* **newly unlocked skills** from the skill tree.

Nothing is estimated and nothing is faked: every number is read from the database.

### 6. Cosmetics (cosmetic only)

Auras, frames, outfits and titles are unlocked by **reaching a level** or by **unlocking an
achievement** – and they change nothing but your appearance. No stat, no rank, no XP bonus.

### 7. New achievements

Eleven new achievements watch new real metrics: *exercises trained* (1/10/25/50), *categories
trained* (2/4/6/8) and the *longest single hold* (60/180/300 s). They only unlock from
**confirmed** performances, so ticking a set in a fake workout never pays anything.

### 8. Sound effects and background music

`audio.py` synthesizes everything in pure Python on first use and caches it as small WAV files in
`<data>/audio/` – no audio files ship with the app and nothing is ever downloaded.

* **Button pop** – every button (navigation, cards, toggles) plays a short pitch-dropping pop;
  disabled buttons and the *Test* button in Settings stay quiet.
* **Event sounds** – welcome confirmation, adding an exercise to a workout (*toggle*), XP gained
  (*success*), achievements (*achievement*) and level-ups (*levelup*).
* **Four selectable music tracks**, generated as seamless loops (note tails wrap around, so there
  is no click at the seam):

  | Track | Mood |
  |---|---|
  | **Temple Bells** | calm pentatonic bells over a slow drone (default) |
  | **Iron Forge** | driving minor arpeggio for heavy sets |
  | **Void Drone** | dark, almost static ambient pad |
  | **Dawn Run** | bright major arpeggio, energetic |
  | *No music* | silence |

* **Settings → Sound & Music**: master switch for effects, effect volume, music on/off, track
  picker and music volume – all applied live and saved immediately. A *Test* button plays the pop.
* **Ctrl+M** (View menu → *Mute all sound*) mutes or restores everything at once.
* Playback uses `QSoundEffect` for the effects and a looping `QMediaPlayer` for the music. When
  Qt Multimedia or the sound card is unavailable the engine degrades silently and the app keeps
  working; the Settings card explains why it is quiet.

---

## Sections (top navigation, Alt+1…11)

| # | Section | What it does |
|---|---|---|
| 1 | **Skill Tree** | The original 67-skill tree: pan/zoom, search & filters, prerequisites, progress, records |
| 2 | **Library** | 89 exercises, 8 categories, full metadata, offline animation, favourites, one-click add to a workout |
| 3 | **Workout Builder** | Build, edit, duplicate and delete workouts; search & filter by category/difficulty/favourites; muscle groups; *Animation…* and *In library* buttons; log a performance; custom exercises |
| 4 | **Schedule** | Week and month calendar, one-time workouts or rest days, weekly routine, move/edit/remove |
| 5 | **Active Workout** | Guided session: set-by-set tracking, editable reps/holds, rest timer, hold stopwatch, pause/resume, completion summary with new personal records |
| 6 | **History** | Every finished session with set-level detail plus real statistics, weekly chart and consistency heatmap |
| 7 | **Dashboard** | Today, upcoming sessions, training stats, consistency and skill-tree progress |
| 8 | **Ranks** | Rank of every exercise and progression line, filters, history, goals |
| 9 | **Achievements** | Level and XP, achievement gallery with filters, XP history |
| 10 | **Profile** | Local profile: avatar, name, level, XP, achievements, ranks, cosmetics and the progress dashboard |
| 11 | **Settings** | Appearance, behaviour, sound effects and music, applied live |

---

## Database & migrations

`PRAGMA user_version` tracks the schema version (currently **5**).

| Version | What it adds |
|---|---|
| 1 | skill tree (`progress`, `records`), `exercises`, `workouts`, `workout_exercises` |
| 2 | `sessions`, `session_sets`, `schedule_entries`, `schedule_skips` |
| 3 | `performances`, `settings`, the `confirmed` flag on `session_sets` |
| 4 | `xp_events`, `xp_state`, `achievements` |
| 5 | `exercise_details`, `profiles`, `favorites`, `profile_cosmetics`, the `anim` column on `exercises` |

**Every migration is additive.** No table is dropped, no row is deleted and no column is
redefined, so all your workouts, sessions, records, ranks and XP survive the upgrade. Before a
migration runs, the database file is copied to `progress.db.bak-v<N>`.

Custom exercises (the ones you create yourself) are never touched by the built-in sync.

---

## Project layout

```
main.py                 window, navigation, menus, wiring
--- skill tree ---
skills_data.py  graph.py  tree_view.py  panels.py
--- exercise library & animations ---
exercises_data.py        89 built-in exercises (8 categories)
exercise_details_data.py full metadata: muscles, technique, mistakes, tips, progressions
animations.py            74 offline 2D clips, skeleton + IK, the Qt player
library_page.py          the library page (search, filters, detail, animation, favourites)
--- profile & cosmetics ---
avatar_data.py           10 fighters, 8 palettes, 11 cosmetics with unlock rules
avatars.py               the painted avatar widget (QPainter, no images)
profile_repo.py          local profile, favourites and cosmetic unlocks (no Qt)
profile_page.py          profile page: overview, progress, cosmetics, ranks
welcome_page.py          first-run welcome screen
progress_charts.py       the progress dashboard widgets and data helpers
--- training logic (no Qt, unit-tested) ---
database.py              SQLite store + versioned migrations
workouts.py              exercises, details, custom workouts
sessions.py              sessions and sets
scheduling.py  schedule_page.py
ranks.py  rank_repo.py  rank_widgets.py  ranks_page.py
progression.py  xp_engine.py  xp_widgets.py  achievements.py  achievements_page.py
stats.py  history_page.py  active_page.py  builder_page.py  dashboard_page.py
settings.py  settings_page.py  theme.py  ui_common.py
audio.py                 synthesized sound effects + 4 music loops + the Qt audio engine
test_logic.py            headless tests:  python test_logic.py
```

Pure logic (no Qt) lives in `database.py`, `workouts.py`, `sessions.py`, `ranks.py`, `profile_repo.py`,
`progression.py`, `xp_engine.py`, `achievements.py` and `stats.py` – that is what makes the headless
tests possible.

---

## Extending

* **New exercise**: add a `_e(...)` line in `exercises_data.py` and its metadata in
  `exercise_details_data.py` (both are synced into the database on startup).
* **New animation**: add a clip in `animations.py` (`_add(key, title, frames, labels, notes, ...)`)
  and reference its key in the exercise's `anim` field.
* **New skill**: add a `_s(...)` line in `skills_data.py`.
* **New sound effect**: add a builder to `SFX_BUILDERS` in `audio.py`; **new music track**: add an
  entry to `TRACKS` (and its id to `settings.CHOICES["music_track"]`), then bump `CACHE_VERSION` so
  the cached WAVs are regenerated.
* **New schema change**: append a function to `MIGRATIONS` in `database.py`.

---

## Privacy

The app never opens a network connection. Everything – your profile, your workouts, your records –
stays in `~/.calisthenics_skill_tree/progress.db` on your computer. Delete that file and everything
is gone; back it up and nothing is lost.
