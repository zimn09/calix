"""Procedural audio for CALIX: UI sound effects and background music.

Everything is synthesized in pure Python and cached as small WAV files in the
data folder, so the app stays completely offline and ships no audio assets.

Qt is only used for playback:

* ``QSoundEffect``  - short effects (button clicks, level-up, achievements)
* ``QMediaPlayer``  - the looping background music

If Qt Multimedia or an audio device is missing, the engine silently degrades to
"no sound" and the rest of the app keeps working exactly the same.

The synthesiser itself has no Qt dependency, so it can be tested headlessly:

    >>> generate_sfx("/tmp/x")            # writes click/toggle/... WAV files
    >>> generate_track("/tmp/x", "temple")  # writes one music loop

All waveforms are generated as *periodic* buffers (note tails wrap around), so
the music loops without a click at the seam.
"""
from __future__ import annotations

import math
import os
import random
import sys
import threading
import wave
from array import array
from pathlib import Path

SAMPLE_RATE = 22050
CACHE_VERSION = 1

# --------------------------------------------------------------------------- synth


def _note_hz(midi):
    """Frequency of a MIDI note (69 = A4 = 440 Hz)."""
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def _blank(seconds):
    return [0.0] * max(1, int(seconds * SAMPLE_RATE))


def _env(i, n, attack, release):
    """Linear attack / release envelope, 1.0 in between."""
    a = max(1, int(attack * SAMPLE_RATE))
    r = max(1, int(release * SAMPLE_RATE))
    if i < a:
        return i / a
    if i > n - r:
        return max(0.0, (n - i) / r)
    return 1.0


def _tone(dur, freq, amp=0.3, harm=(1.0, 0.25), attack=0.005, release=0.05,
          decay=3.0, sweep=0.0, vibrato=0.0):
    """One synthesized note: additive sines with a pluck or pad envelope.

    sweep   1.0 = constant pitch, 0.5 = ends an octave lower (a "pop")
    decay   exponential decay rate (0 = a sustained pad)
    """
    n = max(1, int(dur * SAMPLE_RATE))
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / n
        f = freq * (1.0 + (sweep - 1.0) * t) if sweep else freq
        if vibrato:
            f *= 1.0 + vibrato * math.sin(2.0 * math.pi * 5.2 * i / SAMPLE_RATE)
        phase += 2.0 * math.pi * f / SAMPLE_RATE
        e = _env(i, n, attack, release)
        if decay:
            e *= math.exp(-decay * t)
        s = 0.0
        for k, a in enumerate(harm):
            s += a * math.sin(phase * (k + 1))
        out[i] = amp * e * s
    return out


def _noise(dur, amp, rng, decay=24.0, attack=0.001):
    n = max(1, int(dur * SAMPLE_RATE))
    out = [0.0] * n
    for i in range(n):
        t = i / n
        out[i] = amp * _env(i, n, attack, 0.02) * math.exp(-decay * t) * rng.uniform(-1.0, 1.0)
    return out


def _mix(buf, start, samples, wrap=False):
    """Add samples to buf at start; wrap=True makes the buffer periodic."""
    n = len(buf)
    if wrap:
        for i, v in enumerate(samples):
            buf[(start + i) % n] += v
    else:
        for i, v in enumerate(samples):
            j = start + i
            if j >= n:
                break
            buf[j] += v


def _normalise(buf, peak=0.88):
    m = max((abs(v) for v in buf), default=0.0)
    if m > peak:
        k = peak / m
        return [v * k for v in buf]
    return buf


def _wav_bytes(buf):
    """16-bit mono PCM WAV in memory."""
    pcm = array("h", (int(max(-1.0, min(1.0, v)) * 32767.0) for v in buf))
    if sys.byteorder == "big":                       # WAV is little endian
        pcm.byteswap()
    data = pcm.tobytes()
    import io
    bio = io.BytesIO()
    with wave.open(bio, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(data)
    return bio.getvalue()


def _write_wav(path, buf):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(_wav_bytes(_normalise(buf)))
    os.replace(tmp, path)                            # atomic: a half written file is never played
    return path


# ---------------------------------------------------------------------- effects
def _make_click():
    """A short pitch-dropping pop - the sound of pressing a button."""
    buf = _blank(0.12)
    _mix(buf, 0, _tone(0.08, 820, 0.55, harm=(1.0, 0.35, 0.12), sweep=0.58, decay=6.5,
                       attack=0.001, release=0.02))
    _mix(buf, 0, _noise(0.018, 0.22, random.Random(7)))
    return buf


def _make_toggle():
    """Two quick notes: something was added / switched."""
    buf = _blank(0.18)
    _mix(buf, 0, _tone(0.07, _note_hz(76), 0.34, harm=(1.0, 0.25), decay=7.0))
    _mix(buf, int(0.055 * SAMPLE_RATE), _tone(0.10, _note_hz(83), 0.30, harm=(1.0, 0.25), decay=7.0))
    return buf


def _make_success():
    """C major arpeggio."""
    buf = _blank(0.75)
    for i, note in enumerate((72, 76, 79)):
        _mix(buf, int(i * 0.075 * SAMPLE_RATE),
             _tone(0.5, _note_hz(note), 0.30, harm=(1.0, 0.3, 0.1), decay=3.4))
    return buf


def _make_achievement():
    """Brighter, longer arpeggio for an unlocked achievement."""
    buf = _blank(1.1)
    for i, note in enumerate((72, 76, 79, 84, 88)):
        _mix(buf, int(i * 0.07 * SAMPLE_RATE),
             _tone(0.75, _note_hz(note), 0.26, harm=(1.0, 0.35, 0.12), decay=2.8))
    return buf


def _make_levelup():
    """Rising run with a shimmering fifth on top."""
    buf = _blank(1.5)
    for i, note in enumerate((60, 64, 67, 72, 76, 79)):
        _mix(buf, int(i * 0.09 * SAMPLE_RATE),
             _tone(1.1, _note_hz(note), 0.24, harm=(1.0, 0.3, 0.15), decay=2.4))
    _mix(buf, int(0.5 * SAMPLE_RATE), _tone(0.9, _note_hz(84), 0.12,
                                            harm=(1.0, 0.2), decay=1.6, attack=0.05))
    return buf


SFX_BUILDERS = {
    "click": _make_click,
    "toggle": _make_toggle,
    "success": _make_success,
    "achievement": _make_achievement,
    "levelup": _make_levelup,
}
SFX_NAMES = tuple(SFX_BUILDERS)


def sfx_path(directory, name):
    return Path(directory) / f"sfx-{name}-v{CACHE_VERSION}.wav"


def generate_sfx(directory):
    """Write every effect (tiny files) and return {name: path}."""
    out = {}
    for name, build in SFX_BUILDERS.items():
        path = sfx_path(directory, name)
        if not path.exists() or path.stat().st_size < 1000:
            _write_wav(path, build())
        out[name] = path
    return out


# ------------------------------------------------------------------------ music
TRACKS = [
    {"id": "temple", "name": "Temple Bells", "bpm": 66, "bars": 4, "seed": 11,
     "desc": "Calm, warm bells over a slow drone.",
     "chords": ((50, 53, 57), (46, 50, 53), (41, 45, 48), (43, 47, 50))},     # Dm Bb F G
    {"id": "forge", "name": "Iron Forge", "bpm": 100, "bars": 4, "seed": 23,
     "desc": "Driving minor arpeggio for heavy sets.",
     "chords": ((40, 43, 47), (36, 40, 43), (43, 47, 50), (38, 42, 45))},     # Em C G D
    {"id": "void", "name": "Void Drone", "bpm": 48, "bars": 2, "seed": 31,
     "desc": "Dark, almost static ambient pad.",
     "chords": ((37, 40, 44), (33, 37, 40))},                                 # C#m A
    {"id": "dawn", "name": "Dawn Run", "bpm": 116, "bars": 4, "seed": 47,
     "desc": "Bright major arpeggio, energetic.",
     "chords": ((48, 52, 55), (43, 47, 50), (45, 48, 52), (41, 45, 48))},     # C G Am F
]
TRACK_BY_ID = {t["id"]: t for t in TRACKS}
TRACK_IDS = tuple(t["id"] for t in TRACKS)


def music_path(directory, track_id):
    return Path(directory) / f"music-{track_id}-v{CACHE_VERSION}.wav"


def loop_seconds(track):
    return 4.0 * track["bars"] * 60.0 / track["bpm"]


def _render_music(track):
    """A seamless loop: bass drone, pad, arpeggio and a sparse melody."""
    beat = 60.0 / track["bpm"]
    n = int(loop_seconds(track) * SAMPLE_RATE)
    buf = [0.0] * n
    rng = random.Random(track["seed"])
    drone = track["id"] == "void"

    for bar, chord in enumerate(track["chords"]):
        start = int(bar * 4 * beat * SAMPLE_RATE)
        root, third, fifth = chord
        # bass drone - one long note per bar
        _mix(buf, start, _tone(4 * beat, _note_hz(root), 0.17,
                               harm=(1.0, 0.45, 0.20, 0.08), attack=0.30,
                               release=0.45, decay=0.0), wrap=True)
        # soft pad with the upper chord tones
        for note in (third, fifth):
            _mix(buf, start, _tone(4 * beat, _note_hz(note), 0.055,
                                   harm=(1.0, 0.30), attack=0.55,
                                   release=0.75, decay=0.0), wrap=True)

    # arpeggio - the pulse of the track
    steps = 4 if drone else 8
    for bar, chord in enumerate(track["chords"]):
        for step in range(steps):
            note = chord[step % len(chord)] + (12 if (step // len(chord)) % 2 else 0)
            start = int((bar * 4 + step * (4.0 / steps)) * beat * SAMPLE_RATE)
            dur = 2.2 * beat if drone else 0.85 * beat
            amp = 0.05 if drone else 0.115
            _mix(buf, start, _tone(dur, _note_hz(note), amp,
                                   harm=(1.0, 0.28, 0.07), attack=0.004,
                                   release=0.22, decay=3.6), wrap=True)

    # sparse high bells (deterministic, seeded)
    bells = 3 if not drone else 2
    for _ in range(bells):
        bar = rng.randrange(track["bars"])
        tonic = track["chords"][bar][rng.randrange(3)]
        note = tonic + 24
        start = int((bar * 4 + rng.choice((0, 2))) * beat * SAMPLE_RATE)
        _mix(buf, start, _tone(1.8 * beat, _note_hz(note), 0.06,
                               harm=(1.0, 0.15), attack=0.01, release=0.5,
                               decay=1.7), wrap=True)

    return buf


def generate_track(directory, track_id):
    """Render one music loop to disk (a couple of seconds of CPU) and return its path."""
    track = TRACK_BY_ID[track_id]
    path = music_path(directory, track_id)
    if path.exists() and path.stat().st_size > 1000:
        return path
    return _write_wav(path, _render_music(track))


def ensure_all(directory):
    """Generate every asset (used by the tests and by a background warm-up)."""
    out = generate_sfx(directory)
    for tid in TRACK_IDS:
        out[tid] = generate_track(directory, tid)
    return out


def default_audio_dir():
    """Same folder as the database, so SKILLTREE_DATA moves the cache too."""
    base = Path(os.environ.get("SKILLTREE_DATA") or Path.home() / ".calisthenics_skill_tree")
    return base / "audio"


# -------------------------------------------------------------------- Qt player
try:                                                  # Qt Multimedia is part of PySide6 Addons
    from PySide6.QtCore import QEvent, QLoggingCategory, QObject, QUrl, Signal
    from PySide6.QtMultimedia import (QAudioOutput, QMediaDevices, QMediaPlayer,
                                      QSoundEffect)
    from PySide6.QtWidgets import QAbstractButton
    # The FFmpeg backend prints an "Input #0 ..." banner for every file it opens.
    # Silence its info messages (real warnings and errors still show).
    _rules = os.environ.get("QT_LOGGING_RULES", "")
    QLoggingCategory.setFilterRules((_rules + "\n" if _rules else "") + "qt.multimedia.*.info=false")
    QT_AUDIO = True
except Exception:                                     # pragma: no cover - depends on the install
    QT_AUDIO = False

    class _Stub:                                      # minimal stand-in so the module always imports
        def __init__(self, *a, **k):
            pass

    class AudioEngine(_Stub):
        available = False

        def __init__(self, settings, directory=None, parent=None):
            self.settings = settings

        def apply(self):
            pass

        def sfx(self, name="click", force=False):
            pass

        def play_music(self, track_id):
            pass

        def stop_music(self):
            pass

        def close(self):
            pass

    class ClickSfxFilter(_Stub):
        def __init__(self, engine, parent=None):
            super().__init__(parent)
            self.engine = engine

        def eventFilter(self, obj, ev):
            return False


if QT_AUDIO:

    class AudioEngine(QObject):
        """Plays the generated effects and the looping background music."""

        trackReady = Signal(str)

        def __init__(self, settings, directory=None, parent=None):
            super().__init__(parent)
            self.settings = settings
            self.directory = Path(directory) if directory else default_audio_dir()
            self.available = True
            self._sfx_on = True
            self._sfx_volume = 0.6
            self._music_volume = 0.3
            self._track = None
            self._pending = None
            self._building = set()
            self._effects = {}
            self._music = None
            self._output = None
            self._has_output = False

            try:
                generate_sfx(self.directory)          # tiny: build before the first click
                self._effects = {name: QSoundEffect(self) for name in SFX_NAMES}
                for name, effect in self._effects.items():
                    effect.setSource(QUrl.fromLocalFile(str(sfx_path(self.directory, name))))
                    effect.setLoopCount(1)
            except Exception:                         # pragma: no cover
                self.available = False
                self._effects = {}

            try:
                self._has_output = bool(QMediaDevices.audioOutputs())
                self._output = QAudioOutput(self)
                self._music = QMediaPlayer(self)
                self._music.setAudioOutput(self._output)
                self._music.setLoops(QMediaPlayer.Infinite)
                self._music.errorOccurred.connect(self._music_failed)
            except Exception:                         # pragma: no cover
                self._music = None
                self._has_output = False

            self.trackReady.connect(self._on_track_ready)

        # ------------------------------------------------------------- settings
        def apply(self):
            """Read the settings, set volumes and start/stop the music."""
            cfg = self.settings.all()
            self._sfx_on = bool(cfg.get("sfx", True)) and self.available
            self._sfx_volume = max(0.0, min(1.0, float(cfg.get("sfx_volume", 60)) / 100.0))
            self._music_volume = max(0.0, min(1.0, float(cfg.get("music_volume", 30)) / 100.0))
            if self._output is not None:
                self._output.setVolume(self._music_volume)
            track = cfg.get("music_track", "temple")
            wanted = bool(cfg.get("music", True)) and track in TRACK_BY_ID
            if wanted and self._music is not None:
                self.play_music(track)
            else:
                self.stop_music()

        # ------------------------------------------------------------------ sfx
        def sfx(self, name="click", force=False):
            """Play an effect. force=True lets the Settings *Test* button pop even when muted."""
            if not self._sfx_on and not force:
                return
            effect = self._effects.get(name)
            if effect is None:
                return
            try:
                effect.setVolume(self._sfx_volume)
                effect.play()
            except RuntimeError:                       # widget already deleted
                pass

        # ---------------------------------------------------------------- music
        def play_music(self, track_id):
            if self._music is None or track_id not in TRACK_BY_ID:
                return
            if not self._has_output:
                try:
                    self._has_output = bool(QMediaDevices.audioOutputs())
                except Exception:
                    self._has_output = False
            if not self._has_output:                  # no sound card / headless: stay silent
                return
            if self._track == track_id and self._music.playbackState() == QMediaPlayer.PlayingState:
                return
            path = music_path(self.directory, track_id)
            if not path.exists() or path.stat().st_size < 1000:
                self._pending = track_id
                self._build_later(track_id)
                return
            if self._track != track_id:
                self._music.setSource(QUrl.fromLocalFile(str(path)))
                self._track = track_id
            self._output.setVolume(self._music_volume)
            self._music.play()
            self._pending = None

        def stop_music(self):
            self._pending = None
            if self._music is not None:
                self._music.stop()

        def close(self):
            try:
                if self._music is not None:
                    self._music.stop()
                    self._music.setSource(QUrl())
                for effect in self._effects.values():
                    effect.stop()
            except RuntimeError:
                pass

        # -------------------------------------------------------------- private
        def _build_later(self, track_id):
            if track_id in self._building:
                return
            self._building.add(track_id)

            def work():
                try:
                    generate_track(self.directory, track_id)
                except Exception:
                    pass
                finally:
                    self._building.discard(track_id)
                self.trackReady.emit(track_id)

            threading.Thread(target=work, name=f"music-{track_id}", daemon=True).start()

        def _on_track_ready(self, track_id):
            if self._pending != track_id:
                return
            if not self.settings.get("music") or self.settings.get("music_track") != track_id:
                return
            self.play_music(track_id)

        def _music_failed(self, *_args):
            """A missing codec or audio device must never break the app."""
            self._track = None


    class ClickSfxFilter(QObject):
        """Application wide: every button press gets the short pop."""

        def __init__(self, engine, parent=None):
            super().__init__(parent)
            self.engine = engine

        def eventFilter(self, obj, ev):
            try:
                if (ev.type() == QEvent.MouseButtonPress and isinstance(obj, QAbstractButton)
                        and obj.isEnabled() and obj.objectName() != "sfxTest"):
                    self.engine.sfx("click")
            except RuntimeError:
                pass
            return False
