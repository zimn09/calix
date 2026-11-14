"""XP amounts, level curve and titles (pure logic: no Qt, no database).

Level n -> n+1 needs  100 + 40*(n-1) + 6*(n-1)^2  XP, so early levels come quickly
(100, 146, 204, 274 ...) and later ones need sustained effort (level 10 needs ~950 XP,
level 20 ~3000). Edit the constants below to rebalance.
"""
from dataclasses import dataclass

from skills_data import TIER_XP

MAX_LEVEL = 100
# (first level, title, colour)
TITLES = [(1, "Beginner", "#9aa4b2"), (5, "Apprentice", "#69db7c"), (10, "Warrior", "#4dabf7"),
          (15, "Veteran", "#9775fa"), (20, "Elite", "#f06595"), (30, "Master", "#ff922b"),
          (45, "Grandmaster", "#ffd43b"), (60, "Legend", "#ffffff")]

# ---- what gives XP (every reward is one-time and tied to a recorded activity)
XP_WORKOUT = 25                  # finishing a workout (>= half of its sets done)
XP_SCHEDULED = 15                # extra when it was started from the schedule (>= 80% of sets)
XP_PER_SET = 1                   # per completed set ...
MAX_SET_XP = 15                  # ... up to this many per workout
XP_PER_EXERCISE = 3              # per exercise with every set completed ...
MAX_EXERCISES_XP = 8             # ... up to this many per workout
XP_PR = {0: 10, 1: 15, 2: 20, 3: 30}                 # new personal best, by exercise difficulty
XP_RANK = [0, 3, 5, 10, 20, 35, 55, 85, 130]         # reaching rank 1..8 for the first time (low ranks are cheap)
LINE_RANK_SHARE = 0.5                                # progression lines overlap with single exercises: half pay
XP_SKILL_UNLOCK = [5, 10, 20, 40]                    # a skill becomes available (by tier)
XP_SKILL_DONE = list(TIER_XP)                        # a skill is completed (by tier)

SESSION_DAILY_CAP = 3            # only the first 3 qualifying workouts per day earn XP
MIN_SESSION_SECONDS = 120        # a workout shorter than 2 minutes earns nothing
MIN_SETS_SHARE = 0.5             # share of planned sets that must be done


def rank_xp(rank, difficulty, line=False):
    return max(1, round(XP_RANK[rank] * (1 + 0.25 * difficulty) * (LINE_RANK_SHARE if line else 1)))


def xp_needed(level):
    """XP to go from `level` to `level + 1`."""
    k = level - 1
    return 100 + 40 * k + 6 * k * k


def cumulative(level):
    """Total XP at which `level` is reached (level 1 = 0 XP)."""
    m = level - 1
    return 100 * m + 20 * m * (m - 1) + (m - 1) * m * (2 * m - 1)


def title_for(level):
    cur = TITLES[0]
    for t in TITLES:
        if level >= t[0]:
            cur = t
    return cur[1], cur[2]


@dataclass(frozen=True)
class LevelInfo:
    level: int
    title: str
    color: str
    total: int
    into: int            # XP earned inside the current level
    need: int            # XP the current level needs (0 at max level)
    progress: float      # 0..1
    next_title: str = ""  # title of the next tier, if any
    next_title_level: int = 0


def level_info(total):
    total = max(0, int(total))
    level = 1
    while level < MAX_LEVEL and total >= cumulative(level + 1):
        level += 1
    title, color = title_for(level)
    nxt = next(((n, lv) for lv, n, _ in TITLES if lv > level), ("", 0))
    if level >= MAX_LEVEL:
        return LevelInfo(level, title, color, total, 0, 0, 1.0, *nxt)
    into, need = total - cumulative(level), xp_needed(level)
    return LevelInfo(level, title, color, total, into, need, into / need, *nxt)
