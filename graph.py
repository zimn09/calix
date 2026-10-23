"""Prerequisite graph logic (no Qt code, so it can be unit-tested on its own)."""
from collections import defaultdict

from skills_data import CATEGORIES, TIER_XP

NODE_W, NODE_H = 170, 66
COL_W, ROW_H, LANE_GAP = 200, 150, 70

LEVEL_XP = [0, 15, 40, 80, 140, 220, 330, 480, 680, 950, 1300, 1800, 2500, 3400, 4500]
TITLES = ["Novice", "Trainee", "Apprentice", "Adept", "Veteran", "Master", "Grandmaster", "Legend"]


class SkillGraph:
    def __init__(self, skills):
        self.skills = {s.id: s for s in skills}
        self.order = [s.id for s in skills]
        self.children = defaultdict(list)
        for s in skills:
            for p in s.prereqs:
                if p not in self.skills:
                    raise ValueError(f"{s.id}: unknown prerequisite '{p}'")
                self.children[p].append(s.id)
        self.depth = {}
        for sid in self.order:
            self._depth(sid, ())

    # ------------------------------------------------------------ structure
    def _depth(self, sid, stack):
        if sid in stack:
            raise ValueError(f"Prerequisite cycle through '{sid}'")
        if sid not in self.depth:
            pre = self.skills[sid].prereqs
            self.depth[sid] = 0 if not pre else 1 + max(self._depth(p, stack + (sid,)) for p in pre)
        return self.depth[sid]

    def ancestors(self, sid):
        seen, stack = set(), list(self.skills[sid].prereqs)
        while stack:
            cur = stack.pop()
            if cur not in seen:
                seen.add(cur)
                stack.extend(self.skills[cur].prereqs)
        return seen

    # ------------------------------------------------------------ progress
    def status(self, sid, progress):
        """locked | available | training | completed"""
        cur = progress.get(sid)
        if cur == "completed":
            return "completed"
        if all(progress.get(p) == "completed" for p in self.skills[sid].prereqs):
            return "training" if cur == "training" else "available"
        return "locked"

    def missing_prereqs(self, sid, progress):
        return [p for p in self.skills[sid].prereqs if progress.get(p) != "completed"]

    def xp(self, progress):
        return sum(TIER_XP[self.skills[s].tier] for s, v in progress.items()
                   if v == "completed" and s in self.skills)

    # ------------------------------------------------------------ layout
    def layout(self):
        """Returns ({id: (x, y)}, {category: (left, width)}, max_row).

        One lane per category, rows by prerequisite depth. Within a lane, nodes
        in the same row are ordered by the x of their prerequisites to keep
        edges short.
        """
        cats = list(CATEGORIES)
        groups = defaultdict(list)
        for sid in self.order:
            groups[(self.skills[sid].category, self.depth[sid])].append(sid)

        lane_cols = {c: max([len(v) for (cc, _), v in groups.items() if cc == c] or [1]) for c in cats}
        lanes, x = {}, 0
        for c in cats:
            lanes[c] = (x, lane_cols[c] * COL_W)
            x += lane_cols[c] * COL_W + LANE_GAP

        pos = {}
        max_row = max(self.depth.values())
        for d in range(max_row + 1):
            for c in cats:
                ids = groups.get((c, d))
                if not ids:
                    continue
                center = lanes[c][0] + lanes[c][1] / 2

                def desire(sid):
                    xs = [pos[p][0] for p in self.skills[sid].prereqs if p in pos]
                    return sum(xs) / len(xs) if xs else center

                ids = sorted(ids, key=desire)
                n = len(ids)
                for i, sid in enumerate(ids):
                    pos[sid] = (center + (i - (n - 1) / 2) * COL_W, d * ROW_H)
        return pos, lanes, max_row


def level_info(xp):
    """-> (level, xp_into_level, xp_needed_for_next, title)"""
    lvl = 1
    for i, t in enumerate(LEVEL_XP):
        if xp >= t:
            lvl = i + 1
    title = TITLES[min((lvl - 1) // 2, len(TITLES) - 1)]
    if lvl >= len(LEVEL_XP):
        return lvl, 1, 1, title
    lo, hi = LEVEL_XP[lvl - 1], LEVEL_XP[lvl]
    return lvl, xp - lo, hi - lo, title
