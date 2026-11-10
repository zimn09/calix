"""Dashboard: today's plan, upcoming sessions, training stats and skill-tree progress in one place."""
import datetime as dt

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

import stats
from panels import StatsPanel
from ranks_page import overview_html
from schedule_page import TodayCard, occ_color
import achievements as AC
from xp_widgets import LevelCard
from ui_common import Card, Heatmap, StatTile, fmt_duration, plain, pretty_date


class DashboardPage(QWidget):
    navigate = Signal(str)                    # "tree" | "builder" | "schedule" | "active" | "history" | "ranks" | "achievements"
    startRequested = Signal(int, object)
    resumeRequested = Signal()
    skillLink = Signal(str)

    def __init__(self, graph, store, sess, srepo, ranks, xp, parent=None):
        super().__init__(parent)
        self.store, self.sess, self.srepo, self.ranks, self.xp = store, sess, srepo, ranks, xp

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("pageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer.addWidget(scroll)
        body = plain()
        scroll.setWidget(body)
        v = QVBoxLayout(body)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(12)

        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        v.addWidget(title)

        self.level_card = LevelCard(xp)
        v.addWidget(self.level_card)

        tiles = QHBoxLayout()
        self.t_total, self.t_week = StatTile("Workouts completed"), StatTile("This week")
        self.t_streak, self.t_skills = StatTile("Current streak"), StatTile("Skills completed")
        for t in (self.t_total, self.t_week, self.t_streak, self.t_skills):
            tiles.addWidget(t)
        v.addLayout(tiles)

        cols = QHBoxLayout()
        cols.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(12)
        self.today = TodayCard(srepo, sess, "Today")
        self.today.startRequested.connect(self.startRequested.emit)
        self.today.resumeRequested.connect(self.resumeRequested.emit)
        up = Card("Coming up")
        self.up_label = QLabel("")
        self.up_label.setTextFormat(Qt.RichText)
        self.up_label.setWordWrap(True)
        up.lay.addWidget(self.up_label)
        rk = Card("Ranks")
        self.rank_label = QLabel("")
        self.rank_label.setTextFormat(Qt.RichText)
        self.rank_label.setWordWrap(True)
        b_rank = QPushButton("Open all ranks")
        b_rank.clicked.connect(lambda: self.navigate.emit("ranks"))
        rk.lay.addWidget(self.rank_label)
        rk.lay.addWidget(b_rank)
        ac = Card("Closest achievements")
        self.ach_label = QLabel("")
        self.ach_label.setTextFormat(Qt.RichText)
        self.ach_label.setWordWrap(True)
        b_ach = QPushButton("Open all achievements")
        b_ach.clicked.connect(lambda: self.navigate.emit("achievements"))
        ac.lay.addWidget(self.ach_label)
        ac.lay.addWidget(b_ach)
        cons = Card("Training consistency")
        self.heat = Heatmap(26)
        cons.lay.addWidget(self.heat)
        quick = Card("Go to")
        row = QHBoxLayout()
        for text, key in (("Skill Tree", "tree"), ("Build a workout", "builder"), ("Schedule", "schedule"),
                          ("History", "history")):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, k=key: self.navigate.emit(k))
            row.addWidget(b)
        quick.lay.addLayout(row)
        for w in (self.today, ac, rk, up, cons, quick):
            left.addWidget(w)
        left.addStretch(1)

        skills = Card("Skill progress")
        self.skill_panel = StatsPanel(graph, store, xp.profile, show_level=False)
        self.skill_panel.setMinimumHeight(480)
        self.skill_panel.skillLink.connect(self.skillLink.emit)
        skills.lay.addWidget(self.skill_panel)
        cols.addLayout(left, 1)
        cols.addWidget(skills, 1)
        v.addLayout(cols)
        self.graph = graph
        self.refresh()

    def refresh(self):
        today = dt.date.today()
        dates = stats.session_dates(self.sess.db)
        progress = self.store.progress()
        t = stats.totals(self.sess.db)
        self.t_total.set(t["sessions"], f"{fmt_duration(t['seconds'])} total" if t["sessions"] else "")
        self.t_week.set(stats.this_week(dates, today), f"{stats.avg_per_week(dates, today, 8):.1f} avg / week")
        n = stats.streak(dates, today)
        self.t_streak.set(n, "day" if n == 1 else "days in a row")
        done = sum(1 for sid in self.graph.order if self.graph.status(sid, progress) == "completed")
        self.t_skills.set(f"{done}/{len(self.graph.order)}", "in the skill tree")
        self.today.refresh()
        end = today + dt.timedelta(days=14)
        items = self.srepo.upcoming(today, 14, self.sess.completed_on(today, end), 5)
        self.up_label.setText("<br>".join(
            f"<span style='color:{occ_color(o)}'>●</span> <b>{pretty_date(o['date'])}</b> &nbsp;{o['workout_name']}"
            for o in items) or "<span style='color:#8b95a7'>Nothing scheduled. Plan your week in the Schedule tab.</span>")
        self.heat.set_data(stats.day_counts(dates), today)
        self.skill_panel.refresh(progress)
        self.level_card.refresh()
        lines = []
        for r in self.xp.nearest(3):
            a = r["a"]
            lines.append(f"<span style='color:{AC.RARITIES[a.rarity][1]}'>{a.icon} <b>{a.name}</b></span> "
                         f"<span style='color:#8b95a7'>{a.description}</span><br>"
                         f"<span style='color:#6b7686'>{r['progress']:g} / {a.target:g} {a.unit} · +{a.xp} XP</span>")
        self.ach_label.setText("<br><br>".join(lines) or "<span style='color:#8b95a7'>Every achievement is unlocked. Impressive!</span>")
        self.rank_label.setText(overview_html(self.ranks.results()))
