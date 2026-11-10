"""Settings page. Every control writes to Settings immediately, and the app restyles itself live."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QColorDialog, QComboBox, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget)

from audio import TRACKS
from theme import ACCENTS, BG_LABELS, bg_base, hex_mix
from ui_common import Card, confirm, plain

SAMPLE_CATEGORY = ("#ff6b6b", "#4dabf7", "#ffd43b")      # colours the preview uses in 'by category' mode


class TreePreview(QWidget):
    """Three sample nodes (completed, unlocked, locked) painted with the current skill-tree colours."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = None
        self.setFixedHeight(96)

    def set_config(self, cfg):
        self.cfg = cfg
        self.update()

    def paintEvent(self, _):
        if not self.cfg:
            return
        c, p = self.cfg, QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(bg_base(c)))
        w, h = 120, 40
        gap = (self.width() - 3 * w) / 4
        y = (self.height() - h) / 2
        xs = [gap + i * (w + gap) for i in range(3)]
        node = [QColor(c["tree_node_color"]) if c["tree_node_mode"] == "custom" else QColor(s) for s in SAMPLE_CATEGORY]
        edge = [QColor(c["tree_edge_color"]) if c["tree_edge_mode"] == "custom" else QColor(s) for s in SAMPLE_CATEGORY]
        unlock = QColor(c["tree_unlock_color"]) if c["tree_unlock_mode"] == "custom" else node[1]
        # connections: done -> unlocked is lit, unlocked -> locked is idle
        p.setPen(QPen(edge[0], 3))
        p.drawLine(int(xs[0] + w), int(y + h / 2), int(xs[1]), int(y + h / 2))
        p.setPen(QPen(QColor("#2a3242"), 2))
        p.drawLine(int(xs[1] + w), int(y + h / 2), int(xs[2]), int(y + h / 2))
        specs = ((xs[0], "Completed", QColor("#10141b"), node[0], node[0]),
                 (xs[1], "Unlocked", QColor("#1a2230"), unlock, node[1]),
                 (xs[2], "Locked", QColor("#11151d"), QColor("#2b3341"), QColor("#2b3341")))
        for i, (x, label, fill, border, accent) in enumerate(specs):
            rect = QRectF(x, y, w, h)
            if i == 1 and c["effects"]:
                g = QColor(unlock)
                g.setAlpha(70)
                p.setPen(QPen(g, 9))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(rect, 10, 10)
            if i == 0:
                fill = QColor(hex_mix(node[0].name(), "#10141b", 0.4))
            p.setBrush(QBrush(fill))
            p.setPen(QPen(border, 2))
            p.drawRoundedRect(rect, 10, 10)
            p.setPen(Qt.NoPen)
            p.setBrush(accent)
            p.drawRoundedRect(QRectF(x + 6, y + 8, 3, h - 16), 1.5, 1.5)
            p.setPen(QColor("#e6e9ef") if i < 2 else QColor("#6b7686"))
            p.drawText(rect.adjusted(16, 0, 0, 0), int(Qt.AlignVCenter | Qt.AlignLeft), label)


class SettingsPage(QWidget):
    def __init__(self, settings, audio=None, parent=None):
        super().__init__(parent)
        self.s = settings
        self.audio = audio
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("pageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)
        body = plain()
        scroll.setWidget(body)
        row = QHBoxLayout(body)
        inner = plain()
        inner.setMaximumWidth(880)
        row.addStretch(1)
        row.addWidget(inner, 10)
        row.addStretch(1)
        v = QVBoxLayout(inner)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(12)

        title = QLabel("Settings")
        title.setObjectName("pageTitle")
        sub = QLabel("Changes apply instantly and are saved automatically.")
        sub.setObjectName("muted")
        v.addWidget(title)
        v.addWidget(sub)

        # ---- background
        card = Card("Background")
        r = QHBoxLayout()
        self.bg_group, self.bg_buttons = QButtonGroup(self), {}
        for key, label in BG_LABELS.items():
            b = QPushButton(label)
            b.setCheckable(True)
            b.setMinimumSize(120, 64)
            b.setCursor(Qt.PointingHandCursor)
            self.bg_group.addButton(b)
            b.clicked.connect(lambda _=False, k=key: self.s.set("bg", k))
            r.addWidget(b)
            self.bg_buttons[key] = b
        card.lay.addLayout(r)
        v.addWidget(card)

        # ---- accent
        card = Card("Color theme")
        r = QHBoxLayout()
        self.acc_group, self.acc_buttons = QButtonGroup(self), {}
        for name, hexv in ACCENTS:
            b = QPushButton(name)
            b.setCheckable(True)
            b.setMinimumHeight(40)
            b.setCursor(Qt.PointingHandCursor)
            self.acc_group.addButton(b)
            b.clicked.connect(lambda _=False, h=hexv: self.s.set("accent", h))
            r.addWidget(b)
            self.acc_buttons[hexv] = b
        self.acc_custom = QPushButton("Custom…")
        self.acc_custom.setCheckable(True)
        self.acc_custom.setMinimumHeight(40)
        self.acc_group.addButton(self.acc_custom)
        self.acc_custom.clicked.connect(lambda: self._pick("accent", "Accent color"))
        r.addWidget(self.acc_custom)
        card.lay.addLayout(r)
        v.addWidget(card)

        # ---- skill tree
        card = Card("Skill tree")
        self.preview = TreePreview()
        card.lay.addWidget(self.preview)
        self.tree_rows = {}
        for label, prefix in (("Skill nodes", "tree_node"), ("Connections", "tree_edge"),
                              ("Unlocked skills highlight", "tree_unlock")):
            r = QHBoxLayout()
            name = QLabel(label)
            name.setFixedWidth(190)
            combo = QComboBox()
            combo.addItem("By category", "category")
            combo.addItem("Custom color", "custom")
            btn = QPushButton("")
            btn.setFixedWidth(110)
            combo.currentIndexChanged.connect(lambda _=0, p=prefix, c=combo: self.s.set(p + "_mode", c.currentData()))
            btn.clicked.connect(lambda _=False, p=prefix, l=label: self._pick(p + "_color", l))
            for w in (name, combo, btn):
                r.addWidget(w)
            r.addStretch(1)
            card.lay.addLayout(r)
            self.tree_rows[prefix] = (combo, btn)
        v.addWidget(card)

        # ---- animations
        card = Card("Animations and effects")
        self.c_anim = QCheckBox("Animations: pulsing unlocked skills, flowing connections, smooth camera, unlock flash")
        self.c_fx = QCheckBox("Glow effects around nodes and selections")
        self.c_anim.toggled.connect(lambda on: self.s.set("animations", on))
        self.c_fx.toggled.connect(lambda on: self.s.set("effects", on))
        card.lay.addWidget(self.c_anim)
        card.lay.addWidget(self.c_fx)
        v.addWidget(card)

        # ---- sound
        card = Card("Sound & Music")
        self.c_sfx = QCheckBox("Sound effects: button clicks, level-ups, achievements")
        self.c_sfx.toggled.connect(lambda on: self.s.set("sfx", on))
        card.lay.addWidget(self.c_sfx)

        r = QHBoxLayout()
        r.addWidget(QLabel("Effects volume"))
        self.sfx_slider = QSlider(Qt.Horizontal)
        self.sfx_slider.setRange(0, 100)
        self.sfx_slider.setFixedWidth(190)
        self.sfx_slider.setCursor(Qt.PointingHandCursor)
        self.sfx_label = QLabel("")
        self.sfx_label.setFixedWidth(46)
        self.sfx_slider.valueChanged.connect(self._sfx_volume_changed)
        self.sfx_slider.sliderReleased.connect(self._test_sound)
        test = QPushButton("Test")
        test.setObjectName("sfxTest")            # the global click sound skips this button
        test.setCursor(Qt.PointingHandCursor)
        test.clicked.connect(self._test_sound)
        r.addWidget(self.sfx_slider)
        r.addWidget(self.sfx_label)
        r.addSpacing(12)
        r.addWidget(test)
        r.addStretch(1)
        card.lay.addLayout(r)

        r = QHBoxLayout()
        self.c_music = QCheckBox("Background music")
        self.c_music.toggled.connect(lambda on: self.s.set("music", on))
        r.addWidget(self.c_music)
        r.addSpacing(12)
        self.music_combo = QComboBox()
        for t in TRACKS:
            self.music_combo.addItem(t["name"], t["id"])
        self.music_combo.addItem("No music", "none")
        self.music_combo.currentIndexChanged.connect(
            lambda _=0: self.s.set("music_track", self.music_combo.currentData()))
        r.addWidget(self.music_combo)
        r.addSpacing(16)
        r.addWidget(QLabel("Music volume"))
        self.music_slider = QSlider(Qt.Horizontal)
        self.music_slider.setRange(0, 100)
        self.music_slider.setFixedWidth(150)
        self.music_slider.setCursor(Qt.PointingHandCursor)
        self.music_label = QLabel("")
        self.music_label.setFixedWidth(46)
        self.music_slider.valueChanged.connect(self._music_volume_changed)
        r.addWidget(self.music_slider)
        r.addWidget(self.music_label)
        r.addStretch(1)
        card.lay.addLayout(r)

        self.audio_note = QLabel("Every sound is generated inside the app - nothing is downloaded.")
        self.audio_note.setObjectName("muted")
        self.audio_note.setWordWrap(True)
        card.lay.addWidget(self.audio_note)
        v.addWidget(card)

        # ---- interface
        card = Card("Interface")
        r = QHBoxLayout()
        self.font = QComboBox()
        for size, label in ((9, "Small"), (10, "Medium (default)"), (11, "Large"), (12, "Extra large")):
            self.font.addItem(f"{label}, {size} pt", size)
        self.corners = QComboBox()
        for key, label in (("sharp", "Sharp"), ("rounded", "Rounded (default)"), ("round", "Very round")):
            self.corners.addItem(label, key)
        self.font.currentIndexChanged.connect(lambda _=0: self.s.set("font_size", self.font.currentData()))
        self.corners.currentIndexChanged.connect(lambda _=0: self.s.set("corners", self.corners.currentData()))
        for text, w in (("Text size", self.font), ("Corners", self.corners)):
            r.addWidget(QLabel(text))
            r.addWidget(w)
            r.addSpacing(16)
        r.addStretch(1)
        card.lay.addLayout(r)
        self.c_rank = QCheckBox("Show rank badges on skill-tree nodes")
        self.c_grid = QCheckBox("Show dot grid on the skill-tree canvas")
        self.c_rank.toggled.connect(lambda on: self.s.set("rank_badges", on))
        self.c_grid.toggled.connect(lambda on: self.s.set("tree_grid", on))
        card.lay.addWidget(self.c_rank)
        card.lay.addWidget(self.c_grid)
        v.addWidget(card)

        # ---- reset
        card = Card("Reset")
        r = QHBoxLayout()
        note = QLabel("Restores every option above to its original value. Your training data is not affected.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        b = QPushButton("Restore default settings")
        b.setObjectName("danger")
        b.clicked.connect(self._reset)
        r.addWidget(note, 1)
        r.addWidget(b)
        card.lay.addLayout(r)
        v.addWidget(card)
        v.addStretch(1)

        settings.subscribe(lambda cfg: self.sync())
        self.sync()

    # --------------------------------------------------------------- helpers
    def _sfx_volume_changed(self, value):
        self.sfx_label.setText(f"{value}%")
        self.s.set("sfx_volume", value)

    def _music_volume_changed(self, value):
        self.music_label.setText(f"{value}%")
        self.s.set("music_volume", value)

    def _test_sound(self):
        if self.audio is not None:
            self.audio.sfx("click", force=True)

    def _pick(self, key, title):
        col = QColorDialog.getColor(QColor(self.s[key]), self, title)
        if col.isValid():
            self.s.set(key, col.name())
        else:
            self.sync()                      # cancelled: restore the checked state of the buttons

    def _reset(self):
        if confirm(self, "Restore defaults", "Reset all appearance settings to their defaults?"):
            self.s.reset()

    def sync(self):
        """Show the current settings in the controls (signals blocked so nothing is re-saved)."""
        cfg = self.s.all()
        widgets = [self.font, self.corners, self.c_anim, self.c_fx, self.c_rank, self.c_grid,
                   self.c_sfx, self.c_music, self.sfx_slider, self.music_slider, self.music_combo,
                   *[c for c, _ in self.tree_rows.values()]]
        for w in widgets:
            w.blockSignals(True)
        acc = cfg["accent"]
        gradient_preview = (f"qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {bg_base(cfg)}, stop:1 {hex_mix(acc, bg_base(cfg), 0.30)})")
        previews = {"charcoal": "#0b0e14", "black": "#000000", "graphite": "#15171b",
                    "gradient": gradient_preview, "pattern": "#0b0e14"}
        for key, b in self.bg_buttons.items():
            b.setChecked(cfg["bg"] == key)
            b.setStyleSheet(f"QPushButton {{ background: {previews[key]}; border: 2px solid #2a3548; "
                            f"border-radius: 10px; color: #e6e9ef; }} QPushButton:checked {{ border: 3px solid {acc}; }}")
        for hexv, b in self.acc_buttons.items():
            b.setChecked(acc == hexv)
            b.setStyleSheet(f"QPushButton {{ background: {hexv}; color: #10141b; font-weight: 700; "
                            f"border: 2px solid transparent; }} QPushButton:checked {{ border: 3px solid #ffffff; }}")
        custom = acc not in self.acc_buttons
        self.acc_custom.setChecked(custom)
        self.acc_custom.setStyleSheet(f"QPushButton {{ background: {acc if custom else '#182030'}; "
                                      f"color: {'#10141b' if custom else '#e6e9ef'}; font-weight: 700; "
                                      f"border: 2px solid transparent; }} QPushButton:checked {{ border: 3px solid #ffffff; }}")
        for prefix, (combo, btn) in self.tree_rows.items():
            custom_mode = cfg[prefix + "_mode"] == "custom"
            combo.setCurrentIndex(0 if not custom_mode else 1)
            btn.setEnabled(custom_mode)
            col = cfg[prefix + "_color"]
            btn.setText(col)
            btn.setStyleSheet(f"QPushButton {{ background: {col}; color: #10141b; font-weight: 700; }}"
                              if custom_mode else "")
        self.font.setCurrentIndex(max(0, self.font.findData(cfg["font_size"])))
        self.corners.setCurrentIndex(max(0, self.corners.findData(cfg["corners"])))
        self.c_anim.setChecked(cfg["animations"])
        self.c_fx.setChecked(cfg["effects"])
        self.c_rank.setChecked(cfg["rank_badges"])
        self.c_grid.setChecked(cfg["tree_grid"])
        self.c_sfx.setChecked(cfg["sfx"])
        self.c_music.setChecked(cfg["music"])
        self.sfx_slider.setValue(int(cfg["sfx_volume"]))
        self.music_slider.setValue(int(cfg["music_volume"]))
        self.sfx_label.setText(f"{int(cfg['sfx_volume'])}%")
        self.music_label.setText(f"{int(cfg['music_volume'])}%")
        self.music_combo.setCurrentIndex(max(0, self.music_combo.findData(cfg["music_track"])))
        self.music_slider.setEnabled(cfg["music"])
        self.music_combo.setEnabled(cfg["music"])
        if self.audio is None or not getattr(self.audio, "available", False):
            self.audio_note.setText("The audio backend (Qt Multimedia) is not available on this system - "
                                    "the settings are saved, but no sound will play.")
        for w in widgets:
            w.blockSignals(False)
        self.preview.set_config(cfg)
