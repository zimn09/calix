"""Achievement catalogue (pure data).

Each achievement watches one *metric* computed from real app data (see xp_engine.metrics)
and unlocks when metric >= target. Metric names:
  best:<exercise id>   best recorded set of an exercise      workouts / scheduled   qualifying workouts
  sets / reps / hold_seconds   lifetime totals                week_best / month_best  most workouts in a week / month
  streak_days          longest run of training days          week_streak             longest run of weeks with 3+ workouts
  skills_done / skills_tier:<n> / skills_cat:<cat> / skill:<id>   skill-tree progress
  prs / ranked / ranks_ge:<n>   records and ranks            level / achievements    meta
  exercises_trained / categories_trained / max_hold / favorites   exercise library
"""
from dataclasses import dataclass

from skills_data import CATEGORIES, SKILLS

CATEGORY_LABELS = {
    "strength": "Strength", "static": "Static holds", "skills": "Skill tree", "training": "Training",
    "records": "Personal records", "consistency": "Consistency", "progression": "Level & collection",
    "library": "Exercise library",
}
RARITIES = {            # key: (label, colour, order)
    "common": ("Common", "#9aa4b2", 0),
    "rare": ("Rare", "#4dabf7", 1),
    "epic": ("Epic", "#b197fc", 2),
    "legendary": ("Legendary", "#ffd43b", 3),
}


@dataclass(frozen=True)
class Achievement:
    id: str
    name: str
    description: str
    category: str
    rarity: str
    xp: int
    metric: str
    target: float
    icon: str
    unit: str = ""
    exercises: tuple = ()      # library exercises this relates to
    skills: tuple = ()         # skill-tree skills this relates to


ACHIEVEMENTS = []


def _a(id, name, desc, cat, rarity, xp, metric, target, icon, unit="", ex=(), sk=()):
    ACHIEVEMENTS.append(Achievement(id, name, desc, cat, rarity, xp, metric, target, icon, unit, tuple(ex), tuple(sk)))


def _best(id, name, ex, target, cat, rarity, xp, icon, unit="reps", what=None):
    what = what or f"Record {target:g} {unit} of {{ex}} in a single set."
    _a(id, name, what.replace("{ex}", ex.replace("_", " ")), cat, rarity, xp, f"best:{ex}", target, icon, unit, ex=(ex,))


# ------------------------------------------------------------------ strength
_a("pullup_1", "First Pull-Up", "Do your first strict pull-up.", "strength", "common", 15,
   "best:pullup", 1, "▲", "reps", ex=("pullup",))
_a("pushup_1", "First Push-Up", "Do your first push-up.", "strength", "common", 10,
   "best:pushup", 1, "◆", "reps", ex=("pushup",))
for n, nm, r, xp in ((5, "First Pull-Ups", "common", 20), (10, "Double Digits", "common", 40),
                     (15, "Bar Crusher", "rare", 90), (20, "Iron Grip", "epic", 180),
                     (25, "Pull-Up Legend", "legendary", 400)):
    _a(f"pullup_{n}", nm, f"Do {n} strict pull-ups in one set.", "strength", r, xp, "best:pullup", n, "▲", "reps", ex=("pullup",))
for n, nm, r, xp in ((20, "Push-Up Starter", "common", 20), (40, "Push-Up Pro", "rare", 70), (60, "Push-Up Machine", "epic", 160)):
    _a(f"pushup_{n}", nm, f"Do {n} push-ups in one set.", "strength", r, xp, "best:pushup", n, "◆", "reps", ex=("pushup",))
for n, nm, r, xp in ((10, "Dip Beginner", "common", 30), (20, "Dip Specialist", "rare", 80), (30, "Dip Titan", "epic", 170)):
    _a(f"dip_{n}", nm, f"Do {n} parallel bar dips in one set.", "strength", r, xp, "best:dip", n, "▼", "reps", ex=("dip",))
_a("pistol_1", "Pistol Whisperer", "Do a pistol squat.", "strength", "rare", 80, "best:pistol_squat", 1, "♞", "reps", ex=("pistol_squat",))
_a("pistol_5", "Single-Leg Master", "Do 5 pistol squats on one leg in a set.", "strength", "epic", 160, "best:pistol_squat", 5, "♞", "reps", ex=("pistol_squat",))
_a("mu_1", "Over the Bar", "Do a bar muscle-up.", "strength", "epic", 200, "best:bar_muscle_up", 1, "⬢", "reps", ex=("bar_muscle_up",), sk=("bar_muscle_up",))
_a("mu_5", "Muscle-Up Machine", "Do 5 bar muscle-ups in a set.", "strength", "legendary", 450, "best:bar_muscle_up", 5, "⬢", "reps", ex=("bar_muscle_up",), sk=("bar_muscle_up",))

# -------------------------------------------------------------- static holds
_a("plank_60", "Steady Core", "Hold a plank for 60 seconds.", "static", "common", 20, "best:plank", 60, "▬", "s", ex=("plank",))
_a("plank_180", "Iron Core", "Hold a plank for 3 minutes.", "static", "rare", 80, "best:plank", 180, "▬", "s", ex=("plank",))
_a("hang_60", "Grip of Steel", "Dead hang for 60 seconds.", "static", "common", 30, "best:dead_hang", 60, "∥", "s", ex=("dead_hang",))
_a("hang_120", "Unbreakable Grip", "Dead hang for 2 minutes.", "static", "rare", 70, "best:dead_hang", 120, "∥", "s", ex=("dead_hang",))
_a("lsit_3", "First L-Sit", "Hold an L-sit for 3 seconds.", "static", "common", 40, "best:l_sit", 3, "L", "s", ex=("l_sit",), sk=("l_sit",))
_a("lsit_15", "L-Sit Steady", "Hold an L-sit for 15 seconds.", "static", "rare", 90, "best:l_sit", 15, "L", "s", ex=("l_sit",), sk=("l_sit",))
_a("lsit_30", "L-Sit Master", "Hold an L-sit for 30 seconds.", "static", "epic", 180, "best:l_sit", 30, "L", "s", ex=("l_sit",), sk=("l_sit",))
_a("wallhs_30", "Wall Walker", "Hold a wall handstand for 30 seconds.", "static", "common", 30, "best:wall_handstand", 30, "✚", "s", ex=("wall_handstand",), sk=("wall_handstand",))
_a("hs_5", "Free at Last", "Hold a freestanding handstand for 5 seconds.", "static", "rare", 100, "best:free_handstand", 5, "✚", "s", ex=("free_handstand",), sk=("free_handstand",))
_a("hs_30", "Handstand Artist", "Hold a freestanding handstand for 30 seconds.", "static", "epic", 200, "best:free_handstand", 30, "✚", "s", ex=("free_handstand",), sk=("free_handstand",))
_a("hs_60", "Upside-Down Legend", "Hold a freestanding handstand for a full minute.", "static", "legendary", 400, "best:free_handstand", 60, "✚", "s", ex=("free_handstand",), sk=("free_handstand",))
_a("fl_tuck", "Lever Begins", "Hold a tuck front lever for 5 seconds.", "static", "rare", 100, "best:tuck_front_lever", 5, "═", "s", ex=("tuck_front_lever",), sk=("tuck_front_lever",))
_a("fl_full", "Front Lever", "Hold a full front lever for 3 seconds.", "static", "legendary", 500, "best:full_front_lever", 3, "═", "s", ex=("full_front_lever",), sk=("full_front_lever",))
_a("bl_full", "Back Lever", "Hold a full back lever for 3 seconds.", "static", "legendary", 450, "best:full_back_lever", 3, "═", "s", ex=("full_back_lever",), sk=("full_back_lever",))
_a("planche_tuck", "Planche Begins", "Hold a tuck planche for 5 seconds.", "static", "rare", 100, "best:tuck_planche", 5, "✦", "s", ex=("tuck_planche",), sk=("tuck_planche",))
_a("planche_straddle", "Straddle Planche", "Hold a straddle planche for 3 seconds.", "static", "epic", 250, "best:straddle_planche", 3, "✦", "s", ex=("straddle_planche",), sk=("straddle_planche",))
_a("planche_full", "Full Planche", "Hold a full planche for 3 seconds.", "static", "legendary", 600, "best:full_planche", 3, "✦", "s", ex=("full_planche",), sk=("full_planche",))
_a("flag_clutch", "Flag Raised", "Hold a clutch flag for 5 seconds.", "static", "rare", 90, "best:clutch_flag", 5, "⚑", "s", ex=("clutch_flag",), sk=("clutch_flag",))
_a("flag_human", "Human Flag", "Hold a full human flag for 3 seconds.", "static", "legendary", 500, "best:human_flag", 3, "⚑", "s", ex=("human_flag",), sk=("human_flag",))

# ----------------------------------------------------------------- skill tree
for n, nm, r, xp in ((1, "First Skill", "common", 15), (5, "Skill Collector", "common", 40), (15, "Skill Builder", "rare", 90),
                     (30, "Skill Veteran", "epic", 200), (50, "Skill Master", "legendary", 400), (len(SKILLS), "Master of the Tree", "legendary", 800)):
    _a(f"skills_{n}", nm, f"Complete {n} skills in the skill tree." if n < len(SKILLS) else "Complete every skill in the skill tree.",
       "skills", r, xp, "skills_done", n, "❖", "skills")
_a("tier2_1", "Advanced Practitioner", "Complete an advanced-tier skill.", "skills", "rare", 100, "skills_tier:2", 1, "◇", "skills")
_a("tier3_1", "Elite Initiate", "Complete an elite-tier skill.", "skills", "epic", 220, "skills_tier:3", 1, "◈", "skills")
_a("tier3_5", "Elite Athlete", "Complete 5 elite-tier skills.", "skills", "legendary", 500, "skills_tier:3", 5, "◈", "skills")
for key, (label, _) in CATEGORIES.items():
    count = sum(1 for s in SKILLS if s.category == key)
    _a(f"branch_{key}", f"{label} Master", f"Complete every {label.lower()} skill in the tree ({count} skills).",
       "skills", "epic", 250, f"skills_cat:{key}", count, "♛", "skills")

# ------------------------------------------------------------------- training
for n, nm, r, xp in ((1, "First Workout", "common", 25), (10, "Getting Serious", "common", 60), (25, "Quarter Century", "rare", 100),
                     (50, "Fifty Strong", "rare", 150), (100, "Centurion", "epic", 300), (250, "Iron Habit", "legendary", 600)):
    _a(f"workouts_{n}", nm, f"Complete {n} workout{'s' if n > 1 else ''}.", "training", r, xp, "workouts", n, "●", "workouts")
_a("sched_1", "Plan Executed", "Complete a scheduled workout.", "training", "common", 25, "scheduled", 1, "▣", "workouts")
_a("sched_10", "On Schedule", "Complete 10 scheduled workouts.", "training", "rare", 90, "scheduled", 10, "▣", "workouts")
for n, nm, r, xp in ((100, "Hundred Sets", "common", 40), (500, "Set Grinder", "rare", 120), (2000, "Set Machine", "epic", 300)):
    _a(f"sets_{n}", nm, f"Complete {n} sets.", "training", r, xp, "sets", n, "▤", "sets")
_a("reps_1000", "Thousand Reps", "Perform 1,000 reps in total.", "training", "rare", 100, "reps", 1000, "∑", "reps")
_a("reps_5000", "Five Thousand Reps", "Perform 5,000 reps in total.", "training", "epic", 250, "reps", 5000, "∑", "reps")
_a("hold_600", "Under Tension", "Accumulate 10 minutes of static holds.", "training", "rare", 100, "hold_seconds", 600, "⏱", "s")

# ------------------------------------------------------------ personal records
for n, nm, r, xp in ((1, "New Personal Best", "common", 25), (10, "Record Setter", "common", 70),
                     (25, "Record Breaker", "rare", 140), (50, "Limit Pusher", "epic", 250)):
    _a(f"prs_{n}", nm, f"Set {n} personal record{'s' if n > 1 else ''} (a new best on a later day).", "records", r, xp, "prs", n, "★", "records")
for n, nm, r, xp in ((1, "First Rank", "common", 25), (10, "Rank Collector", "rare", 100), (25, "Rank Hoarder", "epic", 200)):
    _a(f"ranked_{n}", nm, f"Earn a rank in {n} exercise{'s' if n > 1 else ''}.", "records", r, xp, "ranks_ge:1", n, "⬢", "exercises")
_a("rank4_1", "Warden", "Reach Warden rank in any exercise.", "records", "rare", 100, "ranks_ge:4", 1, "⬢", "exercises")
_a("rank6_1", "Champion", "Reach Champion rank in any exercise.", "records", "epic", 200, "ranks_ge:6", 1, "⬢", "exercises")
_a("rank8_1", "Mythic", "Reach the top rank, Mythic, in any exercise.", "records", "legendary", 500, "ranks_ge:8", 1, "⬢", "exercises")
_a("rank4_5", "Well-Rounded", "Reach Warden rank in 5 different exercises.", "records", "epic", 250, "ranks_ge:4", 5, "⬢", "exercises")

# ---------------------------------------------------------------- consistency
for n, nm, r, xp in ((3, "Three in a Week", "common", 40), (4, "Four in a Week", "rare", 80), (5, "Five in a Week", "epic", 150)):
    _a(f"week_{n}", nm, f"Complete {n} workouts within one week.", "consistency", r, xp, "week_best", n, "▥", "workouts")
_a("month_12", "Monthly Rhythm", "Complete 12 workouts within one calendar month.", "consistency", "rare", 100, "month_best", 12, "▦", "workouts")
_a("month_20", "Relentless Month", "Complete 20 workouts within one calendar month.", "consistency", "epic", 220, "month_best", 20, "▦", "workouts")
for n, nm, r, xp in ((3, "Three Days Straight", "common", 40), (7, "Week Warrior", "rare", 120), (14, "Fortnight of Fire", "epic", 260)):
    _a(f"streak_{n}", nm, f"Train on {n} days in a row.", "consistency", r, xp, "streak_days", n, "♨", "days")
for n, nm, r, xp in ((4, "Month of Discipline", "rare", 120), (8, "Two Months Strong", "epic", 250), (12, "Quarter of Iron", "legendary", 450)):
    _a(f"wstreak_{n}", nm, f"Train 3+ times a week for {n} weeks in a row.", "consistency", r, xp, "week_streak", n, "▩", "weeks")

# ------------------------------------------------------------ level & collection
for n, nm, r, xp in ((5, "Rising Star", "common", 30), (10, "Double Figures", "rare", 100), (25, "Quarter Hundred", "epic", 250), (50, "Halfway to Legend", "legendary", 600)):
    _a(f"level_{n}", nm, f"Reach level {n}.", "progression", r, xp, "level", n, "✱", "level")
_a("collect_10", "Trophy Case", "Unlock 10 achievements.", "progression", "rare", 100, "achievements", 10, "❂", "achievements")
_a("collect_25", "Hall of Fame", "Unlock 25 achievements.", "progression", "epic", 250, "achievements", 25, "❂", "achievements")

# --------------------------------------------------------------------- library
for n, nm, r, xp in ((1, "First Exercise", "common", 20), (10, "Library Regular", "common", 60),
                     (25, "Library Explorer", "rare", 140), (50, "Movement Collector", "epic", 280)):
    _a(f"lib_ex_{n}", nm, f"Train {n} different exercise{'s' if n > 1 else ''}.",
       "library", r, xp, "exercises_trained", n, "❖", "exercises")
for n, nm, r, xp in ((2, "Two Worlds", "common", 40), (4, "Category Sampler", "rare", 120),
                     (6, "Wide Spectrum", "epic", 220), (8, "Full Spectrum", "legendary", 450)):
    _a(f"lib_cat_{n}", nm, f"Train exercises from {n} different library categories.",
       "library", r, xp, "categories_trained", n, "◫", "categories")
_a("hold_max_60", "One Minute Tension", "Hold a static exercise for 60 seconds in a single set.",
   "library", "common", 40, "max_hold", 60, "⏲", "s")
_a("hold_max_180", "Three Minute Hold", "Hold a static exercise for 180 seconds in a single set.",
   "library", "rare", 120, "max_hold", 180, "⏲", "s")
_a("hold_max_300", "Five Minute Iron", "Hold a static exercise for 300 seconds in a single set.",
   "library", "epic", 240, "max_hold", 300, "⏲", "s")

BY_ID = {a.id: a for a in ACHIEVEMENTS}
assert len(BY_ID) == len(ACHIEVEMENTS), "duplicate achievement id"
