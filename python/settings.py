"""Application settings stored in the local SQLite database (no Qt).

Every option has a default, is validated, is saved the moment it changes and
notifies subscribers so the UI can react immediately.
"""
import json
import re

DEFAULTS = {
    "bg": "charcoal",                 # charcoal | black | graphite | gradient | pattern
    "accent": "#4dabf7",
    "tree_node_mode": "category",     # category | custom
    "tree_node_color": "#4dabf7",
    "tree_edge_mode": "category",
    "tree_edge_color": "#4dabf7",
    "tree_unlock_mode": "category",   # highlight of skills that are available to train
    "tree_unlock_color": "#ffd43b",
    "animations": True,
    "effects": True,                  # glow effects
    "font_size": 10,
    "corners": "rounded",             # sharp | rounded | round
    "rank_badges": True,              # rank badge on skill-tree nodes
    "tree_grid": True,                # dot grid on the skill-tree canvas
    "sfx": True,                      # button clicks and event sounds
    "sfx_volume": 60,                 # 0-100
    "music": True,                    # background music
    "music_track": "temple",          # temple | forge | void | dawn | none
    "music_volume": 30,               # 0-100
}

CHOICES = {
    "bg": ("charcoal", "black", "graphite", "gradient", "pattern"),
    "tree_node_mode": ("category", "custom"),
    "tree_edge_mode": ("category", "custom"),
    "tree_unlock_mode": ("category", "custom"),
    "font_size": (9, 10, 11, 12),
    "corners": ("sharp", "rounded", "round"),
    "music_track": ("temple", "forge", "void", "dawn", "none"),
}
COLOR_KEYS = ("accent", "tree_node_color", "tree_edge_color", "tree_unlock_color")
VOLUME_KEYS = ("sfx_volume", "music_volume")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class Settings:
    def __init__(self, db):
        self.db = db
        self.values = dict(DEFAULTS)
        self._subs = []
        self._load()

    def _load(self):
        for key, raw in self.db.execute("SELECT key, value FROM settings"):
            if key in DEFAULTS:
                try:
                    self.values[key] = self._check(key, json.loads(raw))
                except (ValueError, TypeError):
                    pass                      # a corrupted value falls back to the default

    @staticmethod
    def _check(key, value):
        default = DEFAULTS[key]
        if key in CHOICES:
            if value not in CHOICES[key]:
                raise ValueError(f"{key}: invalid value {value!r}")
        elif key in COLOR_KEYS:
            if not isinstance(value, str) or not _HEX.match(value):
                raise ValueError(f"{key}: expected #rrggbb")
            value = value.lower()
        elif key in VOLUME_KEYS:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{key}: expected a number 0-100")
            value = max(0, min(100, int(value)))
        elif isinstance(default, bool):
            if not isinstance(value, bool):
                raise ValueError(f"{key}: expected true/false")
        return value

    # ------------------------------------------------------------------ API
    def get(self, key):
        return self.values[key]

    __getitem__ = get

    def all(self):
        return dict(self.values)

    def set(self, key, value):
        if key not in DEFAULTS:
            raise KeyError(key)
        value = self._check(key, value)
        if self.values[key] == value:
            return
        self.values[key] = value
        self.db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", (key, json.dumps(value)))
        self.db.commit()
        self._notify()

    def reset(self):
        """Restore every option to its default."""
        self.values = dict(DEFAULTS)
        self.db.execute("DELETE FROM settings")
        self.db.commit()
        self._notify()

    def subscribe(self, fn):
        self._subs.append(fn)

    def _notify(self):
        for fn in list(self._subs):
            fn(self.all())
