"""Workout Schedule: weekly/monthly calendar, weekly routines, one-time sessions and rest days."""
import calendar
import datetime as dt

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QComboBox, QDateEdit, QDialog,
                               QDialogButtonBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QStackedWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from scheduling import WEEKDAYS, install_example_routine
from ui_common import Card, chip, clear_layout, confirm, plain, pretty_date
from workouts import STYLE_COLORS

REST_COLOR, DONE_COLOR = "#7a8aa6", "#69db7c"


def occ_color(o):
    return REST_COLOR if o["is_rest"] else DONE_COLOR if o["done"] else STYLE_COLORS.get(o["style"], "#4dabf7")


def occ_label(o, short=False):
    if o["is_rest"]:
        return "☾ Rest day"
    name = o["workout_name"] or "Workout"
    if short and len(name) > 14:
        name = name[:13] + "…"
    return ("✓ " if o["done"] else "") + name


def qdate(d):
    return QDate(d.year, d.month, d.day)


class EntryDialog(QDialog):
    """Add or edit a schedule entry: a workout or a rest day, one-time or every week."""

    def __init__(self, wrepo, parent=None, day=None, entry=None, weekly=False):
        super().__init__(parent)
        self.setWindowTitle("Edit schedule entry" if entry else "Add to schedule")
        self.setMinimumWidth(380)
        day = day or dt.date.today()
        form = QFormLayout(self)
        self.type = QComboBox()
        self.type.addItem("Workout", False)
        self.type.addItem("Rest day", True)
        self.workout = QComboBox()
        for w in wrepo.workouts():
            self.workout.addItem(w["name"], w["id"])
        self.repeat = QComboBox()
        self.repeat.addItem("One time", "once")
        self.repeat.addItem("Every week", "weekly")
        self.date = QDateEdit(qdate(day))
        self.date.setCalendarPopup(True)
        self.weekday = QComboBox()
        for i, n in enumerate(WEEKDAYS):
            self.weekday.addItem(n, i)
        self.weekday.setCurrentIndex(day.weekday())
        self.note = QLineEdit()
        self.note.setPlaceholderText("Optional note")
        if entry:
            self.type.setCurrentIndex(1 if entry["is_rest"] else 0)
            i = self.workout.findData(entry["workout_id"])
            if i >= 0:
                self.workout.setCurrentIndex(i)
            self.repeat.setCurrentIndex(1 if entry["kind"] == "weekly" else 0)
            if entry["kind"] == "weekly":
                self.weekday.setCurrentIndex(entry["weekday"])
            else:
                self.date.setDate(qdate(dt.date.fromisoformat(entry["on_date"])))
            self.note.setText(entry["note"])
        elif weekly:
            self.repeat.setCurrentIndex(1)
        self.rows = {}
        for label, w in (("Type", self.type), ("Workout", self.workout), ("Repeat", self.repeat),
                         ("Date", self.date), ("Day of week", self.weekday), ("Note", self.note)):
            form.addRow(label, w)
            self.rows[label] = w
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self._ok)
        box.rejected.connect(self.reject)
        form.addRow(box)
        self._form = form
        self.type.currentIndexChanged.connect(self._toggle)
        self.repeat.currentIndexChanged.connect(self._toggle)
        self._toggle()

    def _toggle(self):
        rest, weekly = self.type.currentData(), self.repeat.currentData() == "weekly"
        self.workout.setEnabled(not rest)
        self.date.setVisible(not weekly)
        self._form.labelForField(self.date).setVisible(not weekly)
        self.weekday.setVisible(weekly)
        self._form.labelForField(self.weekday).setVisible(weekly)

    def _ok(self):
        if not self.type.currentData() and self.workout.currentData() is None:
            QMessageBox.information(self, "No workouts yet",
                                    "Create a workout in the Workout Builder first, or schedule a rest day.")
            return
        self.accept()

    def values(self):
        rest = self.type.currentData()
        return dict(kind=self.repeat.currentData(), weekday=self.weekday.currentData(),
                    on_date=self.date.date().toPython(), workout_id=None if rest else self.workout.currentData(),
                    is_rest=rest, note=self.note.text())


class MoveDialog(QDialog):
    def __init__(self, current, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reschedule")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Move this session to:"))
        self.date = QDateEdit(qdate(current))
        self.date.setCalendarPopup(True)
        lay.addWidget(self.date)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    @staticmethod
    def pick(parent, current):
        d = MoveDialog(current, parent)
        return d.date.date().toPython() if d.exec() == QDialog.Accepted else None


class RoutineDialog(QDialog):
    """Edit the repeating weekly routine."""

    def __init__(self, srepo, wrepo, parent=None):
        super().__init__(parent)
        self.srepo, self.wrepo, self.changed = srepo, wrepo, False
        self.setWindowTitle("Weekly routine")
        self.setMinimumSize(560, 420)
        lay = QVBoxLayout(self)
        hint = QLabel("These sessions repeat every week. Days without an entry are free days.")
        hint.setObjectName("muted")
        lay.addWidget(hint)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Day", "Plan", "Note"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 110)
        self.table.setColumnWidth(1, 220)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemDoubleClicked.connect(lambda *_: self._edit())
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        for text, fn, name in (("Add…", self._add, "primary"), ("Edit…", self._edit, None),
                               ("Remove", self._remove, "danger"), ("Load example routine", self._example, None),
                               ("Clear all", self._clear, "danger")):
            b = QPushButton(text)
            if name:
                b.setObjectName(name)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        lay.addWidget(close)
        self._fill()

    def _fill(self):
        entries = self.srepo.weekly_entries()
        self.table.setRowCount(len(entries))
        for r, e in enumerate(entries):
            plan = "☾ Rest day" if e["is_rest"] else (e["workout_name"] or "?")
            for c, text in enumerate((WEEKDAYS[e["weekday"]], plan, e["note"])):
                it = QTableWidgetItem(text)
                it.setData(Qt.UserRole, e["id"])
                self.table.setItem(r, c, it)

    def _current(self):
        r = self.table.currentRow()
        return self.table.item(r, 0).data(Qt.UserRole) if r >= 0 else None

    def _add(self):
        dlg = EntryDialog(self.wrepo, self, weekly=True)
        if dlg.exec() == QDialog.Accepted:
            v = dlg.values()
            v["kind"] = "weekly"        # this dialog only manages repeating entries
            self.srepo.add_entry(**v)
            self.changed = True
            self._fill()

    def _edit(self):
        eid = self._current()
        if eid is None:
            return
        dlg = EntryDialog(self.wrepo, self, entry=self.srepo.entry(eid))
        if dlg.exec() == QDialog.Accepted:
            self.srepo.update_entry(eid, **dlg.values())
            self.changed = True
            self._fill()

    def _remove(self):
        eid = self._current()
        if eid is not None:
            self.srepo.delete_entry(eid)
            self.changed = True
            self._fill()

    def _example(self):
        install_example_routine(self.wrepo, self.srepo)
        self.changed = True
        self._fill()

    def _clear(self):
        if self.table.rowCount() and confirm(self, "Clear routine", "Remove every weekly entry?"):
            self.srepo.clear_weekly()
            self.changed = True
            self._fill()


class DayCell(QFrame):
    clicked = Signal(object)

    def __init__(self, day, occs, today, selected, compact, in_month=True):
        super().__init__()
        self.day = day
        self.setObjectName("dayCell")
        self.setCursor(Qt.PointingHandCursor)
        rest = bool(occs) and all(o["is_rest"] for o in occs)
        work = any(not o["is_rest"] for o in occs)
        bg = "#101a2a" if work else "#131722" if rest else "#0d1118"
        border, width, style = "#1c2431", 1, "solid"
        if rest:
            border, style = "#3a4458", "dashed"
        if day == today:
            border, width, style = "#4dabf7", 2, "solid"
        if day == selected:
            border, width, style = "#e6e9ef", 2, "solid"
        self.setStyleSheet(f"QFrame#dayCell {{ background: {bg}; border: {width}px {style} {border}; "
                           f"border-radius: 10px; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)
        head = QLabel(f"{day.strftime('%a')}  {day.day}" if not compact else str(day.day))
        dim = "#4b5565" if not in_month else "#4dabf7" if day == today else "#c9d1d9"
        head.setStyleSheet(f"color: {dim}; font-weight: 700;")
        lay.addWidget(head)
        limit = 2 if compact else 99
        for o in occs[:limit]:
            lay.addWidget(chip(occ_label(o, compact), occ_color(o), filled=not o["is_rest"]))
        if len(occs) > limit:
            more = QLabel(f"+{len(occs) - limit} more")
            more.setObjectName("muted")
            lay.addWidget(more)
        lay.addStretch(1)
        self.setMinimumHeight(86 if compact else 250)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.day)


class TodayCard(Card):
    """Today's plan with Start buttons. Used on the Schedule page and the Dashboard."""
    startRequested = Signal(int, object)
    resumeRequested = Signal()

    def __init__(self, srepo, sess, title="Today", parent=None):
        super().__init__(title, parent)
        self.srepo, self.sess = srepo, sess
        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        self.lay.addLayout(self.body)

    def refresh(self):
        clear_layout(self.body)
        today = dt.date.today()
        act = self.sess.active()
        if act:
            row = QHBoxLayout()
            lab = QLabel(f"<b>In progress:</b> {act['workout_name']}")
            lab.setStyleSheet("color: #ffa94d;")
            b = QPushButton("Resume")
            b.setObjectName("primary")
            b.clicked.connect(self.resumeRequested.emit)
            row.addWidget(lab, 1)
            row.addWidget(b)
            self.body.addLayout(row)
        occs = self.srepo.for_date(today, self.sess.completed_on(today, today))
        if not occs:
            lab = QLabel("Nothing planned today.\nStart any saved workout from the Active Workout tab.")
            lab.setObjectName("muted")
            self.body.addWidget(lab)
        for o in occs:
            if o["is_rest"]:
                lab = QLabel("☾  Rest day. Recover, stretch, sleep well.")
                lab.setStyleSheet(f"color: {REST_COLOR}; font-weight: 600;")
                self.body.addWidget(lab)
                continue
            row = QHBoxLayout()
            lab = QLabel(occ_label(o))
            lab.setStyleSheet(f"color: {occ_color(o)}; font-weight: 700; font-size: 11pt;")
            b = QPushButton("Do again" if o["done"] else "Start")
            b.setObjectName("success" if not o["done"] else "")
            b.setEnabled(act is None)
            b.clicked.connect(lambda _=False, o=o: self.startRequested.emit(o["workout_id"], o["entry_id"]))
            row.addWidget(lab, 1)
            row.addWidget(b)
            self.body.addLayout(row)


class SchedulePage(QWidget):
    startRequested = Signal(int, object)
    resumeRequested = Signal()
    scheduleChanged = Signal()

    def __init__(self, srepo, wrepo, sess, parent=None):
        super().__init__(parent)
        self.srepo, self.wrepo, self.sess = srepo, wrepo, sess
        self.selected = dt.date.today()
        self.mode = "week"

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        # ---- left: header + calendar
        left = QVBoxLayout()
        head = QHBoxLayout()
        self.title = QLabel("")
        self.title.setObjectName("pageTitle")
        b_prev, b_next, b_today = QPushButton("◀"), QPushButton("▶"), QPushButton("Today")
        for b in (b_prev, b_next):
            b.setObjectName("tool")
        b_prev.clicked.connect(lambda: self._shift(-1))
        b_next.clicked.connect(lambda: self._shift(1))
        b_today.clicked.connect(lambda: self._select(dt.date.today()))
        self.b_week, self.b_month = QPushButton("Week"), QPushButton("Month")
        group = QButtonGroup(self)
        for b, mode in ((self.b_week, "week"), (self.b_month, "month")):
            b.setObjectName("seg")
            b.setCheckable(True)
            group.addButton(b)
            b.clicked.connect(lambda _=False, m=mode: self._set_mode(m))
        self.b_week.setChecked(True)
        b_routine = QPushButton("Weekly routine…")
        b_routine.clicked.connect(self._routine)
        head.addWidget(self.title, 1)
        for w in (b_prev, b_today, b_next, self.b_week, self.b_month, b_routine):
            head.addWidget(w)
        left.addLayout(head)
        self.legend = QLabel("")
        self.legend.setTextFormat(Qt.RichText)
        left.addWidget(self.legend)
        self.stack = QStackedWidget()
        self.stack.setObjectName("inner")
        self.week_box, self.month_box = plain(), plain()
        self.week_lay, self.month_lay = QHBoxLayout(self.week_box), QGridLayout(self.month_box)
        for lay in (self.week_lay, self.month_lay):
            lay.setSpacing(6)
            lay.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self.week_box)
        self.stack.addWidget(self.month_box)
        left.addWidget(self.stack, 1)
        root.addLayout(left, 1)

        # ---- right: today, selected day, upcoming
        right = QVBoxLayout()
        right.setSpacing(12)
        self.today_card = TodayCard(srepo, sess)
        self.today_card.startRequested.connect(self.startRequested.emit)
        self.today_card.resumeRequested.connect(self.resumeRequested.emit)
        self.day_card = Card("Selected day")
        self.day_title = QLabel("")
        self.day_title.setStyleSheet("font-size: 12pt; font-weight: 700;")
        self.day_rows = QVBoxLayout()
        self.day_rows.setSpacing(8)
        add_row = QHBoxLayout()
        b_add, b_rest = QPushButton("+ Add workout"), QPushButton("☾ Rest day")
        b_add.setObjectName("primary")
        b_add.clicked.connect(self._add)
        b_rest.clicked.connect(self._add_rest)
        add_row.addWidget(b_add)
        add_row.addWidget(b_rest)
        for w in (self.day_title,):
            self.day_card.lay.addWidget(w)
        self.day_card.lay.addLayout(self.day_rows)
        self.day_card.lay.addStretch(1)
        self.day_card.lay.addLayout(add_row)
        self.up_card = Card("Coming up")
        self.up_label = QLabel("")
        self.up_label.setTextFormat(Qt.RichText)
        self.up_label.setWordWrap(True)
        self.up_card.lay.addWidget(self.up_label)
        right.addWidget(self.today_card)
        right.addWidget(self.day_card, 1)
        right.addWidget(self.up_card)
        side = plain()
        side.setLayout(right)
        right.setContentsMargins(0, 0, 0, 0)
        side.setFixedWidth(370)
        root.addWidget(side)

        self.refresh()

    # --------------------------------------------------------- navigation
    def _set_mode(self, mode):
        self.mode = mode
        self.refresh()

    def _select(self, d):
        self.selected = d
        self.refresh()

    def _shift(self, n):
        s = self.selected
        if self.mode == "week":
            self.selected = s + dt.timedelta(days=7 * n)
        else:
            m = s.month - 1 + n
            y, m = s.year + m // 12, m % 12 + 1
            self.selected = dt.date(y, m, min(s.day, calendar.monthrange(y, m)[1]))
        self.refresh()

    def _range(self):
        s = self.selected
        if self.mode == "week":
            start = s - dt.timedelta(days=s.weekday())
            return start, start + dt.timedelta(days=6)
        first = s.replace(day=1)
        last = s.replace(day=calendar.monthrange(s.year, s.month)[1])
        return first - dt.timedelta(days=first.weekday()), last + dt.timedelta(days=6 - last.weekday())

    # ------------------------------------------------------------- refresh
    def refresh(self):
        today = dt.date.today()
        start, end = self._range()
        done = self.sess.completed_on(start, end)
        occ = self.srepo.occurrences(start, end, done)
        self.b_week.setChecked(self.mode == "week")
        self.b_month.setChecked(self.mode == "month")
        self.legend.setText(
            "<span style='color:#4dabf7'>■</span> workout &nbsp; <span style='color:#69db7c'>■</span> completed "
            "&nbsp; <span style='color:#7a8aa6'>▢</span> rest day &nbsp; <span style='color:#6b7686'>"
            "Click a day to see and edit it.</span>")

        if self.mode == "week":
            self.title.setText(f"{start.strftime('%b')} {start.day} – {end.strftime('%b')} {end.day}, {end.year}")
            clear_layout(self.week_lay)
            for i in range(7):
                d = start + dt.timedelta(days=i)
                c = DayCell(d, occ[d], today, self.selected, compact=False)
                c.clicked.connect(self._select)
                self.week_lay.addWidget(c, 1)
            self.stack.setCurrentWidget(self.week_box)
        else:
            self.title.setText(self.selected.strftime("%B %Y"))
            clear_layout(self.month_lay)
            for i, n in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
                lab = QLabel(n)
                lab.setAlignment(Qt.AlignCenter)
                lab.setObjectName("muted")
                self.month_lay.addWidget(lab, 0, i)
            d, r = start, 1
            while d <= end:
                c = DayCell(d, occ[d], today, self.selected, compact=True, in_month=d.month == self.selected.month)
                c.clicked.connect(self._select)
                self.month_lay.addWidget(c, r, d.weekday())
                if d.weekday() == 6:
                    r += 1
                d += dt.timedelta(days=1)
            for i in range(7):
                self.month_lay.setColumnStretch(i, 1)
            self.stack.setCurrentWidget(self.month_box)

        self.today_card.refresh()
        self._fill_day(occ.get(self.selected, []) if start <= self.selected <= end else [])
        self._fill_upcoming(today)

    def _fill_day(self, occs):
        self.day_title.setText(pretty_date(self.selected, True))
        clear_layout(self.day_rows)
        if not occs:
            lab = QLabel("Free day. Nothing planned.")
            lab.setObjectName("muted")
            self.day_rows.addWidget(lab)
        for o in occs:
            self.day_rows.addWidget(self._occ_row(o))

    def _occ_row(self, o):
        box = QFrame()
        box.setObjectName("occRow")
        box.setStyleSheet("QFrame#occRow { background: #141a24; border: 1px solid #1f2837; border-radius: 8px; }")
        v = QVBoxLayout(box)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(4)
        name = QLabel(occ_label(o))
        name.setStyleSheet(f"color: {occ_color(o)}; font-weight: 700; font-size: 10.5pt;")
        sub = ("Every " + WEEKDAYS[o["date"].weekday()]) if o["kind"] == "weekly" else "One-time"
        if o["note"]:
            sub += f" · {o['note']}"
        s = QLabel(sub)
        s.setObjectName("muted")
        v.addWidget(name)
        v.addWidget(s)
        row = QHBoxLayout()
        if not o["is_rest"]:
            b = QPushButton("Do again" if o["done"] else "Start")
            b.setObjectName("small")
            b.setEnabled(self.sess.active() is None)
            b.clicked.connect(lambda _=False, o=o: self.startRequested.emit(o["workout_id"], o["entry_id"]))
            row.addWidget(b)
        for text, fn, danger in (("Move", self._move, False), ("Edit", self._edit, False), ("Remove", self._remove, True)):
            b = QPushButton(text)
            b.setObjectName("danger" if danger else "small")
            if danger:
                b.setStyleSheet("padding: 3px 9px; font-size: 9pt;")
            b.clicked.connect(lambda _=False, o=o, fn=fn: fn(o))
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        return box

    def _fill_upcoming(self, today):
        end = today + dt.timedelta(days=14)
        done = self.sess.completed_on(today, end)
        items = self.srepo.upcoming(today, 14, done, 5)
        if not items:
            self.up_label.setText("<span style='color:#8b95a7'>No upcoming workouts in the next two weeks.</span>")
            return
        self.up_label.setText("<br>".join(
            f"<span style='color:{occ_color(o)}'>●</span> <b>{pretty_date(o['date'])}</b> &nbsp;{o['workout_name']}"
            for o in items))

    # ------------------------------------------------------------- actions
    def _changed(self):
        self.refresh()
        self.scheduleChanged.emit()

    def _add(self):
        dlg = EntryDialog(self.wrepo, self, day=self.selected)
        if dlg.exec() == QDialog.Accepted:
            self.srepo.add_entry(**dlg.values())
            self._changed()

    def _add_rest(self):
        self.srepo.add_entry("once", on_date=self.selected, is_rest=True)
        self._changed()

    def _edit(self, o):
        entry = self.srepo.entry(o["entry_id"])
        if entry["kind"] == "weekly":
            QMessageBox.information(self, "Repeating entry", "This edits the whole weekly entry. To change just "
                                                             "this day, use Move or Remove instead.")
        dlg = EntryDialog(self.wrepo, self, day=o["date"], entry=entry)
        if dlg.exec() == QDialog.Accepted:
            self.srepo.update_entry(o["entry_id"], **dlg.values())
            self._changed()

    def _move(self, o):
        d = MoveDialog.pick(self, o["date"])
        if d:
            self.srepo.move_occurrence(o, d)
            self.selected = d
            self._changed()

    def _remove(self, o):
        if o["kind"] == "weekly":
            box = QMessageBox(self)
            box.setWindowTitle("Remove")
            box.setText(f"Remove this weekly entry for {pretty_date(o['date'])} only, or every week?")
            one = box.addButton("This day only", QMessageBox.AcceptRole)
            allw = box.addButton("Every week", QMessageBox.DestructiveRole)
            box.addButton("Cancel", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() == one:
                self.srepo.remove_occurrence(o)
            elif box.clickedButton() == allw:
                self.srepo.remove_occurrence(o, all_weeks=True)
            else:
                return
        else:
            self.srepo.remove_occurrence(o)
        self._changed()

    def _routine(self):
        dlg = RoutineDialog(self.srepo, self.wrepo, self)
        dlg.exec()
        if dlg.changed:
            self._changed()
