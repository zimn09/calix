"""Colours and the global Qt stylesheet (pure Python: the stylesheet is generated from the user settings)."""
import re

STATUS_COLORS = {
    "locked": "#667085",
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
QWidget { background: #0b0e14; color: #e6e9ef; font-size: 10pt; }
QLabel { background: transparent; }
QMainWindow, QSplitter::handle { background: #0b0e14; }
QSplitter::handle { width: 1px; background: #1b2230; }
#topbar { background: #0f131b; border-bottom: 1px solid #1d2430; }
#brand { font-size: 13pt; font-weight: 800; letter-spacing: 2px; color: #ffffff; }
#brandSub { color: #6b7686; font-size: 8pt; letter-spacing: 1px; }
#sidebar { background: #0d1118; }
#skillTitle { font-size: 19pt; font-weight: 700; color: #ffffff; }
#muted { color: #8b95a7; }
#levelLabel { font-size: 15pt; font-weight: 700; color: #ffd43b; }

QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QDateEdit, QPlainTextEdit {
    background: #141a24; border: 1px solid #263042; border-radius: 8px;
    padding: 6px 10px; selection-background-color: #2563eb;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus, QDateEdit:focus, QPlainTextEdit:focus { border: 1px solid #4dabf7; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: #141a24; border: 1px solid #263042;
    selection-background-color: #22304a; outline: 0;
}

QPushButton {
    background: #182030; border: 1px solid #2a3548; border-radius: 8px; padding: 7px 14px;
}
QPushButton:hover { background: #1f2a3f; border-color: #3b4b66; }
QPushButton:pressed { background: #121a28; }
QPushButton:disabled { color: #4b5565; background: #10141b; border-color: #1c2331; }
QPushButton#primary { background: #2563eb; border-color: #3b82f6; color: white; font-weight: 600; }
QPushButton#primary:hover { background: #3b82f6; }
QPushButton#primary:disabled { background: #162038; border-color: #1c2a4a; color: #4b5565; }
QPushButton#success { background: #1f7a4d; border-color: #2fa56b; color: white; font-weight: 600; }
QPushButton#success:hover { background: #2a9460; }
QPushButton#success:disabled { background: #10201a; border-color: #1a2f26; color: #4b5565; }
QPushButton#tool { padding: 5px 11px; font-weight: 700; }

QTabWidget::pane { border: none; }
QTabBar::tab {
    background: transparent; padding: 10px 20px; color: #8b95a7;
    border-bottom: 2px solid transparent; font-weight: 600;
}
QTabBar::tab:selected { color: #ffffff; border-bottom: 2px solid #4dabf7; }
QTabBar::tab:hover { color: #d0d7e2; }

QTextBrowser {
    background: #0f141c; border: 1px solid #1c2431; border-radius: 10px; padding: 6px;
}
QGroupBox {
    border: 1px solid #1c2431; border-radius: 10px; margin-top: 12px; padding: 14px 10px 8px 10px;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #8b95a7; }

QProgressBar { background: #141a24; border: none; border-radius: 5px; max-height: 10px; min-height: 10px; }
QProgressBar::chunk { border-radius: 5px; background: #4dabf7; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #263042; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #34425a; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { height: 0; }

QMenuBar { background: #0f131b; }
QMenuBar::item { padding: 6px 12px; background: transparent; }
QMenuBar::item:selected { background: #1b2433; }
QMenu { background: #121822; border: 1px solid #263042; padding: 4px; }
QMenu::item { padding: 6px 26px; border-radius: 4px; }
QMenu::item:selected { background: #22304a; }
QMenu::separator { height: 1px; background: #263042; margin: 4px 8px; }
QStatusBar { background: #0f131b; color: #8b95a7; }
QToolTip { background: #121822; color: #e6e9ef; border: 1px solid #2a3548; padding: 6px; }
QMessageBox { background: #0f131b; }

QWidget#plain { background: transparent; }
QFrame#card { background: #0f141c; border: 1px solid #1c2431; border-radius: 12px; }
QLabel#sectionTitle { color: #8b95a7; font-size: 8.5pt; font-weight: 700; letter-spacing: 1px; }
QLabel#pageTitle { font-size: 17pt; font-weight: 700; color: #ffffff; }
QLabel#bigValue { font-size: 20pt; font-weight: 800; color: #ffffff; }
QLabel#bigTime { font-size: 40pt; font-weight: 800; color: #ffffff; }
QLabel#clock { font-size: 15pt; font-weight: 700; color: #ffd43b; }
QLabel#chip { border-radius: 6px; padding: 2px 8px; font-size: 8.5pt; font-weight: 600; }
QWidget#subbar { background: #0d1118; border-bottom: 1px solid #1b2230; }

QPushButton#nav {
    background: transparent; border: none; border-bottom: 2px solid transparent; border-radius: 0;
    padding: 10px 14px; color: #8b95a7; font-weight: 600;
}
QPushButton#nav:hover { color: #d0d7e2; background: transparent; }
QPushButton#nav:checked { color: #ffffff; border-bottom: 2px solid #4dabf7; }
QPushButton#seg { padding: 5px 16px; border-radius: 0; }
QPushButton#seg:checked { background: #22304a; border-color: #4dabf7; color: #ffffff; }
QPushButton#danger { color: #ff8787; }
QPushButton#danger:hover { background: #2a1519; border-color: #5c2a31; }
QPushButton#small { padding: 3px 9px; font-size: 9pt; }
QPushButton#ghost { background: #141a24; border: 1px solid #263042; color: #cdd5e0; }
QPushButton#ghost:hover { background: #1a2333; border-color: #3b4b66; color: #ffffff; }
QPushButton#ghost:disabled { color: #4b5565; background: #10141b; border-color: #1c2331; }
QPushButton#chipButton { font-weight: 600; }
QPushButton#chipButton:checked { background: #22304a; }

QFrame#avatarCard { background: #0f141c; border: 1px solid #1c2431; border-radius: 10px; }
QFrame#avatarCard:hover { border-color: #3b4b66; }
QWidget#welcome { background: #0b0e14; }

QListWidget { background: #0f141c; border: 1px solid #1c2431; border-radius: 10px; padding: 4px; outline: 0; }
QListWidget::item { padding: 7px 8px; border-radius: 6px; }
QListWidget::item:selected { background: #22304a; color: #ffffff; }
QListWidget::item:hover { background: #1a2333; }
QTableWidget { background: #0f141c; border: 1px solid #1c2431; border-radius: 10px; gridline-color: #1c2431; }
QTableWidget::item:selected { background: #22304a; }
QHeaderView::section { background: #141a24; color: #8b95a7; border: none; padding: 6px; font-weight: 600; }
QCheckBox { spacing: 8px; background: transparent; }
QDialog { background: #0b0e14; }
QCalendarWidget QWidget { background: #0f141c; }
"""


# ---------------------------------------------------------------- user themes
ACCENTS = [("Blue", "#4dabf7"), ("Purple", "#9775fa"), ("Red", "#ff6b6b"), ("Green", "#51cf66"),
           ("Orange", "#ff922b"), ("Teal", "#22b8cf")]

# preset -> {default colour in the base stylesheet: replacement}. Charcoal is the original look.
_NEUTRAL = {
    "black": {"#0b0e14": "#000000", "#0f131b": "#050608", "#0d1118": "#050608", "#121822": "#0b0c0f",
              "#0f141c": "#08090c", "#141a24": "#0f1115", "#182030": "#14171c",
              "#1c2431": "#17191f", "#1d2430": "#17191f", "#1b2230": "#17191f", "#1c2331": "#17191f",
              "#263042": "#22252d", "#2a3548": "#2b2f38", "#1f2a3f": "#1a1d24", "#1a2333": "#14171d",
              "#1b2433": "#14171d", "#121a28": "#0b0d11", "#10141b": "#0a0b0e", "#34425a": "#2b2f38",
              "#3b4b66": "#383d49"},
    "graphite": {"#0b0e14": "#15171b", "#0f131b": "#1a1d22", "#0d1118": "#181b20", "#121822": "#20242a",
                 "#0f141c": "#1c1f25", "#141a24": "#23262d", "#182030": "#2a2e36",
                 "#1c2431": "#2c3039", "#1d2430": "#2c3039", "#1b2230": "#2c3039", "#1c2331": "#2c3039",
                 "#263042": "#3a3f4b", "#2a3548": "#444a58", "#1f2a3f": "#2f333c", "#1a2333": "#272b33",
                 "#1b2433": "#272b33", "#121a28": "#1a1d22", "#10141b": "#16181d", "#34425a": "#4a505e",
                 "#3b4b66": "#525867"},
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
    return _NEUTRAL.get(cfg["bg"], {}).get("#0b0e14", "#0b0e14")


def canvas_colors(cfg):
    """(top, bottom) colours of the skill-tree canvas."""
    top = bg_base(cfg)
    if cfg["bg"] == "gradient":
        return top, hex_mix(cfg["accent"], top, 0.28)
    return top, hex_mix("#0d121c", top, 1.0) if cfg["bg"] == "charcoal" else top


def build_qss(cfg, pattern_path=None):
    """Complete application stylesheet for the given settings."""
    css = qss()
    bg, accent = bg_base(cfg), cfg["accent"]
    repl = dict(_NEUTRAL.get(cfg["bg"], {}))
    repl.update({
        "#4dabf7": accent, "#3b82f6": accent,
        "#2563eb": hex_mix(accent, "#000000", 0.72),
        "#22304a": hex_mix(accent, bg, 0.30),
        "#162038": hex_mix(accent, bg, 0.14),
        "#1c2a4a": hex_mix(accent, bg, 0.20),
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
