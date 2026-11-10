"""Offline 2D movement animations for the exercise library.

Every animation is drawn with QPainter from a small forward-kinematic skeleton,
so the whole system works offline and ships with the project - no images, no
network, no external assets.

A *pose* is a dictionary of joint positions in a 0..100 x 0..100 canvas:

    head, neck, sh_l, sh_r, el_l, el_r, wr_l, wr_r, hip, kn_l, kn_r, an_l, an_r

An *Anim* is a list of poses plus the phase label and the technique note of
every pose. Poses are interpolated with a smooth ease so the transitions look
fluid, and the player can be paused, restarted and slowed down.
"""
import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QPushButton, QSizePolicy, QVBoxLayout,
                               QWidget)

# ----------------------------------------------------------------- geometry
L_TORSO, L_NECK, R_HEAD = 16.0, 3.0, 4.0
L_UPPER, L_FORE = 10.0, 10.0
L_THIGH, L_SHIN = 12.5, 12.5
W_SHOULDER = 3.6
GROUND = 96.0
CANVAS = 100.0

ANIMATIONS_ON = True


def _d(a):
    """Unit vector for an angle in degrees (0 = down, 90 = right, 180 = up)."""
    r = math.radians(a)
    return (math.sin(r), math.cos(r))


def _pt(p, a, l):
    """Point at `l` units from `p` in the direction of angle `a`."""
    v = _d(a)
    return (p[0] + v[0] * l, p[1] + v[1] * l)


def _norm(v):
    m = math.hypot(v[0], v[1]) or 1.0
    return (v[0] / m, v[1] / m)


def _ik(root, target, l1, l2, side=1):
    """Two-bone inverse kinematics: place the middle joint between root and target."""
    dx, dy = target[0] - root[0], target[1] - root[1]
    d = math.hypot(dx, dy)
    if d < 1e-6:
        d = 1e-6
    if d > l1 + l2 - 0.01:                 # stretch rather than break the drawing
        f = (l1 + l2 - 0.01) / d
        target = (root[0] + dx * f, root[1] + dy * f)
        dx, dy = target[0] - root[0], target[1] - root[1]
        d = math.hypot(dx, dy)
    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, l1 * l1 - a * a))
    ux, uy = dx / d, dy / d
    mid = (root[0] + ux * a, root[1] + uy * a)
    return (mid[0] + side * uy * h, mid[1] - side * ux * h)


def _rot(p, c, ang):
    """Rotate a point around a centre (positive angle = clockwise on screen)."""
    if not ang:
        return p
    r = math.radians(ang)
    ca, sa = math.cos(r), math.sin(r)
    dx, dy = p[0] - c[0], p[1] - c[1]
    return (c[0] + dx * ca - dy * sa, c[1] + dx * sa + dy * ca)


def _rotv(v, ang):
    r = math.radians(ang)
    ca, sa = math.cos(r), math.sin(r)
    return (v[0] * ca - v[1] * sa, v[0] * sa + v[1] * ca)


def _pose(sc, body_a, wr=None, an=None, w=W_SHOULDER, elbow=(1, -1), knee=(1, 1), roll=0.0,
          elbow_pts=None, knee_pts=None):
    """Build a full pose from a shoulder centre and a body angle.

    sc      - (x, y) of the shoulder centre
    body_a  - direction of the spine, shoulder -> hip (0 = standing, 180 = inverted)
    wr      - (left, right) wrist targets in canvas coordinates
    an      - (left, right) ankle targets in canvas coordinates
    elbow   - side of the perpendicular the elbows bend to
    knee    - side of the perpendicular the knees bend to
    roll    - rotation of the whole skeleton around the shoulder centre (degrees)
    elbow_pts / knee_pts - explicit joint positions (override the IK)
    """
    db = _rotv(_d(body_a), roll)
    per = (db[1], -db[0])
    hip = (sc[0] + db[0] * L_TORSO, sc[1] + db[1] * L_TORSO)
    nck = (sc[0] - db[0] * L_NECK, sc[1] - db[1] * L_NECK)
    head = (nck[0] - db[0] * (R_HEAD - 1.2), nck[1] - db[1] * (R_HEAD - 1.2))
    sh_l = (sc[0] - per[0] * w, sc[1] - per[1] * w)
    sh_r = (sc[0] + per[0] * w, sc[1] + per[1] * w)
    if wr is None:
        arm = (sc[0] - db[0] * (L_UPPER + L_FORE - 1.0), sc[1] - db[1] * (L_UPPER + L_FORE - 1.0))
        wr = (arm, arm)
    if an is None:
        leg = (hip[0] + db[0] * (L_THIGH + L_SHIN), hip[1] + db[1] * (L_THIGH + L_SHIN))
        an = (leg, leg)
    el_l = _ik(sh_l, wr[0], L_UPPER, L_FORE, elbow[0])
    el_r = _ik(sh_r, wr[1], L_UPPER, L_FORE, elbow[1])
    kn_l = _ik(hip, an[0], L_THIGH, L_SHIN, knee[0])
    kn_r = _ik(hip, an[1], L_THIGH, L_SHIN, knee[1])
    if elbow_pts:
        el_l, el_r = elbow_pts
    if knee_pts:
        kn_l, kn_r = knee_pts
    return {"head": head, "neck": nck, "sh_l": sh_l, "sh_r": sh_r,
            "el_l": el_l, "el_r": el_r, "wr_l": wr[0], "wr_r": wr[1],
            "hip": hip, "kn_l": kn_l, "kn_r": kn_r, "an_l": an[0], "an_r": an[1]}


def _sh(sc, body_a, w=W_SHOULDER, roll=0.0):
    """The two shoulder points of a pose (used to aim straight arms)."""
    db = _rotv(_d(body_a), roll)
    per = (db[1], -db[0])
    return ((sc[0] - per[0] * w, sc[1] - per[1] * w), (sc[0] + per[0] * w, sc[1] + per[1] * w))


class Anim:
    """One looping movement animation."""

    def __init__(self, key, title, frames, labels, notes, duration=2.6, props=None, loop=True):
        self.key = key
        self.title = title
        self.frames = frames
        self.labels = list(labels)
        self.notes = list(notes)
        self.duration = duration
        self.props = props or {}
        self.loop = loop

    def __len__(self):
        return len(self.frames)

    def phase(self, index):
        i = max(0, min(index, len(self.labels) - 1))
        return self.labels[i], self.notes[i]


# ============================================================ animation data
ANIMS = {}


def _add(key, title, frames, labels, notes, duration=2.6, props=None, loop=True):
    ANIMS[key] = Anim(key, title, frames, labels, notes, duration, props, loop)


def _alias(key, src, title, labels=None, notes=None, duration=None):
    a = ANIMS[src]
    ANIMS[key] = Anim(key, title, a.frames, labels or a.labels, notes or a.notes,
                       duration or a.duration, dict(a.props), a.loop)


def _straight(sc, target, length=L_UPPER + L_FORE):
    """Point `length` away from `sc` towards `target` (a fully straight limb)."""
    v = (target[0] - sc[0], target[1] - sc[1])
    m = math.hypot(v[0], v[1]) or 1.0
    return (sc[0] + v[0] / m * length, sc[1] + v[1] / m * length)


PULLBAR = {"bar": (38, 62, 18)}


def _hang(sc_y, bar=(38, 62, 18), roll=0.0, w=W_SHOULDER):
    """Arms straight up to a bar: returns the pose."""
    cx = (bar[0] + bar[1]) / 2.0
    return _pose((cx, sc_y), 0, wr=((cx - w, bar[2]), (cx + w, bar[2])), roll=roll)


# ------------------------------------------------------------------- PULL
_pull = [
    _hang(38.0),
    _hang(29.0),
    _hang(20.0),
    _hang(29.0),
]
_add("pullup", "Pull-Up", _pull,
     ["Dead hang", "Pull", "Chin over bar", "Lower"],
     ["Full hang, arms completely straight, shoulders active.",
      "Elbows travel down and back, the chest moves towards the bar.",
      "The chin clearly rises above the bar, no kipping.",
      "Lower under control back to the full hang."],
     3.0, dict(PULLBAR))
_alias("chinup", "pullup", "Chin-Up",
       ["Dead hang", "Pull", "Chin over bar", "Lower"],
       ["Full hang, palms facing you, shoulders active.",
        "Elbows pull straight down to the ribs.",
        "The chin clearly rises above the bar.",
        "Lower under control back to the full hang."])

_c2b = [_hang(38.0), _hang(28.0), _hang(17.0), _hang(28.0)]
_add("c2b_pullup", "Chest-to-Bar Pull-Up", _c2b,
     ["Dead hang", "Explosive pull", "Chest to bar", "Lower"],
     ["Start from a still dead hang.",
      "Pull high and lean back slightly.",
      "The sternum touches the bar, legs quiet.",
      "Control the whole descent back to the hang."],
     3.0, dict(PULLBAR))

_scap = [_hang(38.0), _hang(34.5), _hang(38.0)]
_add("scap_pull", "Scapular Pull-Up", _scap,
     ["Hang", "Pull the blades down", "Hang"],
     ["Arms straight, body completely still.",
      "Only the shoulder blades move - the elbows stay locked.",
      "Lower the shoulders back to a relaxed hang."],
     2.6, dict(PULLBAR))

_neg = [_hang(20.0), _hang(29.0), _hang(38.0), _hang(29.0)]
_add("negative_pullup", "Negative Pull-Up", _neg,
     ["Top position", "Lowering", "Full hang", "Lowering"],
     ["Start at the top with the chin over the bar.",
      "Lower for four to five seconds under full control.",
      "Reach a complete dead hang - this is the end of the rep.",
      "Reset to the top and lower again."],
     3.0, dict(PULLBAR), loop=False)

_asy = [_hang(38.0), _hang(26.0), _hang(38.0)]
_add("assisted_pullup", "Assisted Pull-Up", _asy,
     ["Assisted hang", "Pull with the band", "Assisted hang"],
     ["The band or foot support takes part of the load.",
      "Pull the chin over the bar, the band still assisting.",
      "Lower back to the assisted hang."],
     2.8, {"bar": (38, 62, 18), "band": (50.0, 96.0)})

_arch = [
    _hang(38.0),
    _pose((49.0, 30.0), 0, wr=((46.4, 18), (53.6, 18)), roll=22.0),
    _pose((47.5, 24.0), 0, wr=((46.4, 18), (53.6, 18)), roll=26.0),
    _pose((49.0, 30.0), 0, wr=((46.4, 18), (53.6, 18)), roll=22.0),
]
_add("archer_pullup", "Archer Pull-Up", _arch,
     ["Dead hang", "Pull to one side", "Chin to the hand", "Lower"],
     ["Wide grip, both arms straight.",
      "Pull towards one hand, the other arm stays long.",
      "The chin reaches the pulling hand, hips stay square.",
      "Lower slowly and switch sides."],
     3.0, dict(PULLBAR))

_lsit_pull = [
    _pose((50, 38), 0, wr=((46.4, 18), (53.6, 18)), an=((72, 51), (72, 51))),
    _pose((50, 29), 0, wr=((46.4, 18), (53.6, 18)), an=((72, 42), (72, 42))),
    _pose((50, 20), 0, wr=((46.4, 18), (53.6, 18)), an=((72, 33), (72, 33))),
    _pose((50, 29), 0, wr=((46.4, 18), (53.6, 18)), an=((72, 42), (72, 42))),
]
_add("lsit_pullup", "L-Sit Pull-Up", _lsit_pull,
     ["L-Sit hang", "Pull with the legs up", "Top of the pull-up", "Lower"],
     ["Legs straight and parallel to the floor the whole time.",
      "Keep the legs locked out, pull the elbows down.",
      "Chin over the bar while the legs stay horizontal.",
      "Lower under control, legs never drop."],
     3.2, dict(PULLBAR))

_one_arm = [
    _pose((50, 38), 0, wr=((46.4, 18), (56.0, 55.0))),
    _pose((48, 26), 0, wr=((46.4, 18), (54.0, 44.0))),
    _pose((50, 38), 0, wr=((46.4, 18), (56.0, 55.0))),
]
_add("one_arm_pullup", "One-Arm Pull-Up", _one_arm,
     ["One arm hanging", "Pull with one arm", "One arm hanging"],
     ["Only one arm grips the bar, the other hangs relaxed.",
      "Rotate the pulling shoulder over the bar.",
      "Lower under control to the one-arm hang."],
     3.0, dict(PULLBAR))

_dead = [_hang(38.5), _hang(37.5), _hang(38.5)]
_add("dead_hang", "Dead Hang", _dead,
     ["Relaxed hang", "Shoulders settle", "Relaxed hang"],
     ["Hang passively from the bar, body still.",
      "Let the shoulder blades move away from the ears.",
      "Breathe calmly, switch the grip if the hands burn."],
     3.4, dict(PULLBAR))

_active = [_hang(38.5), _hang(36.5), _hang(38.5)]
_add("active_hang", "Active Hang", _active,
     ["Relaxed", "Pull the shoulders down", "Relaxed"],
     ["Start from a relaxed hang.",
      "Depress the shoulder blades, arms stay straight.",
      "Return to the relaxed position between holds."],
     3.0, dict(PULLBAR))

_add("false_grip_hang", "False Grip Hang", _dead,
     ["False grip", "Hold", "False grip"],
     ["The wrist wraps over the top of the bar.",
      "Press down with the heel of the hand, body in one line.",
      "Build up slowly, the wrist tendon adapts slowly."],
     3.4, dict(PULLBAR))


# ------------------------------------------------------------------- PUSH
def _push(sc, body_a, wr=(74.0, 94.0), **kw):
    kw.setdefault("w", 2.4)
    kw.setdefault("elbow", (-1, -1))
    return _pose(sc, body_a, wr=(wr, wr), **kw)


_pu_top = _push((68, 75), -62.7)
_pu_bot = _push((68, 84), -76.1)
_add("pushup", "Push-Up", [_pu_top, _pu_bot, _pu_top],
     ["Top position", "Bottom position", "Press up"],
     ["One straight line from head to heels, glutes squeezed.",
      "The chest reaches the floor, elbows about 45 degrees from the body.",
      "Push the floor away, the body stays rigid."],
     2.6, {"floor": GROUND})
_alias("diamond_pushup", "pushup", "Diamond Push-Up",
       ["Top position", "Bottom position", "Press up"],
       ["Hands together under the chest, elbows hugging the ribs.",
        "The chest reaches the floor close to the hands.",
        "Push up while keeping the elbows close to the body."])
_alias("wide_pushup", "pushup", "Wide Push-Up",
       ["Top position", "Bottom position", "Press up"],
       ["Hands wider than the shoulders, body in one line.",
        "Lower until the chest is just off the floor.",
        "Press the floor away with control."])

_inc = [_push((64, 67), -49.4, wr=(70, 85)),
        _push((64, 76), -64.2, wr=(70, 85)),
        _push((64, 67), -49.4, wr=(70, 85))]
_add("incline_pushup", "Incline Push-Up", _inc,
     ["Top position", "Bottom position", "Press up"],
     ["Hands on a bench, body in one straight line.",
      "Lower the chest to the edge of the bench.",
      "Press the bench away, shoulders away from the ears."],
     2.6, {"floor": GROUND, "box": (62, 85, 20, 11)})

_wall = [_pose((68, 58), -28.6, wr=((78, 72), (78, 72)), w=2.6, elbow=(-1, 1)),
         _pose((72, 68), -50.6, wr=((78, 72), (78, 72)), w=2.6, elbow=(-1, 1)),
         _pose((68, 58), -28.6, wr=((78, 72), (78, 72)), w=2.6, elbow=(-1, 1))]
_add("wall_pushup", "Wall Push-Up", _wall,
     ["Start", "Lower to the wall", "Press away"],
     ["Hands on the wall at chest height, body in one line.",
      "The chest moves towards the wall, elbows at 45 degrees.",
      "Push the wall away and finish with straight arms."],
     2.6, {"floor": GROUND, "wall": (79.0, 18.0, 96.0)})

_knee = [_pose((64, 80), -53.1, wr=((68, 94), (68, 94)), w=2.4, elbow=(-1, -1),
               knee_pts=((38, 93), (38, 93)), an=((30, 83), (30, 83))),
         _pose((64, 84), -73.3, wr=((68, 94), (68, 94)), w=2.4, elbow=(-1, -1),
               knee_pts=((38, 93), (38, 93)), an=((30, 83), (30, 83))),
         _pose((64, 80), -53.1, wr=((68, 94), (68, 94)), w=2.4, elbow=(-1, -1),
               knee_pts=((38, 93), (38, 93)), an=((30, 83), (30, 83)))]
_add("knee_pushup", "Knee Push-Up", _knee,
     ["Start", "Lower the chest", "Press up"],
     ["Knees and hands on the floor, shoulders over the hands.",
      "Lower the chest between the hands, hips stay level.",
      "Press up, the hips never sag."],
     2.6, {"floor": GROUND})

_dec = [_push((68, 75), -83.0, wr=(74, 94)),
        _push((68, 84), -95.6, wr=(74, 94)),
        _push((68, 75), -83.0, wr=(74, 94))]
_add("decline_pushup", "Decline Push-Up", _dec,
     ["Top position", "Bottom position", "Press up"],
     ["Feet elevated on a bench, body in one straight line.",
      "Lower the chest between the hands, hips stay level.",
      "Press the floor away, shoulders away from the ears."],
     2.6, {"floor": GROUND, "box": (26, 80, 18, 16)})

_pike = [_pose((60, 80), -150.0, wr=((66, 94), (66, 94)), w=2.4, elbow=(-1, -1),
                knee_pts=((45, 79), (45, 79)), an=((39, 91), (39, 91))),
         _pose((60, 89), -160.0, wr=((66, 94), (66, 94)), w=2.4, elbow=(-1, -1),
                knee_pts=((46, 82), (46, 82)), an=((39, 91), (39, 91))),
         _pose((60, 80), -150.0, wr=((66, 94), (66, 94)), w=2.4, elbow=(-1, -1),
                knee_pts=((45, 79), (45, 79)), an=((39, 91), (39, 91)))]
_add("pike_pushup", "Pike Push-Up", _pike,
     ["Start", "Lower the head", "Press up"],
     ["Hips high, legs almost straight, head between the hands.",
      "Lower the crown of the head towards the floor.",
      "Press up, the hips stay high."],
     2.6, {"floor": GROUND})

# ------------------------------------------------------------------- DIPS
_dip_top = _pose((50, 52), 0, wr=((36, 60), (64, 60)), w=3.2, elbow=(1, -1))
_dip_bot = _pose((50, 61), -8.0, wr=((36, 60), (64, 60)), w=3.2, elbow=(1, -1),
                an=((58, 88), (58, 88)))
_add("dip", "Parallel Bar Dip", [_dip_top, _dip_bot, _dip_top],
     ["Top support", "Lower", "Press up"],
     ["Straight arms on the bars, shoulders pushed down.",
      "Lower until the upper arms are about parallel to the floor.",
      "Press down and lock out, shoulders active."],
     2.8, {"floor": GROUND, "bars": [(26, 46, 60), (54, 74, 60)]})
_alias("ring_dip", "dip", "Ring Dip",
       ["Top support", "Lower", "Press up"],
       ["Support on rings, elbows turned out.",
        "Lower between the hands, not behind them.",
        "Press down so the rings stay under the shoulders."])

_scapdip = [_pose((50, 52), 0, wr=((36, 60), (64, 60)), w=3.2, elbow=(1, -1)),
             _pose((50, 49), 0, wr=((36, 60), (64, 60)), w=3.2, elbow=(1, -1)),
             _pose((50, 52), 0, wr=((36, 60), (64, 60)), w=3.2, elbow=(1, -1))]
_add("scapular_dip", "Scapular Dip", _scapdip,
     ["Support", "Lower the blades", "Support"],
     ["Straight arms, shoulders down and back.",
      "Only the shoulder blades move, the elbows stay locked.",
      "Press back to a stable support."],
     2.6, {"floor": GROUND, "bars": [(26, 46, 60), (54, 74, 60)]})

_kdip = [_pose((78, 68), -53.0, wr=((64, 78), (64, 78)), w=2.6, elbow=(-1, 1)),
         _pose((74, 78), -68.8, wr=((64, 78), (64, 78)), w=2.6, elbow=(-1, 1)),
         _pose((78, 68), -53.0, wr=((64, 78), (64, 78)), w=2.6, elbow=(-1, 1))]
_add("korean_dip", "Korean Dip", _kdip,
     ["Top", "Lower", "Press up"],
     ["Body in front of the hands, chest tall and open.",
      "Lower only as far as the shoulders stay comfortable.",
      "Press up with straight arms, shoulders active."],
     2.8, {"floor": GROUND, "bars": [(58, 76, 78)]})

_bdip = [_pose((81, 69), -54.7, wr=((64, 78), (64, 78)), w=2.6, elbow=(-1, 1)),
         _pose((76, 78), -68.8, wr=((64, 78), (64, 78)), w=2.6, elbow=(-1, 1)),
         _pose((81, 69), -54.7, wr=((64, 78), (64, 78)), w=2.6, elbow=(-1, 1))]
_add("bench_dip", "Bench Dip", _bdip,
     ["Top", "Lower", "Press up"],
     ["Hands on a bench behind the hips, shoulders down and back.",
      "Lower only until the elbows reach about 90 degrees.",
      "Press the bench away, feet light on the floor."],
     2.6, {"floor": GROUND, "box": (62, 78, 16, 18)})

_arch_pu = [_push((68, 75), -62.7, wr=(74, 94)),
            _push((66, 81), -69, wr=(74, 94)),
            _push((68, 75), -62.7, wr=(74, 94))]
_add("archer_pushup", "Archer Push-Up", _arch_pu,
     ["Top position", "Lower to one side", "Press up"],
     ["Wide hands, one arm straight, one arm working.",
      "Lower the chest towards one hand, the other arm stays long.",
      "Press up and switch sides."],
     2.6, {"floor": GROUND})

_one_pu = [_push((68, 75), -62.7, wr=(74, 94)),
           _push((66, 83), -72, wr=(74, 94)),
           _push((68, 75), -62.7, wr=(74, 94))]
_add("one_arm_pushup", "One-Arm Push-Up", _one_pu,
     ["Top position", "Lower", "Press up"],
     ["Feet wide, one hand behind the back, hips square.",
      "Lower with one arm, the body does not twist.",
      "Press back up without rotating."],
     2.8, {"floor": GROUND})

_pp = [_push((66, 76), -64.2, wr=(70, 94)),
       _push((66, 85), -72, wr=(70, 94)),
       _push((66, 76), -64.2, wr=(70, 94))]
_add("pseudo_planche_pushup", "Pseudo Planche Push-Up", _pp,
     ["Lean forward", "Lower", "Press up"],
     ["Hands by the hips with the fingers turned out.",
      "Shift the shoulders forward past the hands.",
      "Press back up keeping the lean."],
     2.6, {"floor": GROUND})

_hspu = [_pose((50, 74), 180, wr=((46, 94), (54, 94)), w=3.6, elbow=(1, -1)),
         _pose((50, 84), 180, wr=((46, 94), (54, 94)), w=3.6, elbow=(1, -1)),
         _pose((50, 74), 180, wr=((46, 94), (54, 94)), w=3.6, elbow=(1, -1))]
_add("hspu", "Handstand Push-Up", _hspu,
     ["Handstand", "Lower the head", "Press up"],
     ["Inverted handstand, arms locked, body vertical.",
      "Lower the head towards the floor under control.",
      "Press back to a straight-arm handstand."],
     2.8, {"floor": GROUND})


# ------------------------------------------------------------------- CORE
_plank = _pose((64, 74), -58.0, wr=((64, 94), (64, 94)), w=1.2, elbow=(-1, -1))
_plank2 = _pose((64, 76), -60.0, wr=((64, 94), (64, 94)), w=1.2, elbow=(-1, -1))
_add("plank", "Plank", [_plank, _plank2, _plank],
     ["Hold", "Breathe", "Hold"],
     ["Forearms under the shoulders, one straight line from head to heels.",
      "Keep breathing, squeeze the glutes, ribs down.",
      "Hold the position without letting the hips sag."],
     3.4, {"floor": GROUND})

_sp = _pose((70, 76), -90.0, wr=((70, 93.6), (85, 82)), w=2.4, elbow=(1, -1),
            elbow_pts=((70, 83.6), (78, 78)), an=((29, 76), (31, 80)))
_sp2 = _pose((70, 77), -90.0, wr=((70, 93.6), (85, 82)), w=2.4, elbow=(1, -1),
             elbow_pts=((70, 84.6), (78, 79)), an=((29, 77), (31, 81)))
_add("side_plank", "Side Plank", [_sp, _sp2, _sp],
     ["Hold", "Breathe", "Hold"],
     ["Feet stacked, hips lifted so the body is one straight line.",
      "Push the shoulder away from the ear, breathe.",
      "Hold without dropping the hips."],
     3.4, {"floor": GROUND})

_db = _pose((26, 88), 80.0, wr=((36, 72), (12, 93)), w=2.4, elbow=(-1, 1),
            elbow_pts=((28, 80), (20, 92)), an=((66, 93), (58, 68)),
            knee_pts=((56, 92), (52, 80)))
_db2 = _pose((26, 88), 80.0, wr=((34, 76), (12, 93)), w=2.4, elbow=(-1, 1),
             elbow_pts=((28, 82), (20, 92)), an=((66, 93), (64, 72)),
             knee_pts=((56, 92), (54, 80)))
_add("dead_bug", "Dead Bug", [_db, _db2, _db],
     ["Start", "Extend opposite limbs", "Start"],
     ["Lower back pressed into the floor, arms straight up.",
      "Extend the opposite arm and leg slowly, keep the back flat.",
      "Return to the start and switch sides."],
     3.0, {"floor": GROUND})

_hh = _pose((28, 88), 80.0, wr=((14, 72), (12, 93)), w=2.4, elbow=(-1, 1),
            elbow_pts=((22, 80), (20, 92)), an=((60, 72), (62, 72)),
            knee_pts=((52, 81), (53, 81)))
_hh2 = _pose((28, 88), 80.0, wr=((14, 72), (12, 93)), w=2.4, elbow=(-1, 1),
             elbow_pts=((22, 80), (20, 92)), an=((60, 70), (62, 70)),
             knee_pts=((52, 80), (53, 80)))
_add("hollow_hold", "Hollow Body Hold", [_hh, _hh2, _hh],
     ["Hold", "Breathe", "Hold"],
     ["Lower back flat, shoulders and legs lifted off the floor.",
      "Reach long with the arms and legs, breathe into the belly.",
      "Keep the shape, never let the back arch up."],
     3.2, {"floor": GROUND})

_llr = _pose((26, 90), 80.0, wr=((6, 93), (6, 93)), w=2.4, elbow=(1, 1),
             elbow_pts=((16, 93), (16, 93)), an=((70, 95), (70, 95)),
             knee_pts=((56, 94), (56, 94)))
_llr2 = _pose((26, 90), 80.0, wr=((6, 93), (6, 93)), w=2.4, elbow=(1, 1),
              elbow_pts=((16, 93), (16, 93)), an=((54, 66), (54, 66)),
              knee_pts=((52, 80), (52, 80)))
_add("lying_leg_raise", "Lying Leg Raise", [_llr, _llr2, _llr],
     ["Legs down", "Raise the legs", "Legs down"],
     ["Lower back pressed into the floor, legs straight.",
      "Lift the legs to vertical without arching the back.",
      "Lower the legs slowly, keeping the back flat."],
     2.8, {"floor": GROUND})

_hlr = _pose((48, 38), 0, wr=((46, 18), (50, 18)), w=3.0)
_hlr2 = _pose((48, 38), 0, wr=((46, 18), (50, 18)), w=3.0, an=((73, 54), (73, 54)))
_add("hanging_leg_raise", "Hanging Leg Raise", [_hlr, _hlr2, _hlr],
     ["Dead hang", "Raise the legs", "Dead hang"],
     ["Hang still with straight arms, no swinging.",
      "Raise the straight legs to horizontal, tilt the pelvis up.",
      "Lower the legs slowly back to the hang."],
     3.0, {"bar": (40, 54, 18)})

_abw = _pose((60, 78), -80.0, wr=((60, 94), (60, 94)), w=2.4, elbow=(-1, -1),
             elbow_pts=((55, 86), (55, 86)), an=((26, 88), (26, 88)),
             knee_pts=((36, 93), (36, 93)))
_abw2 = _pose((76, 82), -80.0, wr=((60, 94), (60, 94)), w=2.4, elbow=(-1, -1),
              elbow_pts=((68, 86), (68, 86)), an=((34, 90), (34, 90)),
              knee_pts=((48, 92), (48, 92)))
_add("ab_wheel", "Ab Wheel Rollout", [_abw, _abw2, _abw],
     ["Start", "Roll out", "Pull back"],
     ["Knees down, arms straight, back rounded.",
      "Roll the wheel out while keeping the core tight.",
      "Pull back with the abs, never let the lower back sag."],
     3.0, {"floor": GROUND, "wheel": (60.0, 94.0)})

_lsit = _pose((50, 74), 0, wr=((50, 92), (50, 92)), w=3.0, an=((75, 90), (75, 90)))
_tuck = _pose((50, 74), 0, wr=((50, 92), (50, 92)), w=3.0, an=((56, 72), (56, 72)),
              knee_pts=((58, 84), (58, 84)))
_add("l_sit", "L-Sit", [_lsit, _lsit],
     ["L-Sit", "L-Sit"],
     ["Straight arms locked, legs held parallel to the floor.",
      "Push down hard through the hands, chest open."],
     3.0, {"floor": GROUND, "bars": [(44, 56, 92)]})
_add("tuck_l_sit", "Tuck L-Sit", [_tuck, _lsit],
     ["Tuck position", "Extend the legs"],
     ["Knees tucked, hips pushed forward, arms straight.",
      "Extend the legs towards the full L-Sit."],
     2.8, {"floor": GROUND, "bars": [(44, 56, 92)]})

_ttb = _pose((48, 38), 0, wr=((46, 18), (50, 18)), w=3.0)
_ttb2 = _pose((48, 38), 0, wr=((46, 18), (50, 18)), w=3.0, an=((50, 24), (50, 24)),
              knee_pts=((54, 40), (54, 40)))
_add("toes_to_bar", "Toes to Bar", [_ttb, _ttb2, _ttb],
     ["Dead hang", "Legs to the bar", "Dead hang"],
     ["Hang still, shoulders active, no swinging.",
      "Curl the pelvis up and reach the toes to the bar.",
      "Lower the legs under control back to the hang."],
     3.0, {"bar": (40, 54, 18)})

_df = _pose((41, 79), 90.0, wr=((31, 64), (31, 64)), w=1.6, elbow=(1, 1))
_df2 = _pose((41, 79), 70.0, wr=((31, 64), (31, 64)), w=1.6, elbow=(1, 1))
_add("dragon_flag", "Dragon Flag", [_df, _df2, _df],
     ["Body horizontal", "Lower under control", "Body horizontal"],
     ["Grip the bench behind the head, body in one rigid line.",
      "Lower the body as a straight line, heels towards the floor.",
      "Roll back up to the horizontal position."],
     3.4, {"floor": GROUND, "box": (12, 62, 18, 34)})

# ------------------------------------------------------------------- LEGS
_sq_stand = _pose((50, 52), 0, wr=((50, 71), (50, 71)), w=3.0)
_sq_bot = _pose((52, 58), -23.2, wr=((64, 60), (64, 60)), w=3.0, elbow=(1, -1))
_add("squat", "Bodyweight Squat", [_sq_stand, _sq_bot, _sq_stand],
     ["Standing", "Bottom of the squat", "Standing"],
     ["Feet shoulder-width, chest tall, heels down.",
      "Sit the hips back and down, knees tracking over the toes.",
      "Drive through the whole foot and stand up."],
     2.8, {"floor": GROUND})

_lu_stand = _pose((50, 52), 0, wr=((50, 71), (50, 71)), w=3.0)
_lu_bot = _pose((52, 60), 0, wr=((56, 78), (56, 78)), w=3.0, an=((68, 93), (34, 93)),
                knee_pts=((61, 80), (44, 86)))
_add("lunge", "Lunge", [_lu_stand, _lu_bot, _lu_stand],
     ["Standing", "Bottom of the lunge", "Standing"],
     ["Take a long stride, front foot fully planted.",
      "Lower the back knee straight down, front knee behind the toes.",
      "Push through the front heel and stand up."],
     3.0, {"floor": GROUND})
_alias("split_squat", "lunge", "Split Squat",
       ["Standing", "Bottom of the squat", "Standing"],
       ["Staggered stance, front heel under the back knee.",
        "Lower straight down, no forward lunge.",
        "Push through the front heel to stand up."])

_bu = _pose((52, 58), 0, wr=((50, 77), (50, 77)), w=3.0, an=((64, 93), (42, 80)),
            knee_pts=((60, 82), (50, 88)))
_bd = _pose((52, 64), -6.0, wr=((50, 84), (50, 84)), w=3.0, an=((64, 93), (42, 80)),
            knee_pts=((60, 82), (46, 92)))
_add("bulgarian", "Bulgarian Split Squat", [_bu, _bd, _bu],
     ["Start", "Bottom", "Start"],
     ["Rear foot on a bench, front foot far enough forward.",
      "Lower until the front thigh is parallel to the floor.",
      "Push through the front heel to stand up."],
     3.0, {"floor": GROUND, "box": (34, 80, 16, 16)})

_su = _pose((50, 58), 0, wr=((44, 76), (44, 76)), w=3.0, an=((64, 94), (38, 93)))
_su2 = _pose((52, 60), 0, wr=((46, 78), (46, 78)), w=3.0, an=((64, 88), (38, 93)))
_add("step_up", "Step-Up", [_su, _su2, _su],
     ["Both feet on the floor", "Standing on the box", "Both feet on the floor"],
     ["Place the whole foot on the box before you stand up.",
      "Stand tall on the box, knee tracking over the toes.",
      "Step down slowly, control the landing."],
     3.0, {"floor": GROUND, "box": (56, 88, 20, 8)})

_gb = _pose((18, 90), 90.0, wr=((2, 92), (2, 92)), w=1.6, elbow=(-1, -1),
            an=((56, 92), (56, 92)), knee_pts=((46, 86), (46, 86)))
_gb2 = _pose((18, 90), 138.7, wr=((2, 92), (2, 92)), w=1.6, elbow=(-1, -1),
             an=((56, 92), (56, 92)), knee_pts=((43, 85), (43, 85)))
_add("glute_bridge", "Glute Bridge", [_gb, _gb2, _gb],
     ["Hips down", "Hips lifted", "Hips down"],
     ["Feet flat, knees over the ankles.",
      "Drive the hips up and squeeze the glutes at the top.",
      "Lower slowly, ribs stay down."],
     3.0, {"floor": GROUND})

_ws = _pose((26, 60), 0, wr=((34, 72), (34, 72)), w=2.6, an=((38, 90), (38, 90)),
            knee_pts=((38, 76), (38, 76)))
_add("wall_sit", "Wall Sit", [_ws, _ws],
     ["Hold the position", "Hold the position"],
     ["Back flat against the wall, knees at 90 degrees.",
      "Weight in the heels, chest lifted, breathe steadily."],
     3.4, {"floor": GROUND, "wall": (18.0, 16.0, 96.0)})

_cr = _pose((50, 52), 0, wr=((50, 71), (50, 71)), w=3.0)
_cr2 = _pose((50, 49), 0, wr=((50, 68), (50, 68)), w=3.0)
_add("calf_raise", "Calf Raise", [_cr, _cr2, _cr],
     ["Heels down", "Up on the toes", "Heels down"],
     ["Stand tall, weight over the big toe.",
      "Rise as high as the toes allow and pause.",
      "Lower the heels all the way down, slowly."],
     2.4, {"floor": GROUND})
_alias("single_calf_raise", "calf_raise", "Single-Leg Calf Raise",
       ["Heels down", "Up on the toes", "Heels down"],
       ["Stand on one leg, the other foot off the floor.",
        "Rise and pause at the top of the range.",
        "Lower the heel slowly to the floor."])

_sh = _pose((50, 54), -7.1, wr=((46, 70), (46, 70)), w=2.6, an=((60, 94), (46, 72)),
            knee_pts=((56, 80), (40, 80)))
_sh2 = _pose((50, 64), 7.1, wr=((46, 72), (46, 72)), w=2.6, an=((60, 94), (46, 74)),
             knee_pts=((63, 84), (40, 86)))
_add("shrimp_squat", "Shrimp Squat", [_sh, _sh2, _sh],
     ["Start", "Lower", "Start"],
     ["Hold the rear foot, front foot flat on the floor.",
      "Touch the back knee down in front of the front foot.",
      "Stand up through the front heel."],
     3.0, {"floor": GROUND})

_ps = _pose((54, 56), -7.1, wr=((46, 74), (46, 74)), w=2.6, an=((50, 93), (76, 68)),
            knee_pts=((56, 82), (66, 74)))
_ps2 = _pose((52, 60), -7.1, wr=((44, 80), (44, 80)), w=2.6, an=((50, 93), (76, 72)),
             knee_pts=((59, 84), (64, 80)))
_add("pistol_squat", "Pistol Squat", [_ps, _ps2, _ps],
     ["Start", "Bottom", "Start"],
     ["Free leg extended in front, heel down, balance tall.",
      "Sit straight down over the standing leg.",
      "Stand back up without losing balance."],
     3.2, {"floor": GROUND})

_nc = _pose((42, 63.5), 0, wr=((60, 66), (60, 66)), w=2.6, an=((29.5, 92), (29.5, 92)),
            knee_pts=((42, 92), (42, 92)))
_nc2 = _pose((58.5, 79.5), -90.0, wr=((74, 80), (74, 80)), w=2.6,
             an=((29.5, 92), (29.5, 92)), knee_pts=((42, 92), (42, 92)))
_add("nordic_curl", "Nordic Hamstring Curl", [_nc, _nc2, _nc],
     ["Tall position", "Lower forward", "Tall position"],
     ["Kneel with the feet anchored, body tall.",
      "Lower forward as slowly as you can, catch with the hands.",
      "Push back up to the tall position."],
     3.2, {"floor": GROUND})


# ------------------------------------------------------- ROW / LEVERS
_row_down = _pose((49.9, 82.6), 75.5, wr=((46, 63), (46, 63)), w=1.8)
_row_up = _pose((65.7, 59.4), 35.9, wr=((46, 63), (46, 63)), w=1.8)
_add("row", "Australian Row", [_row_down, _row_up, _row_down],
     ["Lowered position", "Row up", "Lowered position"],
     ["Body in one straight line under the bar, feet on the floor.",
      "Pull the chest towards the bar, elbows stay close to the body.",
      "Lower under control back to the start."],
     2.8, {"floor": GROUND, "bar": (36, 86, 63)})

# front lever: hang -> tuck -> extend -> full hold
_fl_hang = _pose((44, 38), 0, wr=((42, 18), (46, 18)), w=3.0)
_fl_tuck = _pose((44, 38), 0, wr=((42, 18), (46, 18)), w=3.0,
                 an=((50, 34), (50, 34)), knee_pts=((54, 46), (54, 46)))
_fl_open = _pose((44, 38), 90.0, wr=((42, 18), (46, 18)), w=1.2)
_add("front_lever", "Front Lever", [_fl_hang, _fl_tuck, _fl_open, _fl_open],
     ["Dead hang", "Tuck the knees", "Open the body", "Full lever"],
     ["Hang with straight arms and a strong grip on the bar.",
      "Tuck the knees towards the chest, pull the shoulders down.",
      "Open the hips and extend the body to horizontal.",
      "Hold the body perfectly horizontal, shoulders away from the ears."],
     4.2, {"bar": (36, 54, 18)})

_bl_hang = _pose((60, 38), 0, wr=((58, 18), (62, 18)), w=3.0)
_bl_tuck = _pose((60, 38), 0, wr=((58, 18), (62, 18)), w=3.0,
                 an=((66, 34), (66, 34)), knee_pts=((70, 46), (70, 46)))
_bl_open = _pose((60, 38), -90.0, wr=((58, 18), (62, 18)), w=1.2)
_add("back_lever", "Back Lever", [_bl_hang, _bl_tuck, _bl_open, _bl_open],
     ["Dead hang", "Tuck the knees", "Open the body", "Full lever"],
     ["Hang with straight arms, shoulders pulled down and back.",
      "Tuck the knees towards the chest, lean the shoulders back.",
      "Open the hips slowly, the head stays in line with the spine.",
      "Hold the body horizontal, the chest faces the sky."],
     4.2, {"bar": (54, 68, 18)})

_dfly = _pose((40, 38), 90.0, wr=((38, 18), (42, 18)), w=1.2,
              an=((74, 14), (74, 14)), knee_pts=((64, 27), (64, 27)))
_add("dragonfly", "Dragonfly", [_fl_hang, _fl_tuck, _dfly, _dfly],
     ["Dead hang", "Tuck the knees", "Open into the V", "Dragonfly hold"],
     ["Start from a dead hang with straight arms.",
      "Tuck the knees and pull the shoulders down hard.",
      "Open the hips and lift the legs high behind you.",
      "Hold the open V shape, body straight, no arch in the back."],
     4.2, {"bar": (32, 50, 18)})

_pl_lean = _pose((44, 74), 59.5, wr=((40, 94), (40, 94)), w=2.4, elbow=(-1, -1))
_pl_tuck = _pose((50, 84), 156.5, wr=((42, 94), (42, 94)), w=2.4, elbow=(-1, -1),
                 an=((58, 48), (58, 48)), knee_pts=((52, 58), (52, 58)))
_pl_full = _pose((36, 90), 90.0, wr=((55, 94), (55, 94)), w=2.4, elbow=(-1, -1))
_add("planche", "Planche", [_pl_lean, _pl_tuck, _pl_full, _pl_full],
     ["Planche lean", "Tuck planche", "Full planche", "Full planche"],
     ["Hands on the floor, lean the shoulders forward of the hands.",
      "Lift the feet and tuck the knees onto the elbows.",
      "Open the hips and extend the body parallel to the floor.",
      "Hold the horizontal line, protract the shoulder blades hard."],
     4.4, {"floor": GROUND})

_flag = _pose((48, 30), 90.0, wr=((48, 50), (48, 10)), w=1.2, elbow=(1, 1))
_add("flag", "Human Flag", [_flag, _flag],
     ["Hold the flag", "Hold the flag"],
     ["Body sideways against the pole, arms locked and stacked.",
      "Squeeze the glutes and push the hips away from the pole."],
     3.2, {"floor": GROUND, "pole": (44.0, 6.0, 96.0)})

# ------------------------------------------------------- HANDSTAND FAMILY
_wall_hs = _pose((40, 74), 136.3, wr=((40, 94), (40, 94)), w=2.6, elbow=(1, 1))
_add("wall_handstand", "Wall Handstand", [_wall_hs, _wall_hs],
     ["Hold the handstand", "Hold the handstand"],
     ["Feet on the wall, body in one straight line, shoulders pushed up.",
      "Push the floor away and keep the hips over the shoulders."],
     3.0, {"floor": GROUND, "wall": (84.0, 10.0, 96.0)})

_hs = _pose((50, 74), 180.0, wr=((50, 94), (50, 94)), w=2.6, elbow=(1, -1))
_add("free_handstand", "Free Handstand", [_hs, _hs],
     ["Handstand", "Handstand"],
     ["Balance in a straight line, weight on the hands, fingers spread.",
      "Squeeze the glutes and push the shoulders up."],
     3.0, {"floor": GROUND})

_kick1 = _pose((56, 74), 233.1, wr=((56, 94), (56, 94)), w=2.6, elbow=(1, -1),
               an=((30, 40), (30, 40)), knee_pts=((36, 52), (36, 52)))
_kick2 = _pose((50, 74), 173.4, wr=((50, 94), (50, 94)), w=2.6, elbow=(1, -1),
               an=((48, 32), (48, 32)), knee_pts=((50, 44), (50, 44)))
_kick3 = _pose((50, 74), 180.0, wr=((50, 94), (50, 94)), w=2.6, elbow=(1, -1))
_add("handstand_kickup", "Handstand Kick-Up", [_kick1, _kick2, _kick3, _kick3],
     ["Set the hands", "Kick the legs up", "Catch the handstand", "Hold"],
     ["Place the hands shoulder-width, fingers spread.",
      "Push the hips up and kick the legs towards the ceiling.",
      "Catch the balance with the body stacked over the hands.",
      "Hold the straight line, do not let the hips sag."],
     3.6, {"floor": GROUND})

_hsw1 = _pose((44, 74), 180.0, wr=((44, 94), (44, 94)), w=2.6, elbow=(1, -1))
_hsw2 = _pose((56, 74), 180.0, wr=((56, 94), (56, 94)), w=2.6, elbow=(1, -1))
_add("handstand_walk", "Handstand Walk", [_hsw1, _hsw2, _hsw1],
     ["Balance", "Step the hands forward", "Step back"],
     ["Start in a solid handstand, legs together.",
      "Walk the hands forward one at a time, keep the hips stacked.",
      "Walk back the other way without stopping."],
     3.0, {"floor": GROUND})

_press1 = _pose((50, 76), 204.8, wr=((50, 94), (50, 94)), w=2.6, elbow=(1, -1),
                an=((26, 66), (26, 66)), knee_pts=((32, 54), (32, 54)))
_press2 = _pose((50, 75), 190.0, wr=((50, 94), (50, 94)), w=2.6, elbow=(1, -1),
                an=((36, 42), (36, 42)), knee_pts=((38, 56), (38, 56)))
_press3 = _pose((50, 74), 180.0, wr=((50, 94), (50, 94)), w=2.6, elbow=(1, -1))
_add("press_handstand", "Press Handstand", [_press1, _press2, _press3, _press3],
     ["Pike position", "Press up", "Handstand", "Hold"],
     ["Hands on the floor, hips high, legs bent.",
      "Push the shoulders up and straighten the legs overhead.",
      "Reach the stacked handstand position.",
      "Hold the line, shoulders pushed away from the ears."],
     3.6, {"floor": GROUND})


# ------------------------------------------------------- SKILL PROGRESSIONS
_crow_squat = _pose((44, 70), 70.0, wr=((44, 90), (44, 90)), w=2.6,
                    an=((72, 92), (72, 92)))
_crow = _pose((44, 76), 96.3, wr=((44, 94), (44, 94)), w=2.6, elbow=(-1, -1),
              an=((62, 74), (62, 74)), knee_pts=((52, 80), (52, 80)))
_add("crow", "Crow Pose", [_crow_squat, _crow, _crow],
     ["Deep squat", "Lean forward", "Crow hold"],
     ["Squat low, hands on the floor in front of the feet.",
      "Shift the shoulders forward of the hands, knees onto the elbows.",
      "Hold the feet off the floor, look slightly forward."],
     3.0, {"floor": GROUND})

_mu_hang = _pose((50, 50), 0, wr=((44, 30), (56, 30)), w=3.0)
_mu_pull = _pose((50, 40), 0, wr=((44, 30), (56, 30)), w=3.0)
_mu_high = _pose((50, 31), 0, wr=((44, 30), (56, 30)), w=3.0)
_mu_tr = _pose((48, 26), 60.0, wr=((44, 30), (56, 30)), w=3.0, elbow=(1, -1))
_mu_sup = _pose((50, 10), 0, wr=((44, 30), (56, 30)), w=3.0)
_add("muscle_up", "Muscle-Up",
     [_mu_hang, _mu_pull, _mu_high, _mu_tr, _mu_sup, _mu_sup],
     ["Dead hang", "Explosive pull", "Chin over the bar",
      "Transition over the bar", "Support above the bar", "Support above the bar"],
     ["Start from a still dead hang, shoulders engaged.",
      "Pull high and fast, drive the elbows down towards the ribs.",
      "The chest rises to bar height, wrists still over the bar.",
      "Lean the chest over the bar and turn the elbows down and back.",
      "Push to a straight-arm support above the bar.",
      "Hold the support, shoulders down and away from the ears."],
     5.0, {"bar": (38, 62, 30)})
_add("mu_transition", "Muscle-Up Transition",
     [_mu_hang, _mu_high, _mu_tr, _mu_sup, _mu_sup],
     ["Dead hang", "High pull", "Transition over the bar", "Support", "Support"],
     ["Hang with straight arms, no swinging.",
      "Pull the chin above the bar as high as possible.",
      "Roll the chest over the bar with the elbows driving down.",
      "Finish in a straight-arm support above the bar.",
      "The whole transition happens close to the bar, no kipping."],
     4.0, {"bar": (38, 62, 30)})

_stc1 = _pose((50, 38), 0, wr=((46, 18), (54, 18)), w=3.0)
_stc2 = _pose((50, 38), 180.0, wr=((46, 18), (54, 18)), w=3.0,
               an=((52, 46), (48, 46)), knee_pts=((54, 34), (46, 34)))
_stc3 = _pose((50, 38), 180.0, wr=((46, 18), (54, 18)), w=3.0,
               an=((36, 3), (38, 5)), knee_pts=((44, 12), (45, 13)))
_add("skin_the_cat", "Skin the Cat", [_stc1, _stc2, _stc3, _stc2, _stc1],
     ["Hang", "Invert the hips", "Rotate the feet forward", "Back through", "Hang"],
     ["Hang with straight arms and a closed grip.",
      "Tuck the hips and pull the feet towards the bar.",
      "Open the hips and bring the feet over and in front of the bar.",
      "Keep the arms straight and control the rotation.",
      "Return to the hang the same way you came in."],
     4.6, {"bar": (40, 60, 18)})

# ------------------------------------------------------- EXPLOSIVE
_clap1 = _push((68, 72), -62.7, wr=(72, 86))
_clap2 = _push((68, 84), -76.1, wr=(74, 94))
_add("clap_pushup", "Clap Push-Up", [_clap1, _clap2, _clap1],
     ["Hands leave the floor", "Land and absorb", "Press up"],
     ["Push explosively so the hands can leave the floor.",
      "Clap in the air, land with soft elbows.",
      "The body stays in one line the whole time."],
     2.6, {"floor": GROUND})

_js_stand = _pose((50, 52), 0, wr=((50, 71), (50, 71)), w=3.0)
_js_bot = _pose((52, 58), -23.2, wr=((64, 60), (64, 60)), w=3.0, elbow=(1, -1))
_js_air = _pose((50, 40), 0, wr=((43, 22), (57, 22)), w=3.0, elbow=(1, -1))
_add("jump_squat", "Jump Squat", [_js_stand, _js_bot, _js_air, _js_stand],
     ["Stand", "Load the squat", "Jump", "Land"],
     ["Feet shoulder-width, arms ready.",
      "Sit the hips back and load the body.",
      "Explode up and reach the arms overhead.",
      "Land quietly in the squat and absorb the impact."],
     3.0, {"floor": GROUND})

_jl_stand = _pose((50, 52), 0, wr=((50, 71), (50, 71)), w=3.0)
_jl_bot = _pose((52, 60), 0, wr=((56, 78), (56, 78)), w=3.0, an=((68, 93), (34, 93)),
                knee_pts=((61, 80), (44, 86)))
_jl_air = _pose((52, 44), 0, wr=((43, 24), (61, 24)), w=3.0, an=((68, 85), (38, 84)),
                knee_pts=((62, 70), (46, 74)))
_add("jump_lunge", "Jump Lunge", [_jl_stand, _jl_bot, _jl_air, _jl_stand],
     ["Standing", "Load the lunge", "Jump", "Land"],
     ["Take a long split stance with the front foot planted.",
      "Lower the back knee and load the front leg.",
      "Drive up and switch the legs in the air.",
      "Land softly in a lunge and absorb."],
     3.2, {"floor": GROUND})

_bj_squat = _pose((44, 52), 0, wr=((44, 71), (44, 71)), w=3.0)
_bj_air = _pose((44, 38), 0, wr=((37, 20), (51, 20)), w=3.0, elbow=(1, -1))
_bj_land = _pose((44, 66), 0, wr=((44, 86), (44, 86)), w=3.0, an=((68, 86), (68, 86)),
                 knee_pts=((58, 78), (58, 78)))
_add("box_jump", "Box Jump", [_bj_squat, _bj_air, _bj_land],
     ["Prepare", "Jump towards the box", "Land on the box"],
     ["Stand close to the box, arms ready.",
      "Jump up and forward, drive the knees up.",
      "Land with the feet on the box, knees bent, soft landing."],
     3.0, {"floor": GROUND, "box": (56, 72, 26, 24)})

_tj_stand = _pose((50, 52), 0, wr=((50, 71), (50, 71)), w=3.0)
_tj_air = _pose((50, 44), 0, wr=((44, 24), (56, 24)), w=3.0, elbow=(1, -1),
                an=((48, 36), (52, 36)), knee_pts=((44, 48), (56, 48)))
_add("tuck_jump", "Tuck Jump", [_tj_stand, _tj_air, _tj_stand],
     ["Stand", "Tuck jump", "Land"],
     ["Stand tall with the arms ready.",
      "Jump and pull the knees up towards the chest.",
      "Land on both feet with the knees bent."],
     2.6, {"floor": GROUND})

_bur_squat = _pose((50, 52), 0, wr=((50, 71), (50, 71)), w=3.0)
_bur_plank = _pose((64, 74), -58.0, wr=((64, 94), (64, 94)), w=1.2, elbow=(-1, -1))
_bur_jump = _pose((50, 40), 0, wr=((43, 22), (57, 22)), w=3.0, elbow=(1, -1))
_add("burpee", "Burpee", [_bur_squat, _bur_plank, _bur_jump, _bur_squat],
     ["Stand", "Kick back to a plank", "Jump up", "Land and stand"],
     ["Start standing, hands on the floor ready.",
      "Kick the feet back into a straight-arm plank.",
      "Jump the feet in and drive up with a jump.",
      "Land quietly and stand up again."],
     3.4, {"floor": GROUND})


# ============================================================ generic fallback
_gen = _pose((50, 52), 0, wr=((50, 71), (50, 71)), w=3.0)
_add("generic", "Movement", [_gen, _gen],
     ["Start position", "End position"],
     ["Every rep starts and ends in the same controlled position.",
      "Move through the full range of motion with control."],
     3.2, {"floor": GROUND})


def anim_for(ex):
    """Return the :class:`Anim` for an exercise (dict, id or ``None``)."""
    key = None
    if isinstance(ex, dict):
        key = ex.get("anim")
    elif isinstance(ex, str):
        key = ex
    if not key:
        return None
    return ANIMS.get(key)


def anim_for_exercise(ex):
    """Animation for a built-in exercise dict, with a generic fallback."""
    a = anim_for(ex)
    return a if a is not None else ANIMS["generic"]


def phase_breakdown(anim):
    """List of ``(label, note)`` pairs describing the animation phases."""
    if anim is None:
        return []
    return list(zip(anim.labels, anim.notes))


def _ease(t):
    """Smoothstep easing so the transitions look natural."""
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * (3.0 - 2.0 * t)


def _lerp_pose(a, b, t):
    """Interpolate two poses into a new pose dictionary."""
    out = {}
    for k in a:
        pa, pb = a[k], b[k]
        out[k] = (pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t)
    return out


def _pose_at(anim, pos):
    """Pose at a fractional frame position (wraps around when looping)."""
    n = len(anim.frames)
    if n == 1:
        return anim.frames[0], 0
    p = pos % (n if anim.loop else max(1, n - 1))
    i = int(math.floor(p))
    f = p - i
    j = (i + 1) % n
    if not anim.loop and i >= n - 1:
        return anim.frames[n - 1], n - 1
    a = anim.frames[i]
    b = anim.frames[j]
    return _lerp_pose(a, b, _ease(f)), i


# ================================================================== widgets
class FigureView(QWidget):
    """Draws a single pose (and the equipment around it) with QPainter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(240, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._pose = None
        self._anim = None
        self._accent = QColor("#4dabf7")
        self._skin = QColor("#e9edf5")
        self._gear = QColor("#5a6474")
        self._scale = 1.0
        self._off = QPointF(0, 0)

    # ---------------------------------------------------------------- setup
    def set_anim(self, anim):
        self._anim = anim
        if anim and anim.frames:
            self._pose = anim.frames[0]
        self.update()

    def set_pose(self, pose):
        self._pose = pose
        self.update()

    def set_colors(self, accent, skin=None, gear=None):
        self._accent = QColor(accent)
        if skin:
            self._skin = QColor(skin)
        if gear:
            self._gear = QColor(gear)
        self.update()

    # --------------------------------------------------------------- helpers
    def _map(self, p):
        return QPointF(self._off.x() + p[0] * self._scale,
                       self._off.y() + p[1] * self._scale)

    def _line(self, painter, a, b, color, width):
        pen = QPen(color)
        pen.setWidthF(width)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(self._map(a), self._map(b))

    def _dot(self, painter, p, r, color):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        c = self._map(p)
        painter.drawEllipse(c, r, r)

    def _geo(self):
        w, h = self.width(), self.height()
        s = min(w, h) / CANVAS
        return s, QPointF((w - CANVAS * s) / 2.0, (h - CANVAS * s) / 2.0)

    # ------------------------------------------------------------- painting
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#0b0e14"))
        self._scale, self._off = self._geo()
        props = (self._anim.props if self._anim else {}) or {}
        self._draw_props(painter, props)
        if self._pose:
            self._draw_figure(painter, self._pose)

    def _draw_props(self, painter, props):
        s = self._scale
        ground = props.get("floor")
        if ground:
            self._line(painter, (0, ground), (100, ground), QColor("#39414f"), 2.0)
        bar = props.get("bar")
        if bar:
            x0, x1, y = bar
            self._line(painter, (x0, y), (x1, y), QColor("#7d8798"), 2.6)
            self._line(painter, (x0, y - 2.4), (x0, y + 2.4), QColor("#7d8798"), 2.0)
            self._line(painter, (x1, y - 2.4), (x1, y + 2.4), QColor("#7d8798"), 2.0)
        for b in props.get("bars", []) or []:
            x0, x1, y = b
            self._line(painter, (x0, y), (x1, y), QColor("#7d8798"), 2.6)
            self._line(painter, (x0, y - 2.2), (x0, y + 3.0), QColor("#5a6474"), 1.8)
            self._line(painter, (x1, y - 2.2), (x1, y + 3.0), QColor("#5a6474"), 1.8)
        box = props.get("box")
        if box:
            x, ytop, bw, bh = box
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#2a3140")))
            tl = self._map((x, ytop))
            painter.drawRect(QRectF(tl.x(), tl.y(), bw * s, bh * s))
            self._line(painter, (x, ytop), (x + bw, ytop), QColor("#4d5666"), 2.0)
        wall = props.get("wall")
        if wall:
            x, y0, y1 = wall
            self._line(painter, (x, y0), (x, y1), QColor("#39414f"), 3.0)
        pole = props.get("pole")
        if pole:
            x, y0, y1 = pole
            self._line(painter, (x, y0), (x, y1), QColor("#7d8798"), 3.0)
        wheel = props.get("wheel")
        if wheel and self._pose:
            x, y = wheel
            painter.setPen(QPen(QColor("#9aa4b5"), 2.0))
            painter.setBrush(Qt.NoBrush)
            c = self._map((x, y))
            painter.drawEllipse(c, 3.2 * s, 3.2 * s)
        band = props.get("band")
        if band and self._pose:
            x, y = band
            for key in ("an_l", "an_r"):
                self._line(painter, self._pose[key], (x, y), QColor("#d97757"), 2.0)

    def _draw_figure(self, painter, p):
        s = self._scale
        limb = max(1.5, 3.1 * s)
        torso = max(1.5, 4.0 * s)
        joint = max(1.0, 1.9 * s)

        # --- torso (filled trapezoid between shoulders and hips)
        sh_l, sh_r = p["sh_l"], p["sh_r"]
        hip = p["hip"]
        dbx, dby = hip[0] - (sh_l[0] + sh_r[0]) / 2.0, hip[1] - (sh_l[1] + sh_r[1]) / 2.0
        n = (dbx * dbx + dby * dby) or 1.0
        dbx, dby = dbx / n, dby / n
        px, py = dby, -dbx
        hx, hy = hip[0], hip[1]
        poly = QPolygonF([
            self._map((sh_l[0] + px * 1.4, sh_l[1] + py * 1.4)),
            self._map((sh_r[0] + px * 1.4, sh_r[1] + py * 1.4)),
            self._map((hx + px * 2.0, hy + py * 2.0)),
            self._map((hx - px * 2.0, hy - py * 2.0)),
        ])
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(self._accent))
        painter.drawPolygon(poly)

        # --- neck + head
        self._line(painter, p["neck"], p["head"], self._skin, limb * 0.8)
        hr = max(1.6, 3.6 * s)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(self._skin))
        c = self._map(p["head"])
        painter.drawEllipse(c, hr, hr)

        # --- arms
        for sname, ename, wname in (("sh_l", "el_l", "wr_l"),
                                    ("sh_r", "el_r", "wr_r")):
            self._line(painter, p[sname], p[ename], self._accent, limb)
            self._line(painter, p[ename], p[wname], self._skin, limb * 0.85)
            self._dot(painter, p[ename], joint * 0.7, self._accent.darker(140))

        # --- legs
        for kname, aname in (("kn_l", "an_l"), ("kn_r", "an_r")):
            self._line(painter, p["hip"], p[kname], self._accent, limb)
            self._line(painter, p[kname], p[aname], self._skin, limb * 0.85)
            self._dot(painter, p[kname], joint * 0.7, self._accent.darker(140))

        # --- hands and feet
        for wname in ("wr_l", "wr_r"):
            self._dot(painter, p[wname], joint * 0.85, self._skin)
        db = (dbx, dby)
        foot = (db[1], -db[0])
        for aname in ("an_l", "an_r"):
            a = p[aname]
            toe = (a[0] + foot[0] * 4.2, a[1] + foot[1] * 4.2)
            self._line(painter, a, toe, self._skin, limb * 0.75)


class AnimationPlayer(QWidget):
    """Looping animation player with play/pause, restart, speed and phases."""

    def __init__(self, anim=None, parent=None):
        super().__init__(parent)
        self._anim = None
        self._pos = 0.0
        self._speed = 1.0
        self._playing = True
        self._last = 0.0

        self.view = FigureView(self)
        self.phase_label = QLabel("-")
        self.phase_label.setObjectName("sectionTitle")
        self.note_label = QLabel("")
        self.note_label.setObjectName("plain")
        self.note_label.setWordWrap(True)

        self.btn_play = QPushButton("Pause")
        self.btn_play.setObjectName("ghost")
        self.btn_restart = QPushButton("Restart")
        self.btn_restart.setObjectName("ghost")
        self.speed = QComboBox(self)
        self.speed.addItem("0.25x", 0.25)
        self.speed.addItem("0.5x", 0.5)
        self.speed.addItem("1x", 1.0)
        self.speed.addItem("1.5x", 1.5)
        self.speed.addItem("2x", 2.0)
        self.speed.setCurrentIndex(2)
        self.speed.setObjectName("ghost")

        self.slider = QWidget(self)
        self.slider.setFixedHeight(4)
        self.progress = _ProgressBar(self.slider)

        self.phases = _PhaseList(self)
        self.phases.itemClicked.connect(self._jump_to)

        self.btn_play.clicked.connect(self.toggle)
        self.btn_restart.clicked.connect(self.restart)
        self.speed.currentIndexChanged.connect(self._speed_changed)

        left = QVBoxLayout()
        left.addWidget(self.view, 1)
        left.addWidget(self.progress)
        left_widget = QWidget(self)
        left_widget.setLayout(left)

        right = QVBoxLayout()
        right.addWidget(self.phase_label)
        right.addWidget(self.note_label)
        right.addWidget(self.phases, 1)

        ctrl = QHBoxLayout()
        ctrl.addWidget(self.btn_restart)
        ctrl.addWidget(self.btn_play)
        ctrl.addWidget(self.speed)
        ctrl.addStretch(1)
        right.addLayout(ctrl)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(left_widget, 3)
        lay.addLayout(right, 2)
        self.setLayout(lay)

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self.set_anim(anim)

    # -------------------------------------------------------------- public
    def set_anim(self, anim):
        self._anim = anim
        self._pos = 0.0
        if anim:
            self.view.set_anim(anim)
            self.phases.set_phases(anim.labels, anim.notes)
            self._apply_phase(0)
        else:
            self.view.set_anim(None)
            self.phases.set_phases([], [])
            self.phase_label.setText("No animation")
            self.note_label.setText("This exercise has no animation yet.")

    def set_colors(self, accent, skin=None, gear=None):
        self.view.set_colors(accent, skin, gear)

    def toggle(self):
        self.set_playing(not self._playing)

    def set_playing(self, playing):
        self._playing = playing
        self.btn_play.setText("Pause" if playing else "Play")
        if playing:
            self._timer.start()
        else:
            self._timer.stop()

    def restart(self):
        self._pos = 0.0
        self._render()

    def stop(self):
        """Stop the timer. Call this before the widget is destroyed."""
        try:
            self._timer.stop()
        except RuntimeError:
            pass
        self._playing = False

    def _speed_changed(self, idx):
        self._speed = float(self.speed.itemData(idx))

    def _jump_to(self, item):
        idx = self.phases.row(item)
        if idx < 0:
            return
        self._pos = float(idx)
        self._render()

    # -------------------------------------------------------------- private
    def _tick(self):
        if not self._anim or not self._anim.frames:
            return
        n = len(self._anim.frames)
        step = (self._timer.interval() / 1000.0) * self._speed
        limit = float(n if self._anim.loop else max(1, n - 1))
        self._pos += step
        if self._pos > limit:
            if self._anim.loop:
                self._pos = self._pos % limit if limit else 0.0
            else:
                self._pos = limit
                self.set_playing(False)
        self._render()

    def _render(self):
        if not self._anim or not self._anim.frames:
            return
        pose, idx = _pose_at(self._anim, self._pos)
        self.view.set_pose(pose)
        self._apply_phase(idx)
        n = len(self._anim.frames)
        self.progress.set_value((self._pos / max(1, n - 1)) if n > 1 else 0.0)

    def _apply_phase(self, idx):
        if not self._anim:
            return
        labels = self._anim.labels
        notes = self._anim.notes
        if not labels:
            return
        i = max(0, min(idx, len(labels) - 1))
        self.phase_label.setText("%d/%d  %s" % (i + 1, len(labels), labels[i]))
        if i < len(notes):
            self.note_label.setText(notes[i])
        self.phases.set_active(i)


class _ProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._v = 0.0

    def set_value(self, v):
        self._v = max(0.0, min(1.0, v))
        self.update()

    def paintEvent(self, _e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#1b2230"))
        w = self.width() * self._v
        painter.fillRect(QRectF(0, 0, w, self.height()), QColor("#4dabf7"))


class _PhaseList(QListWidget):
    """Compact list of the animation phases."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("plain")
        self.setSelectionMode(QListWidget.SingleSelection)
        self.setFocusPolicy(Qt.NoFocus)

    def set_phases(self, labels, notes):
        self.clear()
        for i, label in enumerate(labels or []):
            item = QListWidgetItem("%d. %s" % (i + 1, label))
            item.setToolTip(notes[i] if i < len(notes or []) else "")
            self.addItem(item)
        if self.count():
            self.setCurrentRow(0)

    def set_active(self, index):
        if 0 <= index < self.count():
            if self.currentRow() != index:
                self.setCurrentRow(index)
            self.scrollToItem(self.item(index))


class AnimationDialog(QDialog):
    """Modal dialog with the animation and its technique breakdown."""

    def __init__(self, anim, title="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title or (anim.title if anim else "Animation"))
        self.resize(860, 520)
        lay = QVBoxLayout(self)
        head = QLabel(self.windowTitle())
        head.setObjectName("pageTitle")
        lay.addWidget(head)
        self.player = AnimationPlayer(anim, self)
        lay.addWidget(self.player, 1)
        btn = QPushButton("Close")
        btn.setObjectName("ghost")
        btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(btn)
        lay.addLayout(row)
