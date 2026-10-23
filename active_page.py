"""Active Workout mode: set-by-set tracking, rest timer, pause/resume and a completion summary.

Everything is written to the database as you go (see sessions.py), so a session
that is interrupted or left open when the app closes can be resumed later.
"""
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QMessageBox, QProgressBar, QPushButton,
                               QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from exercises_data import DIFFICULTY, EX_CATEGORIES
from rank_widgets import PerformanceDialog, change_lines, rank_html
from schedule_page import TodayCard
from ui_common import Card, clear_layout, fmt_clock, fmt_duration, plain
from xp_widgets import ProgressionDialog, xp_result_html


class SummaryDialog(QDialog):
    def __init__(self, s, changes=None, xp_result=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Workout complete")
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        title = QLabel("Workout complete")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        pct = round(100 * s["sets_done"] / s["sets_total"]) if s["sets_total"] else 0
        parts = [f"<p style='font-size:12pt'><b>{s['workout_name']}</b></p>",
                 f"Time: <b>{fmt_duration(s['elapsed_sec'])}</b><br>"
                 f"Sets completed: <b>{s['sets_done']}/{s['sets_total']}</b> ({pct}%)<br>"
                 f"Exercises performed: <b>{s['exercises_done']}</b><br>"
                 f"Total reps: <b>{s['reps_total']}</b><br>"
                 f"Total hold time: <b>{s['hold_total']} s</b>"]
        if s["prs"]:
            parts.append("<p style='color:#ffd43b'><b>New personal records</b></p>" + "<br>".join(
                f"★ {p['name']}: <b>{p['value']:g} {p['unit']}</b> (was {p['previous']:g})" for p in s["prs"]))
        if changes:
            parts.append("<p style='color:#ffd43b'><b>Rank changes</b></p>" + "<br>".join(change_lines(changes)))
        xp_html = xp_result_html(xp_result)
        if xp_html:
            parts.append("<hr>" + xp_html)
        elif xp_result is not None:
            parts.append("<p style='color:#8b95a7'>No XP this time: a workout earns XP when at least half of its sets "
                         "are done, it lasts 2+ minutes, and it is one of the first 3 of the day.</p>")
        info = QLabel("".join(parts))
        info.setTextFormat(Qt.RichText)
        info.setWordWrap(True)
        lay.addWidget(info)
        b = QPushButton("Done")
        b.setObjectName("primary")
        b.clicked.connect(self.accept)
        lay.addWidget(b)


class ActiveWorkoutPage(QWidget):
    sessionChanged = Signal()

    def __init__(self, sess, wrepo, srepo, ranks, xp, parent=None):
        super().__init__(parent)
        self.sess, self.wrepo, self.srepo, self.ranks, self.xp = sess, wrepo, srepo, ranks, xp
        self.sid, self.groups, self.cur = None, [], 0
        self.elapsed, self.paused = 0.0, False
        self.rest_total = self.rest_left = 0.0
        self.rest_running = False
        self.hold_running, self.hold_elapsed = False, 0.0
        self._last, self._since_save = time.monotonic(), 0.0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        self.stack = QStackedWidget()
        self.stack.setObjectName("inner")
        self.stack.addWidget(self._build_idle())
        self.stack.addWidget(self._build_run())
        outer.addWidget(self.stack)

        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self._refresh_idle()

    # ================================================================ idle page
    def _build_idle(self):
        page = plain()
        row = QHBoxLayout(page)
        inner = plain()
        inner.setMaximumWidth(760)
        v = QVBoxLayout(inner)
        v.setSpacing(12)
        title = QLabel("Active Workout")
        title.setObjectName("pageTitle")
        v.addWidget(title)

        self.resume_card = Card("Session in progress")
        self.resume_label = QLabel("")
        self.resume_label.setTextFormat(Qt.RichText)
        r = QHBoxLayout()
        b_res, b_disc = QPushButton("Resume session"), QPushButton("Discard")
        b_res.setObjectName("primary")
        b_disc.setObjectName("danger")
        b_res.clicked.connect(self.resume)
        b_disc.clicked.connect(self._discard_saved)
        r.addWidget(b_res)
        r.addWidget(b_disc)
        r.addStretch(1)
        self.resume_card.lay.addWidget(self.resume_label)
        self.resume_card.lay.addLayout(r)

        self.today_card = TodayCard(self.srepo, self.sess, "Today's plan")
        self.today_card.startRequested.connect(self.start_workout)
        self.today_card.resumeRequested.connect(self.resume)

        pick = Card("Start a saved workout")
        pr = QHBoxLayout()
        self.pick = QComboBox()
        self.b_start = QPushButton("Start")
        self.b_start.setObjectName("success")
        self.b_start.clicked.connect(lambda: self.start_workout(self.pick.currentData()))
        pr.addWidget(self.pick, 1)
        pr.addWidget(self.b_start)
        pick.lay.addLayout(pr)
        self.pick_hint = QLabel("")
        self.pick_hint.setObjectName("muted")
        pick.lay.addWidget(self.pick_hint)

        for w in (self.resume_card, self.today_card, pick):
            v.addWidget(w)
        v.addStretch(1)
        row.addStretch(1)
        row.addWidget(inner, 10)
        row.addStretch(1)
        return page

    def _refresh_idle(self):
        act = self.sess.active()
        self.resume_card.setVisible(bool(act))
        if act:
            self.resume_label.setText(f"<b>{act['workout_name']}</b><br><span style='color:#8b95a7'>Started "
                                      f"{act['started'][:16].replace('T', ' ')} · {fmt_duration(act['elapsed_sec'])} "
                                      f"of training so far</span>")
        self.today_card.refresh()
        current = self.pick.currentData()
        self.pick.clear()
        for w in self.wrepo.workouts():
            if w["n"]:
                self.pick.addItem(f"{w['name']}  ({w['n']} exercises)", w["id"])
        if current is not None:
            self.pick.setCurrentIndex(max(0, self.pick.findData(current)))
        has = self.pick.count() > 0
        self.b_start.setEnabled(has and act is None)
        self.pick_hint.setText("" if has else "No workouts yet. Create one in the Workout Builder.")

    def refresh(self):
        if self.sid is None:
            self._refresh_idle()

    def _discard_saved(self):
        act = self.sess.active()
        if act and QMessageBox.question(self, "Discard session",
                                        "Discard the unfinished session? Nothing from it will be saved.") == QMessageBox.Yes:
            self.sess.discard(act["id"])
            self._refresh_idle()
            self.sessionChanged.emit()

    # ================================================================== run page
    def _build_run(self):
        page = plain()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        top = QHBoxLayout()
        self.run_title = QLabel("")
        self.run_title.setObjectName("pageTitle")
        self.status = QLabel("")
        self.clock = QLabel("00:00")
        self.clock.setObjectName("clock")
        self.b_pause, self.b_end = QPushButton("Pause"), QPushButton("End session")
        self.b_end.setObjectName("danger")
        self.b_pause.clicked.connect(self._toggle_pause)
        self.b_end.clicked.connect(self._end)
        top.addWidget(self.run_title, 1)
        top.addWidget(self.status)
        top.addSpacing(10)
        top.addWidget(self.clock)
        top.addSpacing(10)
        top.addWidget(self.b_pause)
        top.addWidget(self.b_end)
        root.addLayout(top)

        prog = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("QProgressBar::chunk { background: #69db7c; }")
        self.progress_label = QLabel("")
        self.progress_label.setObjectName("muted")
        prog.addWidget(self.progress, 1)
        prog.addWidget(self.progress_label)
        root.addLayout(prog)

        body = QHBoxLayout()
        body.setSpacing(12)
        self.ex_list = QListWidget()
        self.ex_list.setFixedWidth(250)
        self.ex_list.currentRowChanged.connect(self._goto)
        body.addWidget(self.ex_list)

        center = Card()
        self.ex_name = QLabel("")
        self.ex_name.setStyleSheet("font-size: 20pt; font-weight: 800;")
        self.ex_name.setWordWrap(True)
        self.ex_meta = QLabel("")
        self.ex_meta.setTextFormat(Qt.RichText)
        self.ex_rank = QLabel("")
        self.ex_rank.setTextFormat(Qt.RichText)
        self.ex_rank.setWordWrap(True)
        self.ex_how = QLabel("")
        self.ex_how.setWordWrap(True)
        self.ex_how.setStyleSheet("color: #aab4c3; font-size: 10.5pt;")
        self.ex_note = QLabel("")
        self.ex_note.setWordWrap(True)
        self.ex_note.setStyleSheet("color: #ffa94d;")
        self.sets_box = plain()
        self.sets_grid = QGridLayout(self.sets_box)
        self.sets_grid.setContentsMargins(0, 6, 0, 6)
        self.sets_grid.setVerticalSpacing(8)
        nav = QHBoxLayout()
        self.b_prev, self.b_next = QPushButton("◀  Previous exercise"), QPushButton("Next exercise  ▶")
        self.b_prev.clicked.connect(lambda: self._step(-1))
        self.b_next.clicked.connect(lambda: self._step(1))
        nav.addWidget(self.b_prev)
        nav.addStretch(1)
        nav.addWidget(self.b_next)
        for w in (self.ex_name, self.ex_meta, self.ex_rank, self.ex_how, self.ex_note, self.sets_box):
            center.lay.addWidget(w)
        center.lay.addStretch(1)
        center.lay.addLayout(nav)
        body.addWidget(center, 1)

        timer_card = Card("Timer")
        timer_card.setFixedWidth(270)
        self.t_title = QLabel("Rest")
        self.t_title.setAlignment(Qt.AlignCenter)
        self.t_title.setObjectName("muted")
        self.t_title.setWordWrap(True)
        self.t_clock = QLabel("00:00")
        self.t_clock.setObjectName("bigTime")
        self.t_clock.setAlignment(Qt.AlignCenter)
        self.t_bar = QProgressBar()
        self.t_bar.setTextVisible(False)
        self.t_bar.setStyleSheet("QProgressBar::chunk { background: #ffa94d; }")
        self.b_rest, self.b_skip, self.b_add = QPushButton("Start rest"), QPushButton("Skip rest"), QPushButton("+15 s")
        self.b_rest.setObjectName("primary")
        self.b_rest.clicked.connect(self._rest_toggle)
        self.b_skip.clicked.connect(self._rest_skip)
        self.b_add.clicked.connect(self._rest_add)
        self.b_hold = QPushButton("Start hold stopwatch")
        self.b_hold.clicked.connect(self._hold_toggle)
        small = QHBoxLayout()
        small.addWidget(self.b_skip)
        small.addWidget(self.b_add)
        for w in (self.t_title, self.t_clock, self.t_bar, self.b_rest):
            timer_card.lay.addWidget(w)
        timer_card.lay.addLayout(small)
        timer_card.lay.addWidget(self.b_hold)
        timer_card.lay.addStretch(1)
        body.addWidget(timer_card)
        root.addLayout(body, 1)
        return page

    # ----------------------------------------------------------- session control
    def start_workout(self, workout_id, entry_id=None):
        """Start a workout (handling an already-running session). Returns True if a session is now open."""
        if workout_id is None:
            return False
        act = self.sess.active()
        if act:
            if self.sid == act["id"]:
                return True
            box = QMessageBox(self)
            box.setWindowTitle("Session already in progress")
            box.setText(f"“{act['workout_name']}” is still in progress.")
            res = box.addButton("Resume it", QMessageBox.AcceptRole)
            new = box.addButton("Discard it and start new", QMessageBox.DestructiveRole)
            box.addButton("Cancel", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() == res:
                self.resume()
                return True
            if box.clickedButton() != new:
                return False
            self.sess.discard(act["id"])
        try:
            sid = self.sess.start(workout_id, entry_id)
        except ValueError as exc:
            QMessageBox.warning(self, "Can't start", str(exc))
            return False
        self._open(sid, resume=False)
        self.sessionChanged.emit()
        return True

    def resume(self):
        act = self.sess.active()
        if act and self.sid != act["id"]:
            self._open(act["id"], resume=True)
        elif act:
            self.stack.setCurrentIndex(1)

    def _open(self, sid, resume):
        row = self.sess.active()
        state = self.sess.load_state(row)
        self.sid = sid
        self.groups = self._group(self.sess.sets(sid))
        self.elapsed = float(row["elapsed_sec"])
        self.cur = min(max(0, int(state.get("ex_pos", 0))), len(self.groups) - 1)
        self.paused = resume                      # a resumed session waits for you to press Resume
        self.rest_left = float(state.get("rest_left", 0)) if resume else 0.0
        self.rest_total = float(state.get("rest_total", 0)) if resume else 0.0
        self.rest_running, self.hold_running = False, False
        self.run_title.setText(row["workout_name"])
        self._last = time.monotonic()
        self._rebuild_list()
        self._show_exercise()
        self.stack.setCurrentIndex(1)
        self._update_pause_ui()

    @staticmethod
    def _group(rows):
        groups = []
        for r in rows:
            if not groups or groups[-1]["pos"] != r["ex_pos"]:
                groups.append(dict(pos=r["ex_pos"], exercise_id=r["exercise_id"], name=r["exercise_name"],
                                   kind=r["kind"], note=r["note"], sets=[]))
            groups[-1]["sets"].append(r)
        return groups

    def persist(self):
        """Save timer/position so the session can be resumed (also called when the app closes)."""
        if self.sid is not None:
            self.sess.save_state(self.sid, self.elapsed, dict(ex_pos=self.cur, rest_left=self.rest_left,
                                                              rest_total=self.rest_total))

    def _close_session(self):
        self.sid, self.groups = None, []
        self.rest_left = self.rest_total = 0.0
        self.rest_running = self.hold_running = False
        self.stack.setCurrentIndex(0)
        self._refresh_idle()
        self.sessionChanged.emit()

    def _all_done(self):
        return bool(self.groups) and all(s["done"] for g in self.groups for s in g["sets"])

    def _end(self):
        done = sum(s["done"] for g in self.groups for s in g["sets"])
        total = sum(len(g["sets"]) for g in self.groups)
        self.paused = True
        self._update_pause_ui()
        box = QMessageBox(self)
        box.setWindowTitle("End session")
        box.setText(f"{done} of {total} sets completed.")
        fin = box.addButton("Save && finish", QMessageBox.AcceptRole) if done else None
        disc = box.addButton("Discard session", QMessageBox.DestructiveRole)
        keep = box.addButton("Keep going", QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if fin is not None and clicked == fin:
            self.persist()
            sid = self.sid
            summary = self.sess.finish(sid, self.elapsed)
            changes = self._confirm_performances(sid) if summary else []
            xp_result = self.xp.sync() if summary else None      # credits this workout (and any new rank/record) once
            self._close_session()
            if summary:
                SummaryDialog(summary, changes, xp_result, self).exec()
                if xp_result.leveled_up:
                    ProgressionDialog(xp_result, self, show_awards=False).exec()
        elif clicked == disc:
            self.sess.discard(self.sid)
            self._close_session()
        else:
            self.paused = False
            self._last = time.monotonic()
            self._update_pause_ui()

    def _confirm_performances(self, sid):
        """Let the user confirm (or correct) the best set of each exercise. Only confirmed values affect ranks."""
        items = [b for b in self.sess.best_sets(sid) if b["exercise_id"] in self.ranks.by_exercise]
        if not items:
            return []
        dlg = PerformanceDialog(self.ranks, items, self)
        if dlg.exec() != QDialog.Accepted:
            return []
        return self.ranks.record_session(sid, dlg.accepted_items())

    # ------------------------------------------------------------ exercise view
    def _rebuild_list(self):
        self.ex_list.blockSignals(True)
        self.ex_list.clear()
        for i, g in enumerate(self.groups):
            self.ex_list.addItem(QListWidgetItem(self._list_text(i, g)))
        self.ex_list.setCurrentRow(self.cur)
        self.ex_list.blockSignals(False)

    @staticmethod
    def _list_text(i, g):
        done = sum(s["done"] for s in g["sets"])
        return f"{'✓ ' if done == len(g['sets']) else ''}{i + 1}. {g['name']}   {done}/{len(g['sets'])}"

    def _goto(self, i):
        if self.sid is not None and 0 <= i < len(self.groups) and i != self.cur:
            self.cur = i
            self._show_exercise()
            self.persist()

    def _step(self, d):
        if d > 0 and self.cur == len(self.groups) - 1:
            self._end()
        elif 0 <= self.cur + d < len(self.groups):
            self.cur += d
            self._show_exercise()
            self.persist()

    def _show_exercise(self):
        g = self.groups[self.cur]
        ex = self.wrepo.exercise(g["exercise_id"])
        self.ex_name.setText(g["name"])
        if ex:
            label, color = EX_CATEGORIES[ex["category"]]
            self.ex_meta.setText(f"<span style='color:{color}'>● {label}</span> &nbsp; "
                                 f"<span style='color:#9aa4b2'>◆ {DIFFICULTY[ex['difficulty']]}</span> &nbsp; "
                                 f"<span style='color:#9aa4b2'>{'hold for time' if g['kind'] == 'hold' else 'reps'}</span>")
            self.ex_how.setText(ex["instructions"])
        else:
            self.ex_meta.setText("")
            self.ex_how.setText("")
        res = self.ranks.result_for_exercise(g["exercise_id"])
        self.ex_rank.setVisible(res is not None)
        if res is not None:
            self.ex_rank.setText(f"Rank: {rank_html(res.rank)} &nbsp;<span style='color:#8b95a7'>{res.headline} · "
                                 f"next: {res.goal}</span>")
        self.ex_note.setText(f"Note: {g['note']}" if g["note"] else "")
        self.ex_note.setVisible(bool(g["note"]))
        self.ex_list.blockSignals(True)
        self.ex_list.setCurrentRow(self.cur)
        self.ex_list.blockSignals(False)
        self.b_prev.setEnabled(self.cur > 0)
        self.b_next.setText("Finish workout  ▶" if self.cur == len(self.groups) - 1 else "Next exercise  ▶")
        self.b_hold.setVisible(g["kind"] == "hold")
        self._render_sets()
        self._update_progress()

    def _render_sets(self):
        clear_layout(self.sets_grid)
        g = self.groups[self.cur]
        first = next((i for i, s in enumerate(g["sets"]) if not s["done"]), None)
        is_hold = g["kind"] == "hold"
        for c, text in enumerate(("Set", "Hold" if is_hold else "Reps", "Rest after", "")):
            h = QLabel(text.upper())
            h.setObjectName("sectionTitle")
            self.sets_grid.addWidget(h, 0, c)
        for r, s in enumerate(g["sets"], start=1):
            lab = QLabel(f"Set {r}")
            color = "#69db7c" if s["done"] else "#ffd43b" if r - 1 == first else "#c9d1d9"
            lab.setStyleSheet(f"color: {color}; font-weight: 700; font-size: 11pt;")
            spin = QSpinBox()
            spin.setRange(0, 900 if is_hold else 999)
            spin.setSuffix(" s" if is_hold else " reps")
            spin.setValue(s["hold"] if is_hold else s["reps"])
            spin.valueChanged.connect(lambda v, s=s, f=("hold" if is_hold else "reps"): self._set_field(s, f, v))
            rest = QSpinBox()
            rest.setRange(0, 900)
            rest.setSuffix(" s")
            rest.setValue(s["rest_sec"])
            rest.valueChanged.connect(lambda v, s=s: self._set_field(s, "rest_sec", v))
            btn = QPushButton("✓ Done (undo)" if s["done"] else "Complete set")
            btn.setObjectName("" if s["done"] else "primary")
            btn.clicked.connect(lambda _=False, s=s: self._toggle_done(s))
            for c, w in enumerate((lab, spin, rest, btn)):
                self.sets_grid.addWidget(w, r, c)
        self.sets_grid.setColumnStretch(3, 1)

    def _set_field(self, s, field, value):
        s[field] = value
        self.sess.update_set(s["id"], **{field: value})

    def _toggle_done(self, s):
        s["done"] = 0 if s["done"] else 1
        self.sess.update_set(s["id"], done=s["done"], reps=s["reps"], hold=s["hold"], rest_sec=s["rest_sec"])
        g = self.groups[self.cur]
        if s["done"] and s["rest_sec"] > 0:
            self.rest_total = self.rest_left = float(s["rest_sec"])
            self.rest_running = not self.paused
            self.t_title.setText(f"Rest after {g['name']}, set {s['set_idx'] + 1}")
        elif not s["done"]:
            self.rest_left, self.rest_running = 0.0, False
        self.ex_list.item(self.cur).setText(self._list_text(self.cur, g))
        self._render_sets()
        self._update_progress()
        self._update_timer_ui()
        self.persist()

    def _update_progress(self):
        total = sum(len(g["sets"]) for g in self.groups)
        done = sum(s["done"] for g in self.groups for s in g["sets"])
        self.progress.setMaximum(max(1, total))
        self.progress.setValue(done)
        self.progress_label.setText(f"Exercise {self.cur + 1}/{len(self.groups)}  ·  {done}/{total} sets")
        self.b_end.setText("Finish workout" if self._all_done() else "End session")
        self.b_end.setObjectName("success" if self._all_done() else "danger")
        self.b_end.style().unpolish(self.b_end)
        self.b_end.style().polish(self.b_end)

    # ------------------------------------------------------------------ timers
    def _toggle_pause(self):
        self.paused = not self.paused
        self._last = time.monotonic()
        self._update_pause_ui()
        self.persist()

    def _update_pause_ui(self):
        self.b_pause.setText("Resume" if self.paused else "Pause")
        self.b_pause.setObjectName("primary" if self.paused else "")
        self.b_pause.style().unpolish(self.b_pause)
        self.b_pause.style().polish(self.b_pause)
        self.status.setText("⏸ PAUSED" if self.paused else "● In progress")
        self.status.setStyleSheet(f"color: {'#ffa94d' if self.paused else '#69db7c'}; font-weight: 700;")
        self._update_timer_ui()

    def _rest_default(self):
        g = self.groups[self.cur]
        done = [s for s in g["sets"] if s["done"]]
        return float((done[-1] if done else g["sets"][0])["rest_sec"] or 60)

    def _rest_toggle(self):
        if self.rest_left > 0:
            self.rest_running = not self.rest_running
        else:
            self.rest_total = self.rest_left = self._rest_default()
            self.rest_running = True
            self.t_title.setText("Rest")
        self._update_timer_ui()

    def _rest_skip(self):
        self.rest_left, self.rest_running = 0.0, False
        self._update_timer_ui()

    def _rest_add(self):
        self.rest_left += 15
        self.rest_total = max(self.rest_total, self.rest_left)
        self.rest_running = True
        self._update_timer_ui()

    def _hold_toggle(self):
        if not self.hold_running:
            self.hold_running, self.hold_elapsed = True, 0.0
        else:
            self.hold_running = False
            g = self.groups[self.cur]
            target = next((s for s in g["sets"] if not s["done"]), g["sets"][-1])
            self._set_field(target, "hold", int(round(self.hold_elapsed)))
            self._render_sets()
        self._update_timer_ui()

    def _update_timer_ui(self):
        if self.sid is None:
            return
        if self.hold_running:
            self.t_title.setText("Hold stopwatch (counting up)")
            self.t_clock.setText(fmt_clock(self.hold_elapsed))
            self.t_bar.setValue(0)
            self.b_hold.setText("Stop and use this time")
        else:
            self.b_hold.setText("Start hold stopwatch")
            left = int(self.rest_left + 0.999)
            self.t_clock.setText(fmt_clock(left))
            self.t_bar.setMaximum(max(1, int(self.rest_total)))
            self.t_bar.setValue(left)
            if self.rest_left <= 0:
                self.t_title.setText("No rest running" if self.rest_total == 0 else "Rest over. Go!")
        self.b_rest.setText("Pause rest" if self.rest_running else "Resume rest" if self.rest_left > 0 else "Start rest")
        self.b_skip.setEnabled(self.rest_left > 0)

    def _tick(self):
        now = time.monotonic()
        dt_, self._last = now - self._last, now
        if self.sid is None:
            return
        if not self.paused:
            self.elapsed += dt_
            if self.rest_running:
                self.rest_left -= dt_
                if self.rest_left <= 0:
                    self.rest_left, self.rest_running = 0.0, False
                    QApplication.beep()
            if self.hold_running:
                self.hold_elapsed += dt_
            self._since_save += dt_
            if self._since_save >= 5:
                self._since_save = 0.0
                self.persist()
        self.clock.setText(fmt_clock(self.elapsed))
        self._update_timer_ui()
