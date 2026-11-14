"""Exercise Library: browse, search, filter and inspect every exercise.

The library is the single source of truth for the training content. It reads the
same data as the Workout Builder (the `exercises` and `exercise_details`
tables), so a change here shows up there immediately. Every exercise can be
opened in the animation viewer, marked as a favourite and added to a workout
with one click.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QScrollArea, QSizePolicy, QSplitter, QVBoxLayout,
                               QWidget)

from animations import AnimationPlayer, anim_for_exercise
from exercises_data import CATEGORY_ORDER, DIFFICULTY, EX_CATEGORIES
from rank_widgets import rank_html
from ui_common import Card, chip, clear_layout, plain

KIND_LABEL = {"reps": "reps", "hold": "hold (seconds)"}


def _split(text):
    """'a | b' -> ['a', 'b']"""
    return [t.strip() for t in (text or "").split("|") if t.strip()]


def _split_ids(text):
    return [t.strip() for t in (text or "").split(",") if t.strip()]


class ExerciseListItem(QListWidgetItem):
    pass


class LibraryPage(QWidget):
    """Browse the whole exercise library."""

    addToWorkout = Signal(str)          # exercise id
    exerciseSelected = Signal(str)       # exercise id
    message = Signal(str)

    def __init__(self, wrepo, profiles, ranks=None, parent=None):
        super().__init__(parent)
        self.wrepo, self.profiles, self.ranks = wrepo, profiles, ranks
        self.current_id = None
        self._details = {}
        self._detail_sig = None
        self._build()
        self.refresh()

    # ------------------------------------------------------------------ build
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_toolbar())

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self._build_list())
        split.addWidget(self._build_detail())
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 2)
        split.setSizes([420, 900])
        root.addWidget(split, 1)

    def _build_toolbar(self):
        bar = QWidget()
        bar.setObjectName("subbar")
        col = QVBoxLayout(bar)
        col.setContentsMargins(16, 8, 16, 8)
        col.setSpacing(6)

        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search exercises, muscles, technique…")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(260)
        self.search.textChanged.connect(self.refresh)
        self.diff_combo = QComboBox()
        self.diff_combo.addItem("All difficulties", None)
        for i, d in enumerate(DIFFICULTY):
            self.diff_combo.addItem(d, i)
        self.diff_combo.currentIndexChanged.connect(self.refresh)
        self.muscle_combo = QComboBox()
        self.muscle_combo.addItem("All muscle groups", None)
        self.muscle_combo.currentIndexChanged.connect(self.refresh)
        self.fav_only = QCheckBox("Favourites only")
        self.fav_only.toggled.connect(self.refresh)
        self.count_label = QLabel("")
        self.count_label.setObjectName("muted")
        row.addWidget(self.search, 1)
        row.addWidget(self.diff_combo)
        row.addWidget(self.muscle_combo)
        row.addWidget(self.fav_only)
        row.addWidget(self.count_label)
        col.addLayout(row)

        # category chips
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.cat_buttons = {}
        self._cat = None
        for key in CATEGORY_ORDER:
            label, color = EX_CATEGORIES[key]
            b = QPushButton(label)
            b.setObjectName("chipButton")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self._set_category(k))
            chips.addWidget(b)
            self.cat_buttons[key] = b
        self._style_chips()
        allb = QPushButton("All")
        allb.setObjectName("chipButton")
        allb.setCheckable(True)
        allb.setChecked(True)
        allb.setCursor(Qt.PointingHandCursor)
        allb.clicked.connect(lambda: self._set_category(None))
        chips.addWidget(allb)
        self._all_button = allb
        chips.addStretch(1)
        col.addLayout(chips)
        self._style_chips()
        return bar

    def _style_chips(self):
        """Colour the category chips and highlight the active one."""
        for key, b in self.cat_buttons.items():
            label, color = EX_CATEGORIES[key]
            on = (getattr(self, "_cat", None) == key)
            border = color if on else f"{color}55"
            bg = f"{color}22" if on else "transparent"
            weight = 700 if on else 600
            b.setStyleSheet(f"QPushButton#chipButton {{ color:{color}; border:1px solid {border}; "
                            f"border-radius:11px; padding:3px 12px; background:{bg}; "
                            f"font-weight:{weight}; }}")
        b = getattr(self, "_all_button", None)
        if b is not None:
            on = getattr(self, "_cat", None) is None
            border = "#8b95a7" if on else "#2a3242"
            bg = "#8b95a722" if on else "transparent"
            b.setStyleSheet(f"QPushButton#chipButton {{ color:#8b95a7; border:1px solid {border}; "
                            f"border-radius:11px; padding:3px 12px; background:{bg}; "
                            f"font-weight:{700 if on else 600}; }}")

    def _build_list(self):
        wrap = QWidget()
        wrap.setObjectName("plain")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(10, 10, 6, 10)
        self.list = QListWidget()
        self.list.setObjectName("plain")
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.currentItemChanged.connect(self._on_select)
        self.list.setAlternatingRowColors(False)
        lay.addWidget(self.list, 1)
        return wrap

    def _build_detail(self):
        wrap = QWidget()
        wrap.setObjectName("plain")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(6, 10, 14, 10)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setObjectName("plain")
        self.detail = QWidget()
        self.detail.setObjectName("plain")
        self.detail_layout = QVBoxLayout(self.detail)
        self.detail_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_layout.setSpacing(10)
        self.scroll.setWidget(self.detail)
        lay.addWidget(self.scroll, 1)
        self._show_empty()
        return wrap

    # ------------------------------------------------------------------ state
    def _set_category(self, key):
        self._cat = None if key == self._cat else key
        for k, b in self.cat_buttons.items():
            b.setChecked(k == self._cat)
        self._all_button.setChecked(self._cat is None)
        self._style_chips()
        self.refresh()

    def refresh(self, light=True):
        """Re-run the query and redraw the list."""
        self._details = self.wrepo.details_map()
        muscles = self.wrepo.muscles()
        current = self.muscle_combo.currentData()
        self.muscle_combo.blockSignals(True)
        self.muscle_combo.clear()
        self.muscle_combo.addItem("All muscle groups", None)
        for m in muscles:
            self.muscle_combo.addItem(m, m)
        i = self.muscle_combo.findData(current)
        self.muscle_combo.setCurrentIndex(i if i >= 0 else 0)
        self.muscle_combo.blockSignals(False)

        rows = self.wrepo.exercises(category=self._cat, difficulty=self.diff_combo.currentData(),
                                    search=self.search.text(), muscle=self.muscle_combo.currentData(),
                                    favorites=True if self.fav_only.isChecked() else None)
        self._rows = rows
        keep = self.current_id
        self.list.blockSignals(True)
        self.list.clear()
        for ex in rows:
            it = QListWidgetItem()
            it.setData(Qt.UserRole, ex["id"])
            color = QColor(EX_CATEGORIES.get(ex["category"], ("", "#8b95a7"))[1])
            it.setForeground(color)
            it.setText(f"{ex['name']}\n{DIFFICULTY[ex['difficulty']]} · "
                       f"{EX_CATEGORIES.get(ex['category'], (ex['category'], ''))[0]}")
            it.setToolTip(ex["instructions"] or ex["name"])
            self.list.addItem(it)
        self.list.blockSignals(False)
        n = len(rows)
        self.count_label.setText(f"{n} exercise{'s' if n != 1 else ''}")
        if rows:
            self.list.setCurrentRow(0)
            if keep:
                for i in range(self.list.count()):
                    if self.list.item(i).data(Qt.UserRole) == keep:
                        self.list.setCurrentRow(i)
                        break
        else:
            self.current_id = None
            self._show_empty()
        if light and self.current_id:
            # only rebuild the detail panel when something really changed
            if self._signature(self.current_id) != self._detail_sig:
                self._render_detail()
        elif self.current_id:
            self._render_detail()

    def _on_select(self, item, _prev=None):
        if item is None:
            self.current_id = None
            self._show_empty()
            return
        ex_id = item.data(Qt.UserRole)
        if ex_id != self.current_id:
            self.current_id = ex_id
            self._render_detail()
            self.exerciseSelected.emit(ex_id)

    # ----------------------------------------------------------------- detail
    def _stop_player(self):
        """Stop the running animation before the widget is thrown away."""
        player = getattr(self, "player", None)
        if player is not None:
            try:
                player.stop()
            except RuntimeError:
                pass

    def _show_empty(self):
        self._stop_player()
        clear_layout(self.detail_layout)
        lab = QLabel("Select an exercise to see its technique, muscles and animation.")
        lab.setObjectName("muted")
        lab.setWordWrap(True)
        self.detail_layout.addWidget(lab)

    def _section(self, title, rows, color="#8b95a7"):
        """A titled block of short lines."""
        card = Card(title)
        if not rows:
            lab = QLabel("—")
            lab.setObjectName("muted")
            card.lay.addWidget(lab)
            return card
        for text in rows:
            lab = QLabel(f"• {text}")
            lab.setWordWrap(True)
            lab.setTextFormat(Qt.RichText)
            lab.setObjectName("plain")
            card.lay.addWidget(lab)
        return card

    def _link_row(self, ex_ids):
        """Clickable buttons for related exercises."""
        row = QHBoxLayout()
        wrap = QWidget()
        wrap.setObjectName("plain")
        row.setSpacing(6)
        any_btn = False
        for ex_id in ex_ids:
            ex = self.wrepo.exercise(ex_id)
            if not ex:
                continue
            any_btn = True
            b = QPushButton(ex["name"])
            b.setObjectName("ghost")
            b.setToolTip(ex["instructions"] or ex["name"])
            b.clicked.connect(lambda _=False, i=ex_id: self._open(i))
            row.addWidget(b)
        if not any_btn:
            lab = QLabel("—")
            lab.setObjectName("muted")
            row.addWidget(lab)
        wrap.setLayout(row)
        return wrap

    def _open(self, ex_id):
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == ex_id:
                self.list.setCurrentRow(i)
                return
        self._cat = None
        for k, b in self.cat_buttons.items():
            b.setChecked(False)
        self._all_button.setChecked(True)
        self._style_chips()
        self.search.setText("")
        self.diff_combo.setCurrentIndex(0)
        self.refresh()
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == ex_id:
                self.list.setCurrentRow(i)
                break

    def select_exercise(self, ex_id):
        """Show one exercise (used when the builder sends the user here)."""
        self._open(ex_id)

    def _signature(self, ex_id):
        """Everything that can change the detail panel of one exercise."""
        ex = self.wrepo.exercise(ex_id) or {}
        det = self._details.get(ex_id, {})
        rank = None
        if self.ranks is not None:
            res = self.ranks.result_for_exercise(ex_id)
            rank = (res.rank, res.headline, res.goal) if res else None
        return (ex.get("name"), ex.get("difficulty"), ex.get("kind"), ex.get("default_sets"),
                ex.get("default_amount"), ex.get("default_rest"), ex.get("instructions"),
                det.get("muscles"), det.get("mistakes"), det.get("tips"), det.get("easier"),
                det.get("harder"), det.get("prerequisites"), det.get("related"), det.get("equipment"),
                rank, self.profiles.is_favorite(ex_id))

    def _render_detail(self):
        ex = self.wrepo.exercise(self.current_id)
        if not ex:
            self._show_empty()
            return
        det = self._details.get(ex["id"], {})
        self._stop_player()
        clear_layout(self.detail_layout)

        cat_label, cat_color = EX_CATEGORIES.get(ex["category"], (ex["category"], "#8b95a7"))

        # ---- header
        head = Card()
        title = QLabel(ex["name"])
        title.setObjectName("pageTitle")
        head.lay.addWidget(title)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addWidget(chip(cat_label, cat_color))
        chips.addWidget(chip(DIFFICULTY[ex["difficulty"]], "#ffd43b"))
        chips.addWidget(chip("hold" if ex["kind"] == "hold" else "reps", "#38d9a9"))
        if det.get("equipment"):
            chips.addWidget(chip(det["equipment"], "#9775fa"))
        chips.addStretch(1)
        wrap = QWidget()
        wrap.setObjectName("plain")
        wrap.setLayout(chips)
        head.lay.addWidget(wrap)

        # ---- buttons
        buttons = QHBoxLayout()
        self.btn_fav = QPushButton()
        self.btn_fav.setObjectName("ghost")
        self.btn_fav.clicked.connect(self._toggle_fav)
        self.btn_anim = QPushButton("Show animation")
        self.btn_anim.setObjectName("ghost")
        self.btn_anim.clicked.connect(self._toggle_anim)
        self.btn_add = QPushButton("Add to workout  →")
        self.btn_add.setObjectName("primary")
        self.btn_add.clicked.connect(self._add_to_workout)
        buttons.addWidget(self.btn_fav)
        buttons.addWidget(self.btn_anim)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_add)
        bwrap = QWidget()
        bwrap.setObjectName("plain")
        bwrap.setLayout(buttons)
        head.lay.addWidget(bwrap)

        # ---- rank
        rank_text = ""
        if self.ranks is not None:
            res = self.ranks.result_for_exercise(ex["id"])
            if res is not None:
                rank_text = (f"{rank_html(res.rank)} &nbsp;<span style='color:#8b95a7'>"
                             f"{res.headline} · next: {res.goal}</span>")
        if rank_text:
            lab = QLabel(rank_text)
            lab.setTextFormat(Qt.RichText)
            lab.setObjectName("plain")
            head.lay.addWidget(lab)
        self.detail_layout.addWidget(head)

        # ---- animation
        self.player = AnimationPlayer(anim_for_exercise(ex))
        self.player.setMinimumHeight(300)
        self.player.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.anim_box = self.player
        self.detail_layout.addWidget(self.player)
        self._anim_shown = True

        # ---- technique
        technique = (det.get("technique") or ex["instructions"] or "").split("\n")
        self.detail_layout.addWidget(self._section("Technique", [t.strip(" -•") for t in technique if t.strip()]))

        # ---- prescription
        amount = (f"{ex['default_amount']} s" if ex["kind"] == "hold" else f"{ex['default_amount']} reps")
        presc = [f"Recommended: {ex['default_sets']} × {amount}",
                 f"Rest between sets: {ex['default_rest']} s"]
        if det.get("equipment"):
            presc.append(f"Equipment: {det['equipment']}")
        self.detail_layout.addWidget(self._section("Sets, reps and rest", presc))

        # ---- muscles
        muscles = [m.strip() for m in (det.get("muscles") or "").split(",") if m.strip()]
        self.detail_layout.addWidget(self._section("Main muscle groups", muscles))

        # ---- mistakes + tips
        self.detail_layout.addWidget(self._section("Common mistakes", _split(det.get("mistakes"))))
        self.detail_layout.addWidget(self._section("Tips", _split(det.get("tips"))))

        # ---- progressions
        card = Card("Progressions")
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.addWidget(QLabel("Easier"), 0, 0)
        grid.addWidget(QLabel("Harder"), 0, 1)
        grid.addWidget(self._link_row(_split_ids(det.get("easier"))), 1, 0)
        grid.addWidget(self._link_row(_split_ids(det.get("harder"))), 1, 1)
        card.lay.addLayout(grid)
        card.lay.addWidget(QLabel("Prerequisites"))
        card.lay.addWidget(self._link_row(_split_ids(det.get("prerequisites"))))
        card.lay.addWidget(QLabel("Related exercises"))
        card.lay.addWidget(self._link_row(_split_ids(det.get("related"))))
        self.detail_layout.addWidget(card)

        self.detail_layout.addStretch(1)
        self._update_fav_button()
        self._detail_sig = self._signature(ex["id"])

    # --------------------------------------------------------------- actions
    def _update_fav_button(self):
        if not self.current_id:
            return
        fav = self.profiles.is_favorite(self.current_id)
        self.btn_fav.setText("★ Favourite" if fav else "☆ Favourite")
        self.btn_fav.setToolTip("Remove from favourites" if fav else "Add to favourites")

    def _toggle_fav(self):
        if not self.current_id:
            return
        state = self.profiles.toggle_favorite(self.current_id)
        self._update_fav_button()
        self.message.emit(f"{'Added to' if state else 'Removed from'} favourites")
        if self.fav_only.isChecked() and not state:
            self.refresh()

    def _toggle_anim(self):
        self._anim_shown = not self._anim_shown
        self.player.setVisible(self._anim_shown)
        self.btn_anim.setText("Hide animation" if self._anim_shown else "Show animation")

    def _add_to_workout(self):
        if not self.current_id:
            return
        ex = self.wrepo.exercise(self.current_id)
        self.addToWorkout.emit(self.current_id)
        self.message.emit(f"{ex['name']} sent to the Workout Builder")
