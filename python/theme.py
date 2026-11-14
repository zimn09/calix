"""Colours and the global Qt stylesheet (pure Python: the stylesheet is generated from the user settings)."""
import re

STATUS_COLORS = {
    "locked": "#6b7a8f",
    "available": "#4dd0e1",
    "training": "#ffa94d",
    "completed": "#69db7c",
}
STATUS_LABELS = {
    "locked": "Locked",
    "available": "Available to train",
    "training": "Training",
    "completed": "Completed",
}


def qss():
    return """
QWidget { background: #080b11; color: #e8edf5; font-size: 10pt; }
QLabel { background: transparent; }
QMainWindow, QSplitter::handle { background: #080b11; }
QSplitter::handle { width: 1px; background: #1b2534; }

/* ---------------------------------------------------------------- chrome */
#topbar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0e141e, stop:1 #0a0f17);
    border-bottom: 1px solid #1b2534;
}
#brand { font-size: 15pt; font-weight: 900; letter-spacing: 3px; color: #ffffff; }
#brandSub { color: #5f6d82; font-size: 7.5pt; font-weight: 600; letter-spacing: 1.6px; }
#subbar { background: transparent; border-bottom: 1px solid #151d29; }
#sidebar { background: #0a0f17; }
#pages { background: #080b11; }
QStatusBar { background: #0a0f17; color: #6d7c92; border-top: 1px solid #151d29; }
QStatusBar::item { border: none; }

/* ------------------------------------------------------------------ text */
#pageTitle { font-size: 21pt; font-weight: 800; color: #ffffff; letter-spacing: -0.3px; }
#skillTitle { font-size: 18pt; font-weight: 800; color: #ffffff; letter-spacing: -0.2px; }
#muted { color: #8593a8; }
#levelLabel { font-size: 15pt; font-weight: 800; color: #ffd43b; }
#sectionTitle {
    color: #7c8aa1; font-size: 8pt; font-weight: 800; letter-spacing: 1.4px;
}
#bigValue { font-size: 21pt; font-weight: 800; color: #ffffff; letter-spacing: -0.4px; }
#bigTime { font-size: 42pt; font-weight: 800; color: #ffffff; letter-spacing: -1px; }
#clock { font-size: 15pt; font-weight: 800; color: #ffd43b; }
#chip { border-radius: 9px; padding: 3px 10px; font-size: 8.5pt; font-weight: 700; }
#seg { padding: 6px 18px; border-radius: 8px; }

/* ----------------------------------------------------------------- cards */
QFrame#card, QFrame#rankCard, QFrame#achCard, QFrame#avatarCard {
    background: #0f1622;
    border: 1px solid #1d2836;
    border-radius: 16px;
}
QFrame#avatarCard:hover { border: 1px solid #33465f; background: #121b28; }
QWidget#welcome {
    background: #0f1622; border: 1px solid #1d2836; border-radius: 20px;
}
QWidget#plain { background: transparent; }
QScrollArea#pageScroll, QScrollArea#pageScroll > QWidget { background: transparent; }
QScrollArea#pageScroll { border: none; }

/* --------------------------------------------------------------- buttons */
QPushButton {
    background: #16202f; border: 1px solid #243349; border-radius: 10px;
    padding: 8px 16px; color: #dfe7f2; font-weight: 600;
}
QPushButton:hover { background: #1d2a3c; border-color: #33465f; color: #ffffff; }
QPushButton:pressed { background: #121b28; border-color: #2b3c54; }
QPushButton:focus { border: 1px solid #4dabf7; }
QPushButton:disabled { color: #46536a; background: #0d141e; border-color: #19222f; }
QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4dabf7, stop:1 #2f7fd8);
    border: 1px solid #4dabf7; color: #ffffff; font-weight: 700; border-radius: 10px;
}
QPushButton#primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #63b8ff, stop:1 #3a8ce5);
}
QPushButton#primary:pressed { background: #2f7fd8; }
QPushButton#primary:disabled {
    background: #14213a; border-color: #1d2c48; color: #46536a;
}
QPushButton#success {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2aa46a, stop:1 #1f7a4d);
    border: 1px solid #35bd7d; color: #ffffff; font-weight: 700; border-radius: 10px;
}
QPushButton#success:hover { background: #2fb874; }
QPushButton#success:disabled { background: #10201a; border-color: #1a2f26; color: #46536a; }
QPushButton#ghost { background: #121a26; border: 1px solid #22314a; color: #c8d3e2; }
QPushButton#ghost:hover { background: #182333; border-color: #33465f; color: #ffffff; }
QPushButton#ghost:disabled { color: #46536a; background: #0d141e; border-color: #19222f; }
QPushButton#danger { color: #ff8b8b; border-color: #3a2028; }
QPushButton#danger:hover { background: #2a1519; border-color: #5c2a31; }
QPushButton#tool { padding: 6px 12px; font-weight: 700; }
QPushButton#small { padding: 4px 10px; font-size: 9pt; border-radius: 9px; }
QPushButton#chipButton { font-weight: 600; border-radius: 999px; padding: 6px 14px; }
QPushButton#chipButton:checked { background: #22304a; border-color: #4dabf7; }

/* ------------------------------------------------------------------- nav */
QPushButton#nav {
    background: transparent; border: 1px solid transparent; border-radius: 9px;
    padding: 8px 14px; color: #8593a8; font-weight: 600;
}
QPushButton#nav:hover { color: #e8edf5; background: #131c28; }
QPushButton#nav:checked {
    color: #ffffff; background: #182535; border: 1px solid #2a3d56;
}
QPushButton#seg:checked { background: #22304a; border-color: #4dabf7; color: #ffffff; }

/* ---------------------------------------------------------------- inputs */
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QDateEdit, QPlainTextEdit {
    background: #101a27; border: 1px solid #22314a; border-radius: 10px;
    padding: 9px 12px; selection-background-color: #2f7fd8; selection-color: #ffffff;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QDateEdit:hover {
    border-color: #2d405c;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus,
QDateEdit:focus, QPlainTextEdit:focus { border: 1px solid #4dabf7; background: #121d2b; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: #101a27; border: 1px solid #22314a; border-radius: 10px;
    selection-background-color: #22304a; outline: 0; padding: 4px;
}
QCheckBox { spacing: 9px; background: transparent; }

/* ----------------------------------------------------------------- tabs */
QTabWidget::pane { border: none; }
QTabBar::tab {
    background: transparent; padding: 10px 20px; color: #8593a8;
    border-bottom: 2px solid transparent; font-weight: 700;
}
QTabBar::tab:selected { color: #ffffff; border-bottom: 2px solid #4dabf7; }
QTabBar::tab:hover { color: #d6dfeb; }

/* -------------------------------------------------------------- surfaces */
QTextBrowser { background: #0d141f; border: 1px solid #1d2836; border-radius: 12px; padding: 8px; }
QGroupBox {
    border: 1px solid #1d2836; border-radius: 12px; margin-top: 14px; padding: 16px 12px 10px 12px;
}
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; color: #8593a8; }
QProgressBar {
    background: #131c28; border: none; border-radius: 5px; max-height: 8px; min-height: 8px;
}
QProgressBar::chunk {
    border-radius: 5px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4dabf7, stop:1 #3b82f6);
}
QListWidget {
    background: #0d141f; border: 1px solid #1d2836; border-radius: 12px; padding: 6px; outline: 0;
}
QListWidget::item { padding: 8px 10px; border-radius: 8px; }
QListWidget::item:selected { background: #22304a; color: #ffffff; }
QListWidget::item:hover { background: #182333; }
QTableWidget {
    background: #0d141f; border: 1px solid #1d2836; border-radius: 12px; gridline-color: #1a2432;
}
QTableWidget::item:selected { background: #22304a; }
QHeaderView::section {
    background: #111a26; color: #8593a8; border: none; padding: 8px; font-weight: 700;
}

/* ------------------------------------------------------------ scrollbars */
QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; }
QScrollBar::handle:vertical { background: #22314a; border-radius: 4px; min-height: 32px; }
QScrollBar::handle:vertical:hover { background: #2f4361; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 9px; margin: 2px; }
QScrollBar::handle:horizontal { background: #22314a; border-radius: 4px; min-width: 32px; }
QScrollBar::handle:horizontal:hover { background: #2f4361; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ----------------------------------------------------------------- menus */
QMenuBar { background: #0e141e; }
QMenuBar::item { padding: 6px 12px; background: transparent; }
QMenuBar::item:selected { background: #16202f; border-radius: 6px; }
QMenu { background: #101a27; border: 1px solid #22314a; padding: 6px; border-radius: 10px; }
QMenu::item { padding: 7px 26px; border-radius: 6px; }
QMenu::item:selected { background: #22304a; }
QMenu::separator { height: 1px; background: #22314a; margin: 5px 8px; }
QToolTip {
    background: #101a27; color: #e8edf5; border: 1px solid #2a3a4e;
    padding: 7px 9px; border-radius: 8px;
}
QMessageBox { background: #0e141e; }
QDialog { background: #080b11; }
QCalendarWidget QWidget { background: #0f1622; }
"""


# ---------------------------------------------------------------- user themes
ACCENTS = [("Blue", "#4dabf7"), ("Purple", "#9775fa"), ("Red", "#ff6b6b"), ("Green", "#51cf66"),
           ("Orange", "#ff922b"), ("Teal", "#22b8cf")]

# preset -> {default colour in the base stylesheet: replacement}. Charcoal is the original look.
_NEUTRAL = {
    "black": {
        "#080b11": "#000000", "#0e141e": "#04060a", "#0a0f17": "#030408", "#0d141f": "#05070b",
        "#0f1622": "#06080c", "#101a27": "#080b10", "#111a26": "#080a0f", "#121a26": "#090b10",
        "#121b28": "#0a0c11", "#121d2b": "#0b0d12", "#131c28": "#0a0c11", "#16202f": "#101318",
        "#182333": "#111419", "#182535": "#111419", "#1b2534": "#15181d", "#1d2836": "#171a20",
        "#19222f": "#14171c", "#1a2432": "#15181d", "#22314a": "#23262d", "#243349": "#25282f",
        "#2a3d56": "#2b2f38", "#2d405c": "#2f333c", "#2f4361": "#33373f", "#33465f": "#383d49",
        "#3a2028": "#2a1519", "#5c2a31": "#4a2229",
    },
    "graphite": {
        "#080b11": "#14161a", "#0e141e": "#191c21", "#0a0f17": "#16181d", "#0d141f": "#1a1d22",
        "#0f1622": "#1c1f25", "#101a27": "#20242a", "#111a26": "#23262d", "#121a26": "#22252b",
        "#121b28": "#23262d", "#121d2b": "#25282f", "#131c28": "#262a31", "#16202f": "#2a2e36",
        "#182333": "#2e323a", "#182535": "#2f333b", "#1b2534": "#2c3039", "#1d2836": "#2e323b",
        "#19222f": "#272b33", "#1a2432": "#2b2f38", "#22314a": "#3a3f4b", "#243349": "#3d4250",
        "#2a3d56": "#444a58", "#2d405c": "#474d5c", "#2f4361": "#4a505e", "#33465f": "#525867",
        "#3a2028": "#3a2028", "#5c2a31": "#5c2a31",
    },
}
BG_LABELS = {"charcoal": "Charcoal", "black": "Pure black", "graphite": "Dark gray",
             "gradient": "Gradient", "pattern": "Subtle pattern"}


def hex_mix(a, b, t):
    """Blend colour a into b by factor t (0..1); both are #rrggbb."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x * t + y * (1 - t)):02x}" for x, y in zip(ca, cb))


def bg_base(cfg):
    """Window background colour of the chosen preset."""
    return _NEUTRAL.get(cfg["bg"], {}).get("#080b11", "#080b11")


def canvas_colors(cfg):
    """(top, bottom) colours of the skill-tree canvas."""
    top = bg_base(cfg)
    if cfg["bg"] == "gradient":
        return top, hex_mix(cfg["accent"], top, 0.28)
    return top, hex_mix("#0b1018", top, 1.0) if cfg["bg"] == "charcoal" else top


def build_qss(cfg, pattern_path=None):
    """Complete application stylesheet for the given settings."""
    css = qss()
    bg, accent = bg_base(cfg), cfg["accent"]
    repl = dict(_NEUTRAL.get(cfg["bg"], {}))
    repl.update({
        "#4dabf7": accent, "#3b82f6": accent,
        "#2f7fd8": hex_mix(accent, "#000000", 0.78),
        "#3a8ce5": hex_mix(accent, "#000000", 0.85),
        "#63b8ff": hex_mix(accent, "#ffffff", 0.85),
        "#22304a": hex_mix(accent, bg, 0.30),
        "#182535": hex_mix(accent, bg, 0.14),
        "#16202f": hex_mix(accent, bg, 0.10),
        "#14213a": hex_mix(accent, bg, 0.12),
        "#1d2c48": hex_mix(accent, bg, 0.18),
        "#2d405c": hex_mix(accent, bg, 0.22),
        "#2f4361": hex_mix(accent, bg, 0.26),
        "#22314a": hex_mix(accent, bg, 0.20),
    })
    css = re.sub("|".join(re.escape(k) for k in repl), lambda m: repl[m.group(0).lower()], css, flags=re.I)

    radius = {"sharp": 0.25, "rounded": 1.0, "round": 1.5}[cfg["corners"]]
    css = re.sub(r"border-radius: (\d+)px", lambda m: f"border-radius: {max(1, round(int(m.group(1)) * radius))}px", css)
    scale = cfg["font_size"] / 10
    css = re.sub(r"font-size: ([\d.]+)pt", lambda m: f"font-size: {round(float(m.group(1)) * scale, 1):g}pt", css)

    if cfg["bg"] == "gradient":
        backdrop = (f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {bg}, "
                    f"stop:0.55 {hex_mix(accent, bg, 0.10)}, stop:1 {hex_mix(accent, bg, 0.26)});")
    elif cfg["bg"] == "pattern" and pattern_path:
        backdrop = f"background-color: {bg}; background-image: url({pattern_path});"
    else:
        backdrop = f"background: {bg};"
    css += f"""
QStackedWidget#pages {{ {backdrop} }}
QSplitter#pageSplit, QStackedWidget#inner, QScrollArea#pageScroll,
QScrollArea#pageScroll > QWidget {{ background: transparent; }}
"""
    return css
