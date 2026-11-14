"""Export the CALIX Python data modules to JSON for the Rust port.

Run from anywhere:   python3 tools/export_data.py

The Rust app embeds the generated files in ``data/`` at compile time, so the
skill tree, exercise library, achievements and rank ladders stay identical to
the Python edition. Re-run this if the Python data changes.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]          # calix 1.1rust/
PY = ROOT.parent / "calix 1.1" / "python"
OUT = ROOT / "data"
sys.path.insert(0, str(PY))

import achievements as A            # noqa: E402
import exercise_details_data as D   # noqa: E402
import exercises_data as E          # noqa: E402
import progression as P             # noqa: E402
import ranks as R                   # noqa: E402
import skills_data as S             # noqa: E402


def dump(name, obj):
    OUT.mkdir(exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{name}: {path.stat().st_size // 1024} KiB")


def skills():
    items = [dict(id=s.id, name=s.name, category=s.category, tier=s.tier,
                  prereqs=list(s.prereqs), description=s.description, steps=list(s.steps),
                  exercises=list(s.exercises), regressions=list(s.regressions),
                  unit=s.unit, target=s.target, note=s.note) for s in S.SKILLS]
    dump("skills.json", {
        "categories": {k: {"label": v[0], "color": v[1]} for k, v in S.CATEGORIES.items()},
        "category_order": list(S.CATEGORIES),
        "tiers": list(S.TIERS),
        "tier_xp": list(S.TIER_XP),
        "items": items,
    })


def exercises():
    dump("exercises.json", {
        "categories": {k: {"label": v[0], "color": v[1]} for k, v in E.EX_CATEGORIES.items()},
        "category_order": list(E.CATEGORY_ORDER),
        "difficulty": list(E.DIFFICULTY),
        "items": E.EXERCISES,
    })
    dump("details.json", {
        k: dict(muscles=list(d.muscles), mistakes=list(d.mistakes), tips=list(d.tips),
                easier=list(d.easier), harder=list(d.harder), prereq=list(d.prereq),
                related=list(d.related), equipment=d.equipment)
        for k, d in D.DETAILS.items()
    })


def achievements():
    items = [dict(id=a.id, name=a.name, description=a.description, category=a.category,
                  rarity=a.rarity, xp=a.xp, metric=a.metric, target=a.target, icon=a.icon,
                  unit=a.unit, exercises=list(a.exercises), skills=list(a.skills))
             for a in A.ACHIEVEMENTS]
    dump("achievements.json", {
        "categories": A.CATEGORY_LABELS,
        "rarities": {k: {"label": v[0], "color": v[1], "order": v[2]} for k, v in A.RARITIES.items()},
        "items": items,
    })


def ranks():
    dump("ranks.json", {
        "ranks": [[name, color] for name, color in R.RANKS],
        "max_rank": R.MAX_RANK,
        "groups": R.GROUPS,
        "tops": R.TOPS,
        "lines": [dict(id=lid, name=name, group=group,
                       steps=[{"exercise_id": e, "need": n} for e, n in steps])
                  for lid, name, group, steps in R.LINES],
        "single_fractions": list(R.SINGLE_FRACTIONS),
        "line_fractions": list(R.LINE_FRACTIONS),
    })


def progression():
    dump("progression.json", {
        "max_level": P.MAX_LEVEL,
        "titles": [dict(level=l, title=t, color=c) for l, t, c in P.TITLES],
        "xp_workout": P.XP_WORKOUT,
        "xp_scheduled": P.XP_SCHEDULED,
        "xp_per_set": P.XP_PER_SET,
        "max_set_xp": P.MAX_SET_XP,
        "xp_per_exercise": P.XP_PER_EXERCISE,
        "max_exercises_xp": P.MAX_EXERCISES_XP,
        "xp_pr": {str(k): v for k, v in P.XP_PR.items()},
        "xp_rank": list(P.XP_RANK),
        "line_rank_share": P.LINE_RANK_SHARE,
        "xp_skill_unlock": list(P.XP_SKILL_UNLOCK),
        "xp_skill_done": list(P.XP_SKILL_DONE),
        "session_daily_cap": P.SESSION_DAILY_CAP,
        "min_session_seconds": P.MIN_SESSION_SECONDS,
        "min_sets_share": P.MIN_SETS_SHARE,
    })


skills()
exercises()
achievements()
ranks()
progression()
print("done")
