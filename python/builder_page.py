"""Workout Builder: browse the exercise library and build, edit, duplicate and delete workouts."""
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QSplitter,
                               QVBoxLayout, QWidget)

from exercises_data import DIFFICULTY, EX_CATEGORIES
from animations import AnimationDialog, anim_for_exercise
from rank_widgets import log_performance_dialog, rank_html
from ui_common import Card, confirm, fmt_duration, plain
from workouts import STYLES, entry_defaults, estimate_seconds


def entry_text(i, e):
    amount = f"{e['hold_sec']} s hold" if e["kind"] == "hold" else f"{e['reps']} reps"
    return f"{i + 1}.  {e['name']}   ·   {e['sets']} × {amount}   ·   rest {e['rest_sets']} s"


def exercise_item(ex):
    muscles = ex.get("muscles") or ""
    it = QListWidgetItem(f"{ex['name']}   ·   {DIFFICULTY[ex['difficulty']]}, {ex['kind']}"
                         + (f"\n{muscles}" if muscles else "")
                         + ("" if ex["builtin"] else "   (custom)"))
    it.setForeground(QColor(EX_CATEGORIES[ex["category"]][1]))
    it.setToolTip(ex["instructions"] or ex["name"])
    it.setData(Qt.UserRole, ex["id"])
    return it


class ExerciseDialog(QDialog):
    """Create a custom exercise."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New custom exercise")
        self.setMinimumWidth(380)
        form = QFormLayout(self)
        self.name = QLineEdit()
        self.cat = QComboBox()
        for k, (label, _) in EX_CATEGORIES.items():
            self.cat.addItem(label, k)
        self.diff = QComboBox()
        for i, d in enumerate(DIFFICULTY):
            self.diff.addItem(d, i)
        self.kind = QComboBox()
        self.kind.addItem("Reps", "reps")
        self.kind.addItem("Hold (seconds)", "hold")
        self.sets, self.amount, self.rest = QSpinBox(), QSpinBox(), QSpinBox()
        self.sets.setRange(1, 20)
        self.sets.setValue(3)
        self.amount.setRange(1, 600)
        self.amount.setValue(10)
        self.rest.setRange(0, 600)
        self.rest.setValue(60)
        self.how = QPlainTextEdit()
        self.how.setFixedHeight(70)
        for label, w in (("Name", self.name), ("Category", self.cat), ("Difficulty", self.diff),
                         ("Type", self.kind), ("Default sets", self.sets), ("Default reps / seconds", self.amount),
                         ("Default rest (s)", self.rest), ("Instructions", self.how)):
            form.addRow(label, w)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self._ok)
        box.rejected.connect(self.reject)
        form.addRow(box)

    def _ok(self):
        if not self.name.text().strip():
            QMessageBox.warning(self, "Name needed", "Give the exercise a name.")
            return
        self.accept()

    def values(self):
        return (self.name.text(), self.cat.currentData(), self.diff.currentData(), self.kind.currentData(),
                self.sets.value(), self.amount.value(), self.rest.value(), self.how.toPlainText())


class ReplaceDialog(QDialog):
    """Pick an alternative exercise (same category first)."""

    def __init__(self, repo, current, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Replace {current['name']}")
        self.setMinimumSize(420, 480)
        self.repo, self.current, self.chosen = repo, current, None
        lay = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search alternatives…")
        self.search.textChanged.connect(self._fill)
        self.same = QComboBox()
        self.same.addItem("Same category", True)
        self.same.addItem("All categories", False)
        self.same.currentIndexChanged.connect(self._fill)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda *_: self._ok())
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self._ok)
        box.rejected.connect(self.reject)
        for w in (self.search, self.same, self.list, box):
            lay.addWidget(w)
        self._fill()

    def _fill(self):
        cat = self.current["category"] if self.same.currentData() else None
        rows = [e for e in self.repo.exercises(category=cat, search=self.search.text())
                if e["id"] != self.current["exercise_id"]]
        rows.sort(key=lambda e: abs(e["difficulty"] - self.current["difficulty"]))   # closest difficulty first
        self.list.clear()
        for e in rows:
            self.list.addItem(exercise_item(e))
        if rows:
            self.list.setCurrentRow(0)

    def _ok(self):
        it = self.list.currentItem()
        if it:
            self.chosen = it.data(Qt.UserRole)
            self.accept()


class WorkoutBuilderPage(QWidget):
    workoutsChanged = Signal()
    startWorkout = Signal(int)
    openLibrary = Signal(str)

    def __init__(self, repo, ranks, xp, parent=None):
        super().__init__(parent)
        self.repo, self.ranks, self.xp = repo, ranks, xp
        self.cur_id = None
        self.entries = []            # in-memory editor state; written to the DB on Save
        self._uid = 0
        self._dirty = False
        self._loading = False

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        split = QSplitter(Qt.Horizontal)
        split.setObjectName("pageSplit")
        split.setChildrenCollapsible(False)
        split.addWidget(self._build_saved())
        split.addWidget(self._build_library())
        split.addWidget(self._build_editor())
        split.setSizes([230, 420, 560])
        root.addWidget(split)

        self.reload_saved()
        self.reload_library()
        self._new(force=True)

    # ------------------------------------------------------------ build UI
    def _build_saved(self):
        card = Card("My workouts")
        self.saved = QListWidget()
        self.saved.currentItemChanged.connect(self._on_saved_selected)
        row = QHBoxLayout()
        b_new, self.b_dup, self.b_del = QPushButton("New"), QPushButton("Duplicate"), QPushButton("Delete")
        b_new.setObjectName("primary")
        self.b_del.setObjectName("danger")
        b_new.clicked.connect(lambda: self._new())
        self.b_dup.clicked.connect(self._duplicate)
        self.b_del.clicked.connect(self._delete)
        for b in (b_new, self.b_dup, self.b_del):
            row.addWidget(b)
        self.b_preset = QPushButton("Load preset")
        self.b_preset.clicked.connect(self._load_preset)
        row.addWidget(self.b_preset)
        card.lay.addWidget(self.saved, 1)
        card.lay.addLayout(row)
        return card

    def _build_library(self):
        card = Card("Exercise library")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search exercises…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.reload_library)
        self.cat_combo = QComboBox()
        self.cat_combo.addItem("All categories", None)
        for k, (label, _) in EX_CATEGORIES.items():
            self.cat_combo.addItem(label, k)
        self.diff_combo = QComboBox()
        self.diff_combo.addItem("All levels", None)
        for i, d in enumerate(DIFFICULTY):
            self.diff_combo.addItem(d, i)
        self.cat_combo.currentIndexChanged.connect(self.reload_library)
        self.diff_combo.currentIndexChanged.connect(self.reload_library)
        self.fav_only = QCheckBox("Favourites")
        self.fav_only.toggled.connect(self.reload_library)
        filters = QHBoxLayout()
        filters.addWidget(self.cat_combo)
        filters.addWidget(self.diff_combo)
        filters.addWidget(self.fav_only)
        self.library = QListWidget()
        self.library.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.library.itemDoubleClicked.connect(lambda *_: self._add_selected())
        self.library.itemSelectionChanged.connect(self._library_selection)
        self.lib_count = QLabel("")
        self.lib_count.setObjectName("muted")
        self.lib_detail = QLabel("Select an exercise to see its instructions and rank.")
        self.lib_detail.setTextFormat(Qt.RichText)
        self.lib_detail.setWordWrap(True)
        self.lib_detail.setObjectName("muted")
        self.b_log = QPushButton("Log performance…")
        self.b_log.setToolTip("Record a real set. This is what changes this exercise's rank")
        self.b_log.setEnabled(False)
        self.b_log.clicked.connect(self._log_performance)
        self.b_anim = QPushButton("Animation…")
        self.b_anim.setObjectName("ghost")
        self.b_anim.setToolTip("Show the movement animation and its phase breakdown")
        self.b_anim.setEnabled(False)
        self.b_anim.clicked.connect(self._show_animation)
        self.b_lib = QPushButton("In library")
        self.b_lib.setObjectName("ghost")
        self.b_lib.setToolTip("Open this exercise in the full Exercise Library")
        self.b_lib.setEnabled(False)
        self.b_lib.clicked.connect(self._open_in_library)
        row = QHBoxLayout()
        self.b_add = QPushButton("Add to workout  →")
        self.b_add.setObjectName("primary")
        self.b_add.clicked.connect(self._add_selected)
        b_custom = QPushButton("Custom…")
        b_custom.clicked.connect(self._custom_exercise)
        self.b_del_ex = QPushButton("Delete custom")
        self.b_del_ex.setObjectName("danger")
        self.b_del_ex.clicked.connect(self._delete_custom)
        self.b_del_ex.setEnabled(False)
        for b in (self.b_add, b_custom, self.b_del_ex):
            row.addWidget(b)
        card.lay.addWidget(self.search)
        card.lay.addLayout(filters)
        card.lay.addWidget(self.library, 1)
        card.lay.addWidget(self.lib_count)
        card.lay.addWidget(self.lib_detail)
        row.addWidget(self.b_log)
        row.addWidget(self.b_anim)
        row.addWidget(self.b_lib)
        card.lay.addLayout(row)
        return card

    def _build_editor(self):
        card = Card("Workout")
        self.name = QLineEdit()
        self.name.setPlaceholderText("Workout name")
        self.desc = QPlainTextEdit()
        self.desc.setPlaceholderText("Description (optional)")
        self.desc.setFixedHeight(52)
        self.style = QComboBox()
        for k, (label, _) in STYLES.items():
            self.style.addItem(label, k)
        self.b_apply = QPushButton("Apply style to all")
        self.b_apply.setObjectName("small")
        self.b_apply.setToolTip("Reset sets, reps, holds and rests of every exercise to this style's defaults")
        self.b_apply.clicked.connect(self._apply_style)
        style_row = QHBoxLayout()
        style_row.addWidget(QLabel("Style"))
        style_row.addWidget(self.style, 1)
        style_row.addWidget(self.b_apply)
        for w in (self.name, self.desc):
            (w.textChanged if isinstance(w, QPlainTextEdit) else w.textChanged).connect(self._touch)
        self.style.currentIndexChanged.connect(self._touch)

        self.elist = QListWidget()
        self.elist.setDragDropMode(QAbstractItemView.InternalMove)
        self.elist.setDefaultDropAction(Qt.MoveAction)
        self.elist.currentRowChanged.connect(self._load_form)
        self.elist.model().rowsMoved.connect(lambda *a: QTimer.singleShot(0, self._sync_order))

        # per-exercise form
        self.f_sets, self.f_reps, self.f_hold = QSpinBox(), QSpinBox(), QSpinBox()
        self.f_rs, self.f_ra = QSpinBox(), QSpinBox()
        self.f_sets.setRange(1, 30)
        self.f_reps.setRange(0, 500)
        self.f_hold.setRange(0, 900)
        self.f_hold.setSuffix(" s")
        self.f_rs.setRange(0, 900)
        self.f_rs.setSuffix(" s")
        self.f_ra.setRange(0, 900)
        self.f_ra.setSuffix(" s")
        self.f_note = QLineEdit()
        self.f_note.setPlaceholderText("Note for this exercise (optional)")
        for w in (self.f_sets, self.f_reps, self.f_hold, self.f_rs, self.f_ra):
            w.valueChanged.connect(self._form_changed)
        self.f_note.textChanged.connect(self._form_changed)
        self.form_box = plain()
        form = QFormLayout(self.form_box)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Sets", self.f_sets)
        form.addRow("Reps", self.f_reps)
        form.addRow("Hold", self.f_hold)
        form.addRow("Rest between sets", self.f_rs)
        form.addRow("Rest after exercise", self.f_ra)
        form.addRow("Note", self.f_note)

        tools = QHBoxLayout()
        self.b_up, self.b_down = QPushButton("▲ Up"), QPushButton("▼ Down")
        self.b_replace, self.b_remove = QPushButton("Replace…"), QPushButton("Remove")
        self.b_remove.setObjectName("danger")
        self.b_up.clicked.connect(lambda: self._move(-1))
        self.b_down.clicked.connect(lambda: self._move(1))
        self.b_replace.clicked.connect(self._replace)
        self.b_remove.clicked.connect(self._remove)
        for b in (self.b_up, self.b_down, self.b_replace, self.b_remove):
            tools.addWidget(b)

        self.est = QLabel("")
        self.est.setObjectName("muted")
        self.dirty_label = QLabel("")
        self.dirty_label.setStyleSheet("color: #ffa94d;")
        bottom = QHBoxLayout()
        self.b_save = QPushButton("Save workout")
        self.b_save.setObjectName("primary")
        self.b_save.clicked.connect(self.save)
        self.b_start = QPushButton("Start workout")
        self.b_start.setObjectName("success")
        self.b_start.clicked.connect(self._start)
        bottom.addWidget(self.est, 1)
        bottom.addWidget(self.dirty_label)
        bottom.addWidget(self.b_save)
        bottom.addWidget(self.b_start)

        card.lay.addWidget(self.name)
        card.lay.addWidget(self.desc)
        card.lay.addLayout(style_row)
        card.lay.addWidget(self.elist, 1)
        card.lay.addLayout(tools)
        card.lay.addWidget(self.form_box)
        card.lay.addLayout(bottom)
        return card

    # --------------------------------------------------------- list refresh
    def reload_saved(self, select_id=None):
        self.saved.blockSignals(True)
        self.saved.clear()
        for w in self.repo.workouts():
            it = QListWidgetItem(f"{w['name']}\n{w['n']} exercises · {STYLES.get(w['style'], ('?',))[0]}")
            it.setData(Qt.UserRole, w["id"])
            self.saved.addItem(it)
            if w["id"] == select_id:
                self.saved.setCurrentItem(it)
        self.saved.blockSignals(False)
        self._update_buttons()

    def reload_library(self, *_):
        rows = self.repo.exercises(self.cat_combo.currentData(), self.diff_combo.currentData(),
                                   self.search.text(),
                                   favorites=True if self.fav_only.isChecked() else None)
        self.library.clear()
        for ex in rows:
            self.library.addItem(exercise_item(ex))
        self.lib_count.setText(f"{len(rows)} exercise{'s' if len(rows) != 1 else ''} · double-click to add")

    def _library_selection(self):
        ids = [i.data(Qt.UserRole) for i in self.library.selectedItems()]
        self.b_del_ex.setEnabled(len(ids) == 1 and ids[0].startswith("u_"))
        self.b_anim.setEnabled(len(ids) == 1)
        self.b_lib.setEnabled(len(ids) == 1)
        self._show_exercise_detail(ids[0] if len(ids) == 1 else None)

    def _show_exercise_detail(self, ex_id):
        ex = self.repo.exercise(ex_id) if ex_id else None
        res = self.ranks.result_for_exercise(ex_id) if ex else None
        self.b_log.setEnabled(res is not None)
        if not ex:
            self.lib_detail.setText("Select an exercise to see its instructions and rank.")
        elif res is None:
            self.lib_detail.setText(f"<b>{ex['name']}</b><br>{ex['instructions']}<br>"
                                    f"<span style='color:#6b7686'>Custom exercises have no rank.</span>")
        else:
            self.lib_detail.setText(f"<b>{ex['name']}</b> &nbsp;{rank_html(res.rank)}<br>{ex['instructions']}<br>"
                                    f"<span style='color:#8b95a7'>{res.headline} · next: {res.goal}</span>")

    def _log_performance(self):
        items = self.library.selectedItems()
        if len(items) == 1:
            log_performance_dialog(self, self.ranks, items[0].data(Qt.UserRole), None, self.xp)

    def _show_animation(self):
        """Open the offline animation of the selected exercise."""
        items = self.library.selectedItems()
        if len(items) != 1:
            return
        ex = self.repo.exercise(items[0].data(Qt.UserRole))
        if not ex:
            return
        anim = anim_for_exercise(ex)
        dlg = AnimationDialog(anim, ex["name"], self)
        dlg.exec()

    def _open_in_library(self):
        items = self.library.selectedItems()
        if len(items) == 1:
            self.openLibrary.emit(items[0].data(Qt.UserRole))

    # ------------------------------------------------------------ editing state
    def _touch(self, *_):
        if not self._loading:
            self._dirty = True
            self._update_buttons()

    def _update_buttons(self):
        has_sel = self.cur_id is not None
        self.b_dup.setEnabled(has_sel)
        self.b_del.setEnabled(has_sel)
        self.b_start.setEnabled(bool(self.entries))
        self.dirty_label.setText("● unsaved changes" if self._dirty else "")
        self.est.setText(f"{len(self.entries)} exercises · about {fmt_duration(estimate_seconds(self.entries))}"
                         if self.entries else "No exercises yet. Add some from the library.")
        row = self.elist.currentRow()
        has_entry = 0 <= row < len(self.entries)
        for b in (self.b_replace, self.b_remove):
            b.setEnabled(has_entry)
        self.b_up.setEnabled(has_entry and row > 0)
        self.b_down.setEnabled(has_entry and row < len(self.entries) - 1)
        self.form_box.setEnabled(has_entry)

    def _discard_ok(self):
        if not self._dirty:
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Unsaved changes")
        box.setText("This workout has unsaved changes.")
        save = box.addButton("Save", QMessageBox.AcceptRole)
        discard = box.addButton("Discard", QMessageBox.DestructiveRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() == save:
            return self.save()
        return box.clickedButton() == discard

    def _fill_editor(self, wid, name, desc, style, entries):
        self._loading = True
        self.cur_id = wid
        self.name.setText(name)
        self.desc.setPlainText(desc)
        self.style.setCurrentIndex(max(0, self.style.findData(style)))
        self.entries = []
        for e in entries:
            self._uid += 1
            self.entries.append(dict(e, uid=self._uid))
        self._loading = False
        self._dirty = False
        self._rebuild_entries(0 if self.entries else -1)

    def _new(self, force=False):
        if not force and not self._discard_ok():
            return
        self.saved.blockSignals(True)
        self.saved.setCurrentRow(-1)
        self.saved.blockSignals(False)
        self._fill_editor(None, "", "", "strength", [])
        self.name.setFocus()

    def _on_saved_selected(self, item, _prev):
        if item is None:
            return
        wid = item.data(Qt.UserRole)
        if wid == self.cur_id:
            return
        if not self._discard_ok():
            QTimer.singleShot(0, lambda: self.reload_saved(self.cur_id))
            return
        w = self.repo.workout(wid)
        self._fill_editor(wid, w["name"], w["description"], w["style"], w["entries"])

    def _rebuild_entries(self, select_row=-1):
        self.elist.blockSignals(True)
        self.elist.clear()
        for i, e in enumerate(self.entries):
            it = QListWidgetItem(entry_text(i, e))
            it.setData(Qt.UserRole, e["uid"])
            it.setForeground(QColor(EX_CATEGORIES[e["category"]][1]))
            self.elist.addItem(it)
        if 0 <= select_row < len(self.entries):
            self.elist.setCurrentRow(select_row)
        self.elist.blockSignals(False)
        self._load_form(self.elist.currentRow())
        self._update_buttons()

    def _sync_order(self):
        by_uid = {e["uid"]: e for e in self.entries}
        new = [by_uid[self.elist.item(i).data(Qt.UserRole)] for i in range(self.elist.count())]
        if [e["uid"] for e in new] != [e["uid"] for e in self.entries]:
            cur = self.elist.currentItem().data(Qt.UserRole) if self.elist.currentItem() else None
            self.entries = new
            self._dirty = True
            self._rebuild_entries(next((i for i, e in enumerate(new) if e["uid"] == cur), -1))

    # ------------------------------------------------------------ entry form
    def _load_form(self, row):
        self._loading = True
        ok = 0 <= row < len(self.entries)
        e = self.entries[row] if ok else None
        self.f_sets.setValue(e["sets"] if ok else 1)
        self.f_reps.setValue(e["reps"] if ok else 0)
        self.f_hold.setValue(e["hold_sec"] if ok else 0)
        self.f_rs.setValue(e["rest_sets"] if ok else 0)
        self.f_ra.setValue(e["rest_after"] if ok else 0)
        self.f_note.setText(e.get("note", "") if ok else "")
        is_hold = ok and e["kind"] == "hold"
        self.f_reps.setEnabled(ok and not is_hold)
        self.f_hold.setEnabled(bool(is_hold))
        self._loading = False
        self._update_buttons()

    def _form_changed(self, *_):
        row = self.elist.currentRow()
        if self._loading or not 0 <= row < len(self.entries):
            return
        e = self.entries[row]
        e.update(sets=self.f_sets.value(), reps=self.f_reps.value() if e["kind"] == "reps" else 0,
                 hold_sec=self.f_hold.value() if e["kind"] == "hold" else 0,
                 rest_sets=self.f_rs.value(), rest_after=self.f_ra.value(), note=self.f_note.text())
        self.elist.item(row).setText(entry_text(row, e))
        self._touch()

    # --------------------------------------------------------- entry actions
    def _new_entry(self, ex):
        d = entry_defaults(ex, self.style.currentData())
        self._uid += 1
        d.update(exercise_id=ex["id"], name=ex["name"], kind=ex["kind"], category=ex["category"],
                 difficulty=ex["difficulty"], note="", uid=self._uid)
        return d

    def _add_selected(self):
        items = self.library.selectedItems() or ([self.library.currentItem()] if self.library.currentItem() else [])
        if not items:
            return
        for it in items:
            self.entries.append(self._new_entry(self.repo.exercise(it.data(Qt.UserRole))))
        self._touch()
        self._rebuild_entries(len(self.entries) - 1)
        self.elist.scrollToBottom()

    def add_exercise(self, ex_id):
        """Add one exercise to the workout that is currently open (used by the Library page)."""
        ex = self.repo.exercise(ex_id)
        if not ex:
            return False
        if not self.name.text().strip():
            self.name.setText("My workout")
        self.entries.append(self._new_entry(ex))
        self._touch()
        self._rebuild_entries(len(self.entries) - 1)
        self.elist.scrollToBottom()
        return True

    def _move(self, delta):
        row = self.elist.currentRow()
        new = row + delta
        if 0 <= row < len(self.entries) and 0 <= new < len(self.entries):
            self.entries[row], self.entries[new] = self.entries[new], self.entries[row]
            self._touch()
            self._rebuild_entries(new)

    def _remove(self):
        row = self.elist.currentRow()
        if 0 <= row < len(self.entries):
            del self.entries[row]
            self._touch()
            self._rebuild_entries(min(row, len(self.entries) - 1))

    def _replace(self):
        row = self.elist.currentRow()
        if not 0 <= row < len(self.entries):
            return
        old = self.entries[row]
        dlg = ReplaceDialog(self.repo, old, self)
        if dlg.exec() != QDialog.Accepted or not dlg.chosen:
            return
        ex = self.repo.exercise(dlg.chosen)
        new = self._new_entry(ex)
        if ex["kind"] == old["kind"]:                 # keep the user's own numbers when the type matches
            new.update({k: old[k] for k in ("sets", "reps", "hold_sec", "rest_sets", "rest_after")})
        new["note"] = old.get("note", "")
        self.entries[row] = new
        self._touch()
        self._rebuild_entries(row)

    def _apply_style(self):
        if not self.entries or not confirm(self, "Apply style",
                                           "Reset sets, reps, holds and rest times of every exercise to this style's defaults?"):
            return
        for e in self.entries:
            ex = self.repo.exercise(e["exercise_id"])
            e.update(entry_defaults(ex, self.style.currentData()))
        self._touch()
        self._rebuild_entries(max(0, self.elist.currentRow()))

    # ----------------------------------------------------- library actions
    def _custom_exercise(self):
        dlg = ExerciseDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.repo.add_custom_exercise(*dlg.values())
            self.reload_library()

    def _delete_custom(self):
        items = self.library.selectedItems()
        if len(items) == 1 and confirm(self, "Delete exercise", "Delete this custom exercise?"):
            if not self.repo.delete_custom_exercise(items[0].data(Qt.UserRole)):
                QMessageBox.information(self, "In use", "This exercise is used by a saved workout. "
                                                        "Remove it from that workout first.")
            self.reload_library()

    # ------------------------------------------------------------ persistence
    def save(self):
        name = self.name.text().strip()
        if not name:
            QMessageBox.warning(self, "Name needed", "Give your workout a name before saving.")
            self.name.setFocus()
            return False
        if not self.entries:
            QMessageBox.warning(self, "No exercises", "Add at least one exercise before saving.")
            return False
        self.cur_id = self.repo.save_workout(self.cur_id, name, self.desc.toPlainText(),
                                             self.style.currentData(), self.entries)
        self._dirty = False
        self.reload_saved(self.cur_id)
        self._update_buttons()
        self.workoutsChanged.emit()
        return True

    def _duplicate(self):
        if self.cur_id is None or not self._discard_ok():
            return
        new_id = self.repo.duplicate_workout(self.cur_id)
        self.reload_saved(new_id)
        w = self.repo.workout(new_id)
        self._fill_editor(new_id, w["name"], w["description"], w["style"], w["entries"])
        self.workoutsChanged.emit()

    def _delete(self):
        if self.cur_id is None:
            return
        if confirm(self, "Delete workout", f"Delete '{self.name.text()}'? It will also be removed from your "
                                           "schedule. Completed sessions in your history are kept."):
            self.repo.delete_workout(self.cur_id)
            self.reload_saved()
            self._new(force=True)
            self.workoutsChanged.emit()

    def _start(self):
        if self._dirty or self.cur_id is None:
            if not self.save():
                return
        self.startWorkout.emit(self.cur_id)

    def refresh(self):
        """Called when the page is shown: pick up library and rank changes."""
        self.reload_library()
        self._library_selection()

    def refresh_ranks(self):
        ids = [i.data(Qt.UserRole) for i in self.library.selectedItems()]
        self._show_exercise_detail(ids[0] if len(ids) == 1 else None)

    def open_workout(self, wid):
        if wid != self.cur_id and self._discard_ok():
            self.reload_saved(wid)
            w = self.repo.workout(wid)
            self._fill_editor(wid, w["name"], w["description"], w["style"], w["entries"])

    def _load_preset(self):
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        presets = self._get_presets()
        names = [p[0] for p in presets]
        name, ok = QInputDialog.getItem(self, "Load preset", "Choose a calisthenics preset:", names, 0, False)
        if not ok or not name:
            return
        # find preset
        for pname, pdata in presets:
            if pname == name:
                # create new workout from preset
                try:
                    wid = self.repo.create_workout(pname)
                    # clear default entries and add preset
                    self.repo.delete_workout(wid)
                    wid = self.repo.create_workout(pname)
                    for e in pdata:
                        self.repo.add_entry(wid, e)
                    self.reload_saved()
                    # select it
                    for i in range(self.saved.count()):
                        it = self.saved.item(i)
                        if it.data(Qt.UserRole) == wid:
                            self.saved.setCurrentItem(it)
                            break
                    QMessageBox.information(self, "Loaded", f"Preset '{name}' added to your workouts.")
                except Exception as ex:
                    QMessageBox.warning(self, "Error", str(ex))
                break
