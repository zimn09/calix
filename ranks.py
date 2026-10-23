"""Per-exercise rank system (pure logic: no Qt, no database).

Every exercise has its own rank ladder, independent of all others. A rank only
changes when a *performance* is recorded; finishing a workout does not raise it.

Metrics
  reps   best single set of technically clean reps (per side for one-sided moves)
  hold   best single hold in seconds
  line   a progression line (e.g. Planche): the highest step you have mastered
         plus how far you are into the next one

Tuning the ladders: edit TOPS (value needed for the top rank of each exercise,
harder variants simply have lower tops) or LINES, or pass explicit thresholds.
"""
from dataclasses import dataclass, field

RANKS = [
    ("Unranked", "#4b5565"), ("Initiate", "#9aa4b2"), ("Squire", "#69db7c"), ("Vanguard", "#38d9a9"),
    ("Warden", "#4dabf7"), ("Paladin", "#9775fa"), ("Champion", "#f06595"), ("Titan", "#ff922b"),
    ("Mythic", "#ffd43b"),
]
MAX_RANK = len(RANKS) - 1
ROMAN = ["–", "I", "II", "III", "IV", "V", "VI", "VII", "VIII"]

GROUPS = {"pushing": "Pushing", "pulling": "Pulling", "core": "Core", "legs": "Legs", "static": "Static skills"}

# share of the top value needed for ranks 1..8
SINGLE_FRACTIONS = (0.05, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 1.0)
LINE_FRACTIONS = (0.10, 0.20, 0.35, 0.50, 0.65, 0.80, 0.90, 1.0)

# Value for the top rank (Mythic): reps for rep exercises, seconds for holds.
TOPS = {
    # pull
    "australian_row": 40, "assisted_pullup": 25, "negative_pullup": 15, "scap_pull": 30, "chinup": 30,
    "pullup": 25, "wide_pullup": 18, "close_pullup": 22, "c2b_pullup": 15, "archer_pullup": 10,
    "l_sit_pullup": 12, "dead_hang": 180, "active_hang": 90, "one_arm_pullup": 3,
    # push
    "wall_pushup": 80, "incline_pushup": 70, "knee_pushup": 60, "pushup": 70, "wide_pushup": 60,
    "diamond_pushup": 45, "decline_pushup": 50, "pike_pushup": 40, "bench_dip": 50, "dip": 40,
    "korean_dip": 15, "archer_pushup": 15, "pseudo_planche_pushup": 20, "clap_pushup": 25, "wall_hspu": 15,
    "one_arm_pushup": 8, "free_hspu": 8,
    # core
    "plank": 300, "side_plank": 180, "dead_bug": 60, "hollow_hold": 120, "lying_leg_raise": 40,
    "hanging_knee_raise": 40, "hanging_leg_raise": 30, "ab_wheel": 25, "tuck_l_sit": 60, "l_sit": 60,
    "toes_to_bar": 20, "dragon_flag": 10,
    # legs
    "squat": 100, "jump_squat": 50, "lunge": 40, "split_squat": 40, "bulgarian": 25, "step_up": 40,
    "glute_bridge": 60, "wall_sit": 240, "calf_raise": 80, "single_calf_raise": 50, "shrimp_squat": 12,
    "pistol_squat": 20, "nordic_curl": 10,
    # skill training
    "wall_handstand": 180, "free_handstand": 90, "handstand_kickup": 20, "crow_pose": 60,
    "false_grip_hang": 60, "mu_transition": 12, "bar_muscle_up": 15, "skin_the_cat": 15,
    "tuck_front_lever": 40, "adv_tuck_front_lever": 30, "straddle_front_lever": 20, "full_front_lever": 15,
    "tuck_back_lever": 40, "straddle_back_lever": 25, "full_back_lever": 15, "planche_lean": 90,
    "tuck_planche": 30, "adv_tuck_planche": 20, "straddle_planche": 15, "full_planche": 10,
    "clutch_flag": 20, "straddle_flag": 12, "human_flag": 8,
    # balance
    "handstand_walk": 30, "press_handstand": 10,
    # skill progressions
    "ring_muscle_up": 10, "dragonfly": 10,
    # explosive
    "jump_lunge": 25, "box_jump": 20, "tuck_jump": 20, "burpee": 20,
    # extra rings / scapula work
    "scapular_dip": 30, "ring_dip": 30,
}

# Progression lines: (id, name, group, [(exercise_id, value needed to count the step as mastered)])
LINES = [
    ("line_pushup", "Push-up variations", "pushing",
     [("incline_pushup", 15), ("pushup", 15), ("decline_pushup", 12), ("archer_pushup", 6),
      ("pseudo_planche_pushup", 8), ("one_arm_pushup", 3)]),
    ("line_dip", "Dip progression", "pushing", [("bench_dip", 15), ("dip", 10), ("korean_dip", 5)]),
    ("line_hspu", "Handstand push-up line", "pushing", [("pike_pushup", 10), ("wall_hspu", 5), ("free_hspu", 3)]),
    ("line_pullup", "Pull-up variations", "pulling",
     [("australian_row", 12), ("pullup", 8), ("wide_pullup", 8), ("c2b_pullup", 5), ("archer_pullup", 5),
      ("l_sit_pullup", 5)]),
    ("line_muscleup", "Muscle-up line", "pulling",
     [("pullup", 10), ("c2b_pullup", 5), ("mu_transition", 3), ("bar_muscle_up", 3)]),
    ("line_planche", "Planche line", "static",
     [("planche_lean", 20), ("tuck_planche", 5), ("adv_tuck_planche", 5), ("straddle_planche", 5),
      ("full_planche", 3)]),
    ("line_front_lever", "Front lever line", "static",
     [("tuck_front_lever", 10), ("adv_tuck_front_lever", 8), ("straddle_front_lever", 5),
      ("full_front_lever", 3), ("dragonfly", 5)]),
    ("line_back_lever", "Back lever line", "static",
     [("skin_the_cat", 5), ("tuck_back_lever", 10), ("straddle_back_lever", 8), ("full_back_lever", 5)]),
    ("line_handstand", "Handstand line", "static",
     [("crow_pose", 15), ("wall_handstand", 30), ("free_handstand", 30),
      ("handstand_walk", 20), ("press_handstand", 3)]),
    ("line_flag", "Human flag line", "static",
     [("side_plank", 45), ("clutch_flag", 5), ("straddle_flag", 5), ("human_flag", 3)]),
    ("line_pistol", "Single-leg squat line", "legs",
     [("squat", 30), ("bulgarian", 10), ("shrimp_squat", 5), ("pistol_squat", 5)]),
    ("line_ring", "Ring strength line", "pulling",
     [("ring_dip", 10), ("ring_muscle_up", 3)]),
    ("line_explosive", "Explosive power line", "legs",
     [("jump_squat", 20), ("jump_lunge", 12), ("box_jump", 10), ("tuck_jump", 10),
      ("burpee", 15)]),
]

_GROUP_OVERRIDE = {"bar_muscle_up": "pulling", "mu_transition": "pulling", "skin_the_cat": "pulling",
                  "handstand_kickup": "static", "wall_hspu": "pushing", "free_hspu": "pushing",
                  "ring_muscle_up": "pulling", "press_handstand": "static",
                  "clap_pushup": "pushing", "burpee": "core",
                  "jump_squat": "legs", "jump_lunge": "legs", "box_jump": "legs",
                  "tuck_jump": "legs"}

# The eight library categories mapped onto the five rank groups.
_CATEGORY_GROUP = {"push": "pushing", "pull": "pulling", "core": "core", "legs": "legs",
                   "static": "static", "balance": "static", "skill": "static",
                   "explosive": "legs"}

# Categories where a hold is really a static skill rather than a strength set.
_HOLD_AS_STATIC = ("pull", "push", "skill", "balance", "static")


def group_for(ex):
    """Library exercise -> rank group (pushing / pulling / core / legs / static)."""
    if ex["id"] in _GROUP_OVERRIDE:
        return _GROUP_OVERRIDE[ex["id"]]
    if ex["kind"] == "hold" and ex["category"] in _HOLD_AS_STATIC:
        return "static"
    return _CATEGORY_GROUP.get(ex["category"], "core")


def make_thresholds(top, fractions=SINGLE_FRACTIONS, integer=True):
    """Strictly increasing thresholds for ranks 1..8."""
    out = []
    for f in fractions:
        v = max(1, round(top * f)) if integer else round(top * f, 2)
        if out and v <= out[-1]:
            v = out[-1] + (1 if integer else 0.05)
        out.append(v)
    return tuple(out)


@dataclass(frozen=True)
class Step:
    exercise_id: str
    need: float
    name: str
    unit: str


@dataclass(frozen=True)
class Track:
    id: str
    name: str
    group: str
    metric: str                      # reps | hold | line
    thresholds: tuple
    exercise_id: str = ""
    steps: tuple = ()
    difficulty: int = 0
    unit: str = ""


@dataclass
class RankUp:
    date: str
    rank: int
    value: float


@dataclass
class TrackResult:
    track: Track
    best: float = 0.0                # best value, or score for a line
    best_date: str = ""
    rank: int = 0
    progress: float = 0.0            # 0..1 toward the next rank
    target: float = None             # threshold of the next rank (None at max)
    remaining: float = None
    headline: str = ""
    goal: str = ""
    practiced: bool = False
    history: list = field(default_factory=list)


def build_tracks(exercises):
    """Rank tracks for every library exercise that has a ladder, then the progression lines."""
    by_id = {e["id"]: e for e in exercises}
    tracks = []
    for e in exercises:
        top = TOPS.get(e["id"])
        if top is None:
            continue
        tracks.append(Track(e["id"], e["name"], group_for(e), e["kind"], make_thresholds(top),
                            exercise_id=e["id"], difficulty=e["difficulty"],
                            unit="reps" if e["kind"] == "reps" else "s"))
    for lid, name, group, steps in LINES:
        if not all(sid in by_id for sid, _ in steps):
            continue
        st = tuple(Step(sid, need, by_id[sid]["name"], "reps" if by_id[sid]["kind"] == "reps" else "s")
                   for sid, need in steps)
        tracks.append(Track(lid, name, group, "line", make_thresholds(len(st), LINE_FRACTIONS, integer=False),
                            steps=st, difficulty=max(by_id[s]["difficulty"] for s, _ in steps), unit="steps"))
    return tracks


def rank_for(thresholds, value):
    """Number of thresholds reached (0 = unranked)."""
    return sum(1 for t in thresholds if value >= t)


def _fmt(v):
    return f"{v:g}"


def _fill(res, value):
    """Progress/target fields shared by singles and lines."""
    th, r = res.track.thresholds, res.rank
    if r >= MAX_RANK:
        res.progress, res.target, res.remaining = 1.0, None, None
        return
    lo = th[r - 1] if r else 0
    res.target = th[r]
    res.progress = max(0.0, min(1.0, (value - lo) / (th[r] - lo)))
    res.remaining = max(0.0, th[r] - value)


def evaluate_single(track, events):
    """events: [(date, value)] for this exercise (any order)."""
    res = TrackResult(track)
    for date, v in sorted(events):
        if v > res.best:
            res.best, res.best_date = v, date
        r = rank_for(track.thresholds, res.best)
        if r > res.rank:
            res.history.append(RankUp(date, r, res.best))
            res.rank = r
    res.practiced = res.best > 0
    _fill(res, res.best)
    u = track.unit
    res.headline = f"Best {_fmt(res.best)} {u}" if res.practiced else "No performance recorded yet"
    if res.target is None:
        res.goal = f"Top rank reached ({RANKS[MAX_RANK][0]})"
    else:
        res.goal = (f"{_fmt(res.target)} {u} for {RANKS[res.rank + 1][0]}"
                    if res.practiced else f"Log your first set, {_fmt(track.thresholds[0])} {u} makes you an Initiate")
    return res


def line_score(steps, bests, passed):
    """(score, index of highest mastered step). Score = mastered steps + progress into the next one."""
    hi = -1
    for i, s in enumerate(steps):
        if s.exercise_id in passed or bests.get(s.exercise_id, 0) >= s.need:
            hi = i
    score = float(hi + 1)
    if hi + 1 < len(steps):
        nxt = steps[hi + 1]
        score += min(0.99, bests.get(nxt.exercise_id, 0) / nxt.need)
    return score, hi


def evaluate_line(track, events, passed_events=()):
    """events: [(date, exercise_id, value)]; passed_events: [(date, exercise_id)] (skill marked completed)."""
    res = TrackResult(track)
    items = [(d, 0, e, v) for d, e, v in events] + [(d, 1, e, 0) for d, e in passed_events]
    bests, passed = {}, set()
    for date, kind, ex, v in sorted(items):
        if kind == 0:
            bests[ex] = max(bests.get(ex, 0), v)
        else:
            passed.add(ex)
        score, _ = line_score(track.steps, bests, passed)
        r = rank_for(track.thresholds, score)
        if r > res.rank:
            res.history.append(RankUp(date, r, round(score, 2)))
            res.rank = r
        if score > res.best:
            res.best, res.best_date = score, date
    score, hi = line_score(track.steps, bests, passed)
    res.best, res.rank = score, rank_for(track.thresholds, score)
    res.practiced = bool(bests) or bool(passed)
    _fill(res, score)
    n = len(track.steps)
    res.headline = (f"Mastered: {track.steps[hi].name}  ({hi + 1}/{n} steps)" if hi >= 0
                    else "No step mastered yet")
    if hi + 1 >= n:
        res.goal = "Progression line complete"
    else:
        nxt = track.steps[hi + 1]
        res.goal = f"Next step: {nxt.name}, {_fmt(nxt.need)} {nxt.unit}"
    return res


# ------------------------------------------------------------------ overview
def strength(r):
    """Position on the 0..8 ladder including progress toward the next rank."""
    return float(MAX_RANK) if r.rank >= MAX_RANK else r.rank + 0.99 * r.progress


def group_scores(results):
    """Average ladder position per group over foundation exercises (beginner/intermediate) and any ranked ones."""
    out = {}
    for g in GROUPS:
        items = [strength(r) for r in results
                 if r.track.metric != "line" and r.track.group == g and (r.track.difficulty <= 1 or r.rank > 0)]
        out[g] = sum(items) / len(items) if items else 0.0
    return out


def strongest(results, n=5):
    ranked = [r for r in results if r.rank > 0]
    return sorted(ranked, key=lambda r: (strength(r) * (1 + 0.2 * r.track.difficulty), r.best), reverse=True)[:n]


def recommend(results, n=3):
    """[(result, reason)]: closest rank-ups first, then foundations in the weakest groups."""
    near = sorted((r for r in results if r.practiced and r.rank < MAX_RANK), key=lambda r: -r.progress)[:n]
    out = [(r, f"{round(r.progress * 100)}% of the way to {RANKS[r.rank + 1][0]}") for r in near]
    if len(out) < n:
        scores = group_scores(results)
        fresh = [r for r in results if r.track.metric != "line" and not r.practiced and r.track.difficulty == 0]
        fresh.sort(key=lambda r: (scores[r.track.group], r.track.name))
        out += [(r, "Not ranked yet, a good foundation") for r in fresh[:n - len(out)]]
    return out
