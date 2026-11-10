"""Shared rank UI: hexagon badge, 'log performance' dialogs, rank-change messages."""
import math

from PySide6.QtCore import QDate, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout,
                               QGridLayout, QLabel, QLineEdit, QMessageBox, QSpinBox, QVBoxLayout,
                               QWidget)

from ranks import GROUPS, RANKS, ROMAN, rank_for
from xp_widgets import announce_progress


def rank_html(rank, text=None):
    return f"<span style='color:{RANKS[rank][1]}'><b>{text or RANKS[rank][0]}</b></span>"


def change_lines(changes):
    """HTML lines such as '▲ Pull-Up: Warden → Paladin'."""
    return [f"{'▲' if c['up'] else '▼'} <b>{c['track']}</b>: {rank_html(c['before'])} → {rank_html(c['after'])}"
            for c in changes]


def announce_rank_changes(parent, changes):
    if changes:
        QMessageBox.information(parent, "Rank up!" if any(c["up"] for c in changes) else "Rank changed",
                                "<br>".join(change_lines(changes)))


class RankBadge(QWidget):
    """Hexagonal rank emblem: tier colour, roman numeral, brighter and spikier at higher tiers."""

    def __init__(self, size=48, rank=0, parent=None):
        super().__init__(parent)
        self.rank = rank
        self.setFixedSize(size, size)

    def set_rank(self, rank):
        self.rank = rank
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = min(self.width(), self.height())
        cx = cy = s / 2
        col = QColor(RANKS[self.rank][1])

        def hexagon(r, rot=90):
            return QPolygonF([QPointF(cx + r * math.cos(math.radians(rot + 60 * i)),
                                      cy - r * math.sin(math.radians(rot + 60 * i))) for i in range(6)])

        r = s * 0.46
        if self.rank >= 7:                                  # outer points for the top tiers
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(col.red(), col.green(), col.blue(), 70))
            p.drawPolygon(hexagon(r * 1.0, 60))
        grad = QLinearGradient(0, 0, 0, s)
        if self.rank == 0:
            grad.setColorAt(0, QColor("#232a36"))
            grad.setColorAt(1, QColor("#161b24"))
        else:
            grad.setColorAt(0, col.lighter(125))
            grad.setColorAt(1, col.darker(170))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(col if self.rank else QColor("#3a4454"), max(1.5, s * 0.05)))
        p.drawPolygon(hexagon(r))
        p.setPen(QPen(QColor(255, 255, 255, 60 if self.rank else 25), max(1.0, s * 0.02)))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(hexagon(r * 0.74))
        f = QFont(self.font())
        f.setPixelSize(max(8, int(s * (0.30 if self.rank < 4 else 0.26))))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#10141b") if self.rank >= 3 else QColor("#e6e9ef") if self.rank else QColor("#5b6573"))
        p.drawText(QRectF(0, 0, s, s), int(Qt.AlignCenter), ROMAN[self.rank])


class LogPerformanceDialog(QDialog):
    """Record a real performance for one exercise (the only way ranks change besides confirmed workouts)."""

    def __init__(self, ranks, parent=None, exercise_id=None, only_ids=None):
        super().__init__(parent)
        self.ranks = ranks
        self.setWindowTitle("Log performance")
        self.setMinimumWidth(400)
        self.results = ranks.evaluate_all()
        form = QFormLayout(self)
        self.ex = QComboBox()
        tracks = [t for t in ranks.tracks if t.metric != "line" and (only_ids is None or t.exercise_id in only_ids)]
        for t in sorted(tracks, key=lambda t: (list(GROUPS).index(t.group), t.name)):
            self.ex.addItem(f"{t.name}   ({GROUPS[t.group]})", t.exercise_id)
        if exercise_id:
            self.ex.setCurrentIndex(max(0, self.ex.findData(exercise_id)))
        self.value = QSpinBox()
        self.value.setRange(1, 9999)
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setMaximumDate(QDate.currentDate())
        self.note = QLineEdit()
        self.note.setPlaceholderText("Optional note (e.g. strict form, bar height)")
        self.preview = QLabel("")
        self.preview.setTextFormat(Qt.RichText)
        self.preview.setWordWrap(True)
        self.hint = QLabel("Only log clean, technically correct reps and holds. Your rank follows this number.")
        self.hint.setObjectName("muted")
        self.hint.setWordWrap(True)
        form.addRow("Exercise", self.ex)
        form.addRow("Best set", self.value)
        form.addRow("Date", self.date)
        form.addRow("Note", self.note)
        form.addRow(self.preview)
        form.addRow(self.hint)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        form.addRow(box)
        self.ex.currentIndexChanged.connect(self._exercise_changed)
        self.value.valueChanged.connect(self._update_preview)
        self._exercise_changed()

    def _track(self):
        return self.ranks.by_exercise.get(self.ex.currentData())

    def _exercise_changed(self):
        t = self._track()
        if not t:
            return
        res = self.results[t.id]
        self.value.setSuffix(f" {t.unit}")
        self.value.setMaximum(self.ranks.max_plausible(t.exercise_id))
        self.value.blockSignals(True)
        self.value.setValue(int(res.best) if res.best else max(1, t.thresholds[0]))
        self.value.blockSignals(False)
        self._update_preview()

    def _update_preview(self):
        t = self._track()
        if not t:
            return
        res = self.results[t.id]
        new = rank_for(t.thresholds, max(res.best, self.value.value()))
        text = f"Current: {rank_html(res.rank)} &nbsp;·&nbsp; best {res.best:g} {t.unit}"
        if new > res.rank:
            text += f"<br>This result would make you {rank_html(new)} ▲"
        elif self.value.value() <= res.best:
            text += "<br><span style='color:#8b95a7'>Below your best, so your rank won't change.</span>"
        self.preview.setText(text)

    def values(self):
        return (self.ex.currentData(), self.value.value(), self.date.date().toPython(), self.note.text())


def log_performance_dialog(parent, ranks, exercise_id=None, only_ids=None, xp=None):
    """Open the dialog, store the result and announce rank changes. Returns the changes or None."""
    dlg = LogPerformanceDialog(ranks, parent, exercise_id, only_ids)
    if dlg.exec() != QDialog.Accepted:
        return None
    ex, value, day, note = dlg.values()
    try:
        changes = ranks.log_performance(ex, value, day=day, note=note)
    except ValueError as exc:
        QMessageBox.warning(parent, "Can't save", str(exc))
        return None
    if xp is not None:
        announce_progress(parent, xp.sync())          # XP for rank-ups / records / achievements this earned
    else:
        announce_rank_changes(parent, changes)
    return changes


class PerformanceDialog(QDialog):
    """After a workout: confirm the best set you really performed for each exercise."""

    def __init__(self, ranks, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm your performance")
        self.setMinimumWidth(560)
        self.ranks, self.items = ranks, items
        results = ranks.evaluate_all()
        lay = QVBoxLayout(self)
        intro = QLabel("Ranks are based on what you actually achieved. Check or correct your best set for each "
                       "exercise. Unchecked exercises won't affect your ranks.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        grid = QGridLayout()
        grid.setVerticalSpacing(8)
        self.rows = []
        for r, it in enumerate(items):
            t = ranks.by_exercise[it["exercise_id"]]
            res = results[t.id]
            check = QCheckBox(it["name"])
            check.setChecked(True)
            spin = QSpinBox()
            spin.setRange(0, ranks.max_plausible(it["exercise_id"]))
            spin.setValue(min(int(it["value"]), spin.maximum()))
            spin.setSuffix(f" {t.unit}")
            lab = QLabel("")
            lab.setTextFormat(Qt.RichText)
            spin.valueChanged.connect(lambda _=0, s=spin, t=t, res=res, lab=lab: self._preview(s, t, res, lab))
            self._preview(spin, t, res, lab)
            for c, w in enumerate((check, spin, lab)):
                grid.addWidget(w, r, c)
            self.rows.append((check, spin, it))
        lay.addLayout(grid)
        box = QDialogButtonBox()
        save = box.addButton("Save performance", QDialogButtonBox.AcceptRole)
        save.setObjectName("primary")
        box.addButton("Skip", QDialogButtonBox.RejectRole)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    @staticmethod
    def _preview(spin, t, res, lab):
        new = rank_for(t.thresholds, max(res.best, spin.value()))
        arrow = f" → {rank_html(new)} ▲" if new > res.rank else ""
        lab.setText(f"{rank_html(res.rank)}{arrow}")

    def accepted_items(self):
        return [dict(exercise_id=it["exercise_id"], set_id=it["set_id"], value=spin.value())
                for check, spin, it in self.rows if check.isChecked() and spin.value() > 0]
