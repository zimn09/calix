"""Avatar presets, palettes and cosmetic rewards (pure data, no Qt, no database).

The avatar is drawn from scratch with QPainter (see `avatars.py`), so nothing is
loaded from disk and the whole app stays offline.

* `AVATARS`  - the preset characters the player can choose from.
* `PALETTES` - accent colours that recolour the outfit.
* `COSMETICS`- cosmetic-only rewards (aura, frame, palette, title). They are
               unlocked by reaching a level or by unlocking an achievement and
               they never change any gameplay value.
"""

# --------------------------------------------------------------------- avatars
AVATARS = [
    {"id": "warrior", "name": "Warrior", "hint": "Classic calisthenics fighter",
     "skin": "#e2b48c", "hair": "#2b2f3a", "cloth": "#4dabf7", "shape": "band"},
    {"id": "monk", "name": "Monk", "hint": "Calm and steady",
     "skin": "#d9a173", "hair": "#3a2a22", "cloth": "#f59f00", "shape": "hood"},
    {"id": "nomad", "name": "Nomad", "hint": "Trains wherever there is a bar",
     "skin": "#c98b5e", "hair": "#1f2430", "cloth": "#38d9a9", "shape": "wrap"},
    {"id": "knight", "name": "Knight", "hint": "Planche armour",
     "skin": "#f0c9a4", "hair": "#6b7280", "cloth": "#9775fa", "shape": "helm"},
    {"id": "samurai", "name": "Samurai", "hint": "Discipline above all",
     "skin": "#e8b48c", "hair": "#15171c", "cloth": "#f06595", "shape": "topknot"},
    {"id": "shaman", "name": "Shaman", "hint": "Old school strongman",
     "skin": "#8d5a3b", "hair": "#12151c", "cloth": "#20c997", "shape": "horns"},
    {"id": "phantom", "name": "Phantom", "hint": "Quiet and precise",
     "skin": "#d6b49a", "hair": "#0d1016", "cloth": "#22b8cf", "shape": "mask"},
    {"id": "titan", "name": "Titan", "hint": "Heavy and immovable",
     "skin": "#b87a52", "hair": "#2f3542", "cloth": "#ff6b6b", "shape": "horns"},
    {"id": "sage", "name": "Sage", "hint": "Knows every progression",
     "skin": "#e7c3a1", "hair": "#9aa4b2", "cloth": "#ffd43b", "shape": "hood"},
    {"id": "wanderer", "name": "Wanderer", "hint": "Streets and rooftops",
     "skin": "#c99263", "hair": "#33302c", "cloth": "#748ffc", "shape": "wrap"},
]

AVATAR_BY_ID = {a["id"]: a for a in AVATARS}
DEFAULT_AVATAR = "warrior"

# -------------------------------------------------------------------- palettes
PALETTES = [
    {"id": "azure", "name": "Azure", "color": "#4dabf7"},
    {"id": "ember", "name": "Ember", "color": "#ff922b"},
    {"id": "jade", "name": "Jade", "color": "#38d9a9"},
    {"id": "violet", "name": "Violet", "color": "#b197fc"},
    {"id": "rose", "name": "Rose", "color": "#f06595"},
    {"id": "gold", "name": "Gold", "color": "#ffd43b"},
    {"id": "crimson", "name": "Crimson", "color": "#ff6b6b"},
    {"id": "ice", "name": "Ice", "color": "#22b8cf"},
]
PALETTE_BY_ID = {p["id"]: p for p in PALETTES}
DEFAULT_PALETTE = "azure"

# ------------------------------------------------------------------ cosmetics
# kind:  aura    - glowing ring behind the character
#        frame   - ornamental border around the badge
#        outfit  - recolours the clothing
#        title   - title suffix shown next to the player name
# unlock:
#        {"type": "level", "value": N}          reached level N
#        {"type": "achievement", "id": "..."}   unlocked that achievement
COSMETICS = [
    {"id": "aura_ember", "name": "Ember Aura", "kind": "aura", "color": "#ff922b",
     "desc": "A warm glow that follows you through the ranks.",
     "unlock": {"type": "level", "value": 3}},
    {"id": "aura_frost", "name": "Frost Aura", "kind": "aura", "color": "#22b8cf",
     "desc": "Cold steel light around the shoulders.",
     "unlock": {"type": "level", "value": 7}},
    {"id": "aura_void", "name": "Void Aura", "kind": "aura", "color": "#b197fc",
     "desc": "Only for those who trained through the pain.",
     "unlock": {"type": "achievement", "id": "mu_1"}},
    {"id": "frame_runes", "name": "Rune Frame", "kind": "frame", "color": "#4dabf7",
     "desc": "Engraved runes around the avatar frame.",
     "unlock": {"type": "level", "value": 5}},
    {"id": "frame_gold", "name": "Golden Frame", "kind": "frame", "color": "#ffd43b",
     "desc": "Pure gold. Very few athletes own it.",
     "unlock": {"type": "level", "value": 12}},
    {"id": "frame_bones", "name": "Bone Frame", "kind": "frame", "color": "#e6e9ef",
     "desc": "Carved bone. Awarded for consistency.",
     "unlock": {"type": "achievement", "id": "streak_14"}},
    {"id": "outfit_titan", "name": "Titan Outfit", "kind": "outfit", "color": "#ff6b6b",
     "desc": "Red plate of the strongman.",
     "unlock": {"type": "level", "value": 8}},
    {"id": "outfit_void", "name": "Void Outfit", "kind": "outfit", "color": "#9775fa",
     "desc": "Woven from the shadows of the front lever.",
     "unlock": {"type": "achievement", "id": "fl_full"}},
    {"id": "title_of_the_bar", "name": "Title: of the Bar", "kind": "title", "color": "#38d9a9",
     "desc": "Shown after your name once you master the pull-up.",
     "unlock": {"type": "achievement", "id": "pullup_20"}},
    {"id": "title_iron_will", "name": "Title: Iron Will", "kind": "title", "color": "#ff922b",
     "desc": "Forged by 14 days of unbroken training.",
     "unlock": {"type": "achievement", "id": "streak_14"}},
    {"id": "title_worlds", "name": "Title: of Ten Thousand", "kind": "title", "color": "#ffd43b",
     "desc": "Ten thousand repetitions. Not one of them counted twice.",
     "unlock": {"type": "achievement", "id": "reps_1000"}},
]

COSMETIC_BY_ID = {c["id"]: c for c in COSMETICS}


def unlock_text(cosmetic):
    """Human readable unlock condition."""
    u = cosmetic["unlock"]
    if u["type"] == "level":
        return f"Reach level {u['value']}"
    ach_id = u.get("id", "")
    try:                                   # local import: keeps this module dependency free
        from achievements import ACHIEVEMENTS
        name = next((a.name for a in ACHIEVEMENTS if a.id == ach_id), ach_id)
    except Exception:                      # pragma: no cover - defensive
        name = ach_id
    return f"Unlock the “{name}” achievement"


def cosmetics_of_kind(kind):
    return [c for c in COSMETICS if c["kind"] == kind]
