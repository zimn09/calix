"""Workout History: past sessions plus statistics calculated from the saved data."""
import datetime as dt

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
                               QScrollArea, QTextBrowser, QVBoxLayout, QWidget)

import stats
from ui_common import BarChart, Card, Heatmap, StatTile, confirm, fmt_duration, plain, pretty_date


class HistoryPage(QWidget):
    historyChanged = Signal()

    def __init__(self, sess, srepo, parent=None):
        super().__init__(parent)
        self.sess, self.srepo = sess, srepo
        self.db = sess.db

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

        title = QLabel("Workout History")
        title.setObjectName("pageTitle")
        v.addWidget(title)

        tiles = QHBoxLayout()
        self.t_total, self.t_week = StatTile("Workouts completed"), StatTile("This week")
        self.t_avg, self.t_streak = StatTile("Avg per week"), StatTile("Current streak")
        self.t_sets, self.t_reps = StatTile("Sets completed"), StatTile("Total reps")
        self.t_hold, self.t_rate = StatTile("Total hold time"), StatTile("Set completion")
        for t in (self.t_total, self.t_week, self.t_avg, self.t_streak):
            tiles.addWidget(t)
        v.addLayout(tiles)
        tiles2 = QHBoxLayout()
        for t in (self.t_sets, self.t_reps, self.t_hold, self.t_rate):
            tiles2.addWidget(t)
        v.addLayout(tiles2)

        charts = QHBoxLayout()
        c1 = Card("Workouts per week (last 12 weeks)")
        self.bars = BarChart("#4dabf7")
        c1.lay.addWidget(self.bars)
        c2 = Card("Consistency (last 26 weeks)")
        self.heat = Heatmap(26)
        c2.lay.addWidget(self.heat)
        self.adherence = QLabel("")
        self.adherence.setObjectName("muted")
        self.adherence.setWordWrap(True)
        c2.lay.addWidget(self.adherence)
        c2.lay.addStretch(1)
        charts.addWidget(c1, 1)
        charts.addWidget(c2, 1)
        v.addLayout(charts)

        lower = QHBoxLayout()
        c3 = Card("Sessions")
        self.sessions = QListWidget()
        self.sessions.setMinimumHeight(260)
        self.sessions.currentItemChanged.connect(self._show_detail)
        self.detail = QTextBrowser()
        self.detail.setMinimumHeight(180)
        self.b_delete = QPushButton("Delete selected session")
        self.b_delete.setObjectName("danger")
        self.b_delete.clicked.connect(self._delete)
        c3.lay.addWidget(self.sessions)
        c3.lay.addWidget(self.detail)
        c3.lay.addWidget(self.b_delete)
        right = QVBoxLayout()
        c4 = Card("Most performed exercises")
        self.common = QLabel("")
        self.common.setTextFormat(Qt.RichText)
        self.common.setWordWrap(True)
        c4.lay.addWidget(self.common)
        c5 = Card("Personal records")
        self.prs = QLabel("")
        self.prs.setTextFormat(Qt.RichText)
        self.prs.setWordWrap(True)
        c5.lay.addWidget(self.prs)
        right.addWidget(c4)
        right.addWidget(c5)
        right.addStretch(1)
        lower.addWidget(c3, 3)
        lower.addLayout(right, 2)
        v.addLayout(lower)

        self.refresh()

    def refresh(self):
        today = dt.date.today()
        t = stats.totals(self.db)
        dates = stats.session_dates(self.db)
        comp = stats.completion(self.db)
        self.t_total.set(t["sessions"], f"{fmt_duration(t['seconds'])} of training" if t["sessions"] else "")
        self.t_week.set(stats.this_week(dates, today), "workouts since Monday")
        self.t_avg.set(f"{stats.avg_per_week(dates, today, 8):.1f}", "over the last 8 weeks")
        n = stats.streak(dates, today)
        self.t_streak.set(n, "day" if n == 1 else "days in a row")
        self.t_sets.set(t["sets"])
        self.t_reps.set(t["reps"])
        mins, secs = divmod(t["hold"], 60)
        self.t_hold.set(f"{mins}:{secs:02d}" if t["hold"] else "0", "min:sec held" if t["hold"] else "")
        if comp["pct"] is None:
            self.t_rate.set("–", "no finished sessions yet")
        else:
            self.t_rate.set(f"{comp['pct']:.0f}%", f"{comp['full']}/{comp['sessions']} sessions fully completed")

        self.bars.set_data([(f"{w.day}/{w.month}", n) for w, n in stats.weekly_counts(dates, today, 12)])
        self.heat.set_data(stats.day_counts(dates), today)
        done, total = stats.adherence(self.srepo, self.sess, today)
        self.adherence.setText(f"Schedule adherence, last 28 days: <b>{done}/{total}</b> planned workouts done "
                               f"({100 * done // total}%)" if total else
                               "Schedule adherence: no planned workouts in the last 28 days.")
        self.adherence.setTextFormat(Qt.RichText)

        top = stats.most_performed(self.db)
        self.common.setText("<br>".join(f"{i}. <b>{r['name']}</b> <span style='color:#8b95a7'>"
                                        f"{r['sessions']} session{'s' if r['sessions'] != 1 else ''}, {r['sets']} sets</span>"
                                        for i, r in enumerate(top, 1))
                            or "<span style='color:#8b95a7'>Complete a workout to see this.</span>")
        prs = stats.personal_records(self.db)
        self.prs.setText("<br>".join(f"<b>{r['name']}</b>: {r['best']:g} {r['unit']} "
                                     f"<span style='color:#6b7686'>({r['date']})</span>" for r in prs)
                         or "<span style='color:#8b95a7'>No records yet.</span>")

        keep = self.sessions.currentItem().data(Qt.UserRole) if self.sessions.currentItem() else None
        self.sessions.blockSignals(True)
        self.sessions.clear()
        for s in self.sess.history():
            d = dt.date.fromisoformat(s["session_date"])
            it = QListWidgetItem(f"{pretty_date(d, True)}  ·  {s['workout_name']}  ·  "
                                 f"{fmt_duration(s['elapsed_sec'])}  ·  {s['sets_done']}/{s['sets_total']} sets")
            it.setData(Qt.UserRole, s["id"])
            self.sessions.addItem(it)
            if s["id"] == keep:
                self.sessions.setCurrentItem(it)
        self.sessions.blockSignals(False)
        if self.sessions.currentItem() is None and self.sessions.count():
            self.sessions.setCurrentRow(0)
        self._show_detail(self.sessions.currentItem())

    def _show_detail(self, item, _prev=None):
        self.b_delete.setEnabled(item is not None)
        if item is None:
            self.detail.setHtml("<span style='color:#8b95a7'>No sessions yet. Finish a workout and it appears here.</span>")
            return
        sid = item.data(Qt.UserRole)
        s = self.sess.summary(sid)
        rows = self.sess.sets(sid)
        html = [f"<p><b style='font-size:12pt'>{s['workout_name']}</b><br><span style='color:#8b95a7'>"
                f"{fmt_duration(s['elapsed_sec'])} · {s['sets_done']}/{s['sets_total']} sets · "
                f"{s['reps_total']} reps · {s['hold_total']} s held</span></p>"]
        cur = None
        for r in rows:
            if r["exercise_name"] != cur or r["set_idx"] == 0:
                cur = r["exercise_name"]
                html.append(f"<p style='margin-bottom:0'><b>{cur}</b></p>")
            val = f"{r['hold']} s" if r["kind"] == "hold" else f"{r['reps']} reps"
            if r["done"]:
                html.append(f"<span style='color:#69db7c'>✓ Set {r['set_idx'] + 1}: {val}</span><br>")
            else:
                html.append(f"<span style='color:#6b7686'>○ Set {r['set_idx'] + 1}: skipped</span><br>")
        self.detail.setHtml("".join(html))

    def _delete(self):
        it = self.sessions.currentItem()
        if it and confirm(self, "Delete session", "Delete this session from your history? "
                                                  "Statistics will be recalculated."):
            self.sess.delete_session(it.data(Qt.UserRole))
            self.refresh()
            self.historyChanged.emit()
