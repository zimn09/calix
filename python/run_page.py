"""Running: log a run with its distance and time, see the pace and the history."""
import datetime as dt

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (QDateEdit, QDoubleSpinBox, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QPushButton, QScrollArea, QSpinBox, QVBoxLayout,
                               QWidget)

from run_repo import fmt_distance, fmt_pace, fmt_time, pace_seconds
from ui_common import Card, StatTile, confirm, plain, pretty_date


class RunPage(QWidget):
    runsChanged = Signal()

    def __init__(self, runs, parent=None):
        super().__init__(parent)
        self.runs = runs

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

        title = QLabel("Running")
        title.setObjectName("pageTitle")
        v.addWidget(title)

        tiles = QHBoxLayout()
        self.t_runs, self.t_dist = StatTile("Runs logged"), StatTile("Total distance")
        self.t_time, self.t_avg = StatTile("Total time"), StatTile("Average pace")
        self.t_best = StatTile("Best pace")
        for t in (self.t_runs, self.t_dist, self.t_time, self.t_avg, self.t_best):
            tiles.addWidget(t)
        v.addLayout(tiles)

        # ------------------------------------------------------------ log a run
        form = Card("Log a run")
        row = QHBoxLayout()
        row.setSpacing(8)

        self.in_km = QDoubleSpinBox()
        self.in_km.setDecimals(2)
        self.in_km.setRange(0.1, 200.0)
        self.in_km.setSingleStep(0.5)
        self.in_km.setSuffix(" km")
        self.in_km.setValue(5.0)
        self.in_km.setMinimumWidth(110)

        self.in_min = QSpinBox()
        self.in_min.setRange(0, 600)
        self.in_min.setSuffix(" min")
        self.in_min.setValue(25)
        self.in_sec = QSpinBox()
        self.in_sec.setRange(0, 59)
        self.in_sec.setSuffix(" s")

        self.in_date = QDateEdit()
        self.in_date.setCalendarPopup(True)
        self.in_date.setDisplayFormat("ddd d MMM yyyy")
        self.in_date.setDate(QDate.currentDate())

        for w in (QLabel("Distance"), self.in_km, QLabel("Time"), self.in_min, self.in_sec,
                  QLabel("Date"), self.in_date):
            if isinstance(w, QLabel):
                w.setObjectName("muted")
            row.addWidget(w)
        row.addStretch(1)
        form.lay.addLayout(row)

        pacerow = QHBoxLayout()
        self.pace_label = QLabel("")
        self.pace_label.setObjectName("bigValue")
        self.save = QPushButton("Save run")
        self.save.clicked.connect(self._save)
        pacerow.addWidget(self.pace_label, 1)
        pacerow.addWidget(self.save)
        form.lay.addLayout(pacerow)

        self.message = QLabel("")
        self.message.setObjectName("muted")
        self.message.setWordWrap(True)
        form.lay.addWidget(self.message)

        for w in (self.in_km, self.in_min, self.in_sec):
            w.valueChanged.connect(self._update_pace)
        v.addWidget(form)

        # -------------------------------------------------------------- history
        hist = Card("Runs")
        self.list = QListWidget()
        self.list.setMinimumHeight(260)
        hist.lay.addWidget(self.list)
        self.b_delete = QPushButton("Delete selected run")
        self.b_delete.setObjectName("danger")
        self.b_delete.clicked.connect(self._delete)
        hist.lay.addWidget(self.b_delete)
        v.addWidget(hist)
        v.addStretch(1)

        self._update_pace()
        self.refresh()

    # ------------------------------------------------------------------ tools
    def _duration(self):
        return self.in_min.value() * 60 + self.in_sec.value()

    def _update_pace(self, *_):
        pace = pace_seconds(self.in_km.value() * 1000, self._duration())
        self.pace_label.setText(f"Pace {fmt_pace(pace)} /km" if pace else "Pace –")
        self.save.setEnabled(self._duration() > 0 and self.in_km.value() > 0)

    def _save(self):
        km, secs = self.in_km.value(), self._duration()
        if km <= 0 or secs <= 0:
            self.message.setText("Enter a distance and a time above zero.")
            return
        d = self.in_date.date()
        day = dt.date(d.year(), d.month(), d.day())
        sid = self.runs.log(int(round(km * 1000)), secs, day)
        self.message.setText(f"Run saved – {fmt_distance(int(round(km * 1000)))} in "
                             f"{fmt_time(secs)} at {fmt_pace(pace_seconds(km * 1000, secs))} /km "
                             f"(session #{sid}).")
        self.in_min.setValue(0)
        self.in_sec.setValue(0)
        self.refresh()
        self.runsChanged.emit()

    def _delete(self):
        item = self.list.currentItem()
        if not item:
            return
        if confirm(self, "Delete run", "Delete this run? It will no longer count towards your "
                                      "history or statistics."):
            self.runs.delete(item.data(Qt.UserRole))
            self.message.setText("Run deleted.")
            self.refresh()
            self.runsChanged.emit()

    # ---------------------------------------------------------------- refresh
    def refresh(self):
        t = self.runs.totals()
        self.t_runs.set(t["count"])
        self.t_dist.set(fmt_distance(t["distance"]) if t["distance"] else "0 km",
                        f"{t['distance'] / 1000:.0f} km" if t["distance"] else "")
        self.t_time.set(fmt_time(t["seconds"]) if t["seconds"] else "0:00")
        self.t_avg.set(fmt_pace(t["average"]) + " /km" if t["average"] else "–")
        self.t_best.set(fmt_pace(t["best"]) + " /km" if t["best"] else "–",
                        "fastest run" if t["best"] else "")

        keep = self.list.currentItem().data(Qt.UserRole) if self.list.currentItem() else None
        self.list.blockSignals(True)
        self.list.clear()
        for r in self.runs.runs():
            day = pretty_date(dt.date.fromisoformat(r["session_date"]), True)
            pace = fmt_pace(pace_seconds(r["distance_m"], r["elapsed_sec"]))
            it = QListWidgetItem(f"{day}  ·  {fmt_distance(r['distance_m'])}  ·  "
                                 f"{fmt_time(r['elapsed_sec'])}  ·  {pace} /km")
            it.setData(Qt.UserRole, r["id"])
            self.list.addItem(it)
            if r["id"] == keep:
                self.list.setCurrentItem(it)
        self.list.blockSignals(False)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self.b_delete.setEnabled(self.list.count() > 0)
