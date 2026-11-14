"""Progress charts and the progress panel (Qt).

Every number shown here comes from real stored data: finished workout sessions,
confirmed performances, the XP ledger and the skill tree. Nothing is estimated
or randomised. Where a "current performance" is shown next to a "personal
record", the two are always labelled separately.
"""
import datetime as dt
from collections import Counter, defaultdict

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QProgressBar, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from database import fetch_all
from ui_common import Card, StatTile, plain


# --------------------------------------------------------------------- helpers
def _week_start(d):
    return d - dt.timedelta(days=d.weekday())


def weekly_history(history, weeks=12):
    """[(week label, workouts, reps, hold seconds)] for the last `weeks` weeks."""
    today = dt.date.today()
    start = _week_start(today) - dt.timedelta(weeks=weeks - 1)
    buckets = defaultdict(lambda: [0, 0, 0])
    for r in history:
        try:
            d = dt.date.fromisoformat(r["session_date"])
        except (TypeError, ValueError):
            continue
        w = _week_start(d)
        if w < start:
            continue
        b = buckets[w]
        b[0] += 1
        b[1] += int(r["reps_total"] or 0)
        b[2] += int(r["hold_total"] or 0)
    out = []
    for i in range(weeks):
        w = start + dt.timedelta(weeks=i)
        b = buckets.get(w, [0, 0, 0])
        out.append((w.strftime("%d.%m."), b[0], b[1], b[2]))
    return out


def exercise_performance(db, limit=8):
    """Current performance next to the historical personal record.

    Returns a list of dicts with the exercise name, the most recent confirmed
    value, the all-time best and when it was set.
    """
    rows = fetch_all(db, """SELECT p.exercise_id, p.value, p.logged, p.source, e.name, e.kind
                            FROM performances p LEFT JOIN exercises e ON e.id=p.exercise_id""")
    latest, best = {}, {}
    for r in rows:
        ex = r["exercise_id"]
        logged = r["logged"]
        if ex not in latest or logged > latest[ex]["logged"]:
            latest[ex] = r
        if ex not in best or float(r["value"]) > float(best[ex]["value"]):
            best[ex] = r
    out = []
    for ex, last in latest.items():
        b = best[ex]
        out.append(dict(id=ex, name=last["name"] or ex, kind=last["kind"] or "reps",
                        current=float(last["value"]), current_on=last["logged"][:10],
                        best=float(b["value"]), best_on=b["logged"][:10],
                        source=last["source"]))
    out.sort(key=lambda r: (-r["best"], r["name"]))
    return out[:limit]


def recent_milestones(db, limit=8):
    """The newest XP events - real rewards that were paid out."""
    return fetch_all(db, """SELECT amount, reason, category, earned_on FROM xp_events
                            ORDER BY earned_on DESC, id DESC LIMIT ?""", (limit,))


def recently_completed_skills(db, graph, limit=6):
    """Skills the player finished most recently (real skill-tree progress)."""
    rows = fetch_all(db, """SELECT skill_id, status, updated FROM progress
                            WHERE status='completed' ORDER BY updated DESC LIMIT ?""", (limit,))
    out = []
    for r in rows:
        sk = graph.skills.get(r["skill_id"]) if graph else None
        out.append(dict(name=sk.name if sk else r["skill_id"], updated=r["updated"][:10]))
    return out


def rank_overview(results):
    """(ranked tracks, average rank, highest ranks per group)."""
    rows = list(results.values())
    ranked = [r for r in rows if r.rank > 0]
    avg = sum(r.rank for r in ranked) / len(ranked) if ranked else 0
    by_group = defaultdict(list)
    for r in rows:
        by_group[r.track.group].append(r.rank)
    return ranked, avg, {g: max(v) for g, v in by_group.items()}


# ---------------------------------------------------------------------- charts
class TrendChart(QWidget):
    """Line / area chart over time. One or more series with the same x axis."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels = []
        self.series = []          # [(name, color, [values])]
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def set_data(self, labels, series):
        """series = [(name, color, values)]"""
        self.labels = list(labels)
        self.series = [(n, QColor(c), list(v)) for n, c, v in series]
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        left, right, top, bottom = 34, 10, 16, 24
        if not self.labels or not self.series:
            p.setPen(QColor("#6b7686"))
            p.drawText(QRectF(0, 0, w, h), int(Qt.AlignCenter), "No data yet")
            p.end()
            return
        peak = max([max(v) if v else 0 for _, _, v in self.series] + [1])
        top_val = peak if peak <= 4 else (peak + 1) // 2 * 2
        small = QFont(self.font())
        small.setPointSizeF(7.5)
        p.setFont(small)
        plot_h = h - top - bottom
        plot_w = w - left - right
        for i in range(5):
            v = top_val * i / 4
            y = top + plot_h - plot_h * i / 4
            p.setPen(QPen(QColor(255, 255, 255, 16), 1))
            p.drawLine(QPointF(left, y), QPointF(left + plot_w, y))
            p.setPen(QColor("#6b7686"))
            p.drawText(QRectF(0, y - 8, left - 5, 16), int(Qt.AlignRight | Qt.AlignVCenter), f"{v:g}")
        n = len(self.labels)
        step = plot_w / max(1, n - 1) if n > 1 else plot_w
        for name, color, values in self.series:
            pts = []
            for i, v in enumerate(values):
                x = left + (i * step if n > 1 else plot_w / 2)
                y = top + plot_h - plot_h * (v / top_val if top_val else 0)
                pts.append(QPointF(x, y))
            if len(pts) > 1:
                fill = QColor(color)
                fill.setAlpha(38)
                path_area = None
                p.setPen(Qt.NoPen)
                p.setBrush(fill)
                for i in range(len(pts) - 1):
                    x0 = pts[i].x()
                    x1 = pts[i + 1].x()
                    rect = QRectF(x0, top + plot_h, x1 - x0, max(0.0, min(pts[i].y(), pts[i + 1].y()) - (top + plot_h)))
                    p.drawRect(rect)
                p.setPen(QPen(color, 2))
                for i in range(len(pts) - 1):
                    p.drawLine(pts[i], pts[i + 1])
            for i, pt in enumerate(pts):
                p.setPen(Qt.NoPen)
                p.setBrush(color)
                p.drawEllipse(QRectF(pt.x() - 2.5, pt.y() - 2.5, 5, 5))
        p.setPen(QColor("#6b7686"))
        for i, lab in enumerate(self.labels):
            x = left + (i * step if n > 1 else plot_w / 2)
            if n > 9 and i % 2:
                continue
            p.drawText(QRectF(x - 24, h - bottom + 4, 48, 16), int(Qt.AlignCenter), lab)
        # legend
        lx = left
        for name, color, _ in self.series:
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawRect(QRectF(lx, 3, 8, 8))
            p.setPen(QColor("#8b95a7"))
            p.drawText(QRectF(lx + 12, 0, 160, 14), int(Qt.AlignLeft | Qt.AlignVCenter), name)
            lx += 12 + 9 * len(name) + 14
        p.end()


class CompareBars(QWidget):
    """Two horizontal bars: the current performance and the personal record."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.setMinimumHeight(60)

    def set_rows(self, rows):
        self.rows = rows
        self.setMinimumHeight(max(60, 26 * len(rows)))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        small = QFont(self.font())
        small.setPointSizeF(8)
        p.setFont(small)
        y = 4
        for r in self.rows:
            p.setPen(QColor("#e6e9ef"))
            p.drawText(QRectF(0, y, 190, 16), int(Qt.AlignLeft | Qt.AlignVCenter), r["name"])
            x0, w_full = 196, max(60, self.width() - 196 - 120)
            peak = max(r["current"], r["best"], 1)
            unit = " s" if r["kind"] == "hold" else ""
            # current performance
            w1 = w_full * r["current"] / peak
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#4dabf7"))
            p.drawRoundedRect(QRectF(x0, y + 1, max(2, w1), 6), 3, 3)
            p.setPen(QColor("#8b95a7"))
            p.drawText(QRectF(x0 + w1 + 6, y - 1, 110, 14), int(Qt.AlignLeft | Qt.AlignVCenter),
                       f"now {r['current']:g}{unit}")
            # personal record
            w2 = w_full * r["best"] / peak
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#ffd43b"))
            p.drawRoundedRect(QRectF(x0, y + 11, max(2, w2), 5), 2, 2)
            p.setPen(QColor("#6b7686"))
            p.drawText(QRectF(x0 + w2 + 6, y + 8, 120, 14), int(Qt.AlignLeft | Qt.AlignVCenter),
                       f"PR {r['best']:g}{unit} ({r['best_on']})")
            y += 26
        p.end()


# ---------------------------------------------------------------------- panel
class ProgressPanel(QWidget):
    """The progress dashboard: real numbers only."""

    def __init__(self, store, sess, ranks, xp, graph=None, parent=None):
        super().__init__(parent)
        self.store, self.sess, self.ranks, self.xp, self.graph = store, sess, ranks, xp, graph
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setObjectName("plain")
        body = QWidget()
        body.setObjectName("plain")
        self.body = QVBoxLayout(body)
        self.body.setContentsMargins(16, 16, 16, 16)
        self.body.setSpacing(12)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        # ---- level card
        self.level_card = Card("Level & experience")
        lvl = QLabel("")
        lvl.setObjectName("bigValue")
        self.level_value = lvl
        self.level_card.lay.addWidget(lvl)
        self.level_bar = QProgressBar()
        self.level_bar.setTextVisible(True)
        self.level_card.lay.addWidget(self.level_bar)
        self.level_note = QLabel("")
        self.level_note.setObjectName("muted")
        self.level_card.lay.addWidget(self.level_note)

        # ---- stat tiles
        self.tiles = {}
        tiles_row = QHBoxLayout()
        for key, title in (("xp", "Total XP"), ("workouts", "Workouts"), ("achievements", "Achievements"),
                           ("ranks", "Ranked exercises"), ("prs", "Personal records"), ("skills", "Skills done")):
            t = StatTile(title)
            self.tiles[key] = t
            tiles_row.addWidget(t)

        # ---- charts
        self.reps_chart = TrendChart()
        self.hold_chart = TrendChart()
        self.workout_chart = TrendChart()
        self.compare = CompareBars()

        chart_card = Card("Performance over time (real recorded data)")
        self.chart_note = QLabel("")
        self.chart_note.setObjectName("muted")
        chart_card.lay.addWidget(self.chart_note)
        tabs = QGridLayout()
        tabs.addWidget(QLabel("Reps per week"), 0, 0)
        tabs.addWidget(QLabel("Hold seconds per week"), 0, 1)
        tabs.addWidget(QLabel("Workouts per week"), 0, 2)
        tabs.addWidget(self.reps_chart, 1, 0)
        tabs.addWidget(self.hold_chart, 1, 1)
        tabs.addWidget(self.workout_chart, 1, 2)
        chart_card.lay.addLayout(tabs)

        compare_card = Card("Current performance vs personal record")
        compare_card.lay.addWidget(self.compare)
        self.compare_note = QLabel("")
        self.compare_note.setObjectName("muted")
        self.compare_note.setWordWrap(True)
        compare_card.lay.addWidget(self.compare_note)

        # ---- milestones
        self.milestones_card = Card("Recent milestones")
        self.milestones = QLabel("")
        self.milestones.setTextFormat(Qt.RichText)
        self.milestones.setWordWrap(True)
        self.milestones_card.lay.addWidget(self.milestones)

        self.skills_card = Card("Newly unlocked skills")
        self.new_skills = QLabel("")
        self.new_skills.setTextFormat(Qt.RichText)
        self.new_skills.setWordWrap(True)
        self.skills_card.lay.addWidget(self.new_skills)

        self.body.addWidget(self.level_card)
        self.body.addLayout(tiles_row)
        self.body.addWidget(chart_card)
        self.body.addWidget(compare_card)
        self.body.addWidget(self.milestones_card)
        self.body.addWidget(self.skills_card)
        self.body.addStretch(1)

    # ----------------------------------------------------------------- update
    def refresh(self):
        db = self.store.db
        prof = self.xp.profile()
        lvl = self.xp.level()
        self.level_value.setText(f"Level {prof['level']} · {prof['title']}")
        self.level_value.setStyleSheet(f"color:{prof['color']};")
        self.level_bar.setRange(0, max(1, prof["need"]))
        self.level_bar.setValue(min(prof["need"], prof["into"]))
        self.level_bar.setFormat(f"{prof['into']:,} / {prof['need']:,} XP to level {prof['level'] + 1}")
        nxt = prof.get("next_title") or ""
        self.level_note.setText(
            f"{prof['total']:,} XP in total"
            + (f" · next title “{nxt}” at level {prof['next_title_level']}" if nxt else " · maximum title reached"))

        history = self.sess.history(1000)
        results = self.ranks.evaluate_all()
        ranked, avg, by_group = rank_overview(results)
        prs = fetch_all(db, """SELECT COUNT(*) AS n FROM (
                                SELECT exercise_id, MAX(value) FROM performances GROUP BY exercise_id)""")
        pr_count = prs[0]["n"] if prs else 0
        skills = fetch_all(db, "SELECT COUNT(*) AS n FROM progress WHERE status='completed'")

        self.tiles["xp"].set(f"{prof['total']:,}", f"{prof['level']} levels · {prof['title']}")
        self.tiles["workouts"].set(len(history), "workouts completed")
        self.tiles["achievements"].set(f"{prof['unlocked']}/{prof['count']}", "achievements unlocked")
        self.tiles["ranks"].set(len(ranked), f"average rank {avg:.1f}" if ranked else "no rank yet")
        self.tiles["prs"].set(pr_count, "personal records")
        self.tiles["skills"].set(skills[0]["n"] if skills else 0, "skills completed")

        weeks = weekly_history(history, 12)
        labels = [w[0] for w in weeks]
        self.reps_chart.set_data(labels, [("reps", "#4dabf7", [w[2] for w in weeks])])
        self.hold_chart.set_data(labels, [("hold seconds", "#38d9a9", [w[3] for w in weeks])])
        self.workout_chart.set_data(labels, [("workouts", "#ff922b", [w[1] for w in weeks])])
        self.chart_note.setText("The last 12 calendar weeks. Only finished workouts that were really "
                                "performed are counted.")

        perf = exercise_performance(db, 8)
        self.compare.set_rows(perf)
        self.compare_note.setText("“now” is the most recent confirmed performance, “PR” is the best "
                                  "value ever recorded for that exercise. A PR is never overwritten by "
                                  "a weaker later set.")

        ms = recent_milestones(db, 8)
        if ms:
            lines = [f"<span style='color:#8b95a7'>{m['earned_on'][:10]}</span> "
                     f"<b>+{m['amount']} XP</b> {m['reason']}" for m in ms]
            self.milestones.setText("<br>".join(lines))
        else:
            self.milestones.setText("No XP awarded yet - finish a workout to start earning.")

        sk = recently_completed_skills(db, self.graph, 6)
        if sk:
            self.new_skills.setText("<br>".join(
                f"<span style='color:#8b95a7'>{s['updated']}</span> <b>{s['name']}</b>" for s in sk))
        else:
            self.new_skills.setText("No skill completed yet. Mark skills as completed in the skill tree.")
