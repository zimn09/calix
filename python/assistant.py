"""CALIX Coach — a local, rule-based assistant. No network, no model, no magic.

It reads free text the way a coach would skim a training note: it looks for the
exercise you mean (fuzzy, typo and slang tolerant), the numbers around it, the
intent of the sentence and the time window, and then either answers from your
database or prepares a change for you to confirm.

    did 3x12 push ups          -> log 3 sets x 12 reps of Push-Up
    plank 1:30                 -> log a 90 s hold
    ran 5k in 26:30            -> log a 5 km run
    sum of reps this week      -> answer from session_sets
    what's my best pull up?    -> answer from records / performances
    what should I train today? -> suggestion from the skill tree
    what is a muscle up?       -> explanation from the skill catalogue

Nothing here imports Qt, so the parser can be unit-tested on its own.
"""
from __future__ import annotations

import datetime as dt
import difflib
import re
import unicodedata
from dataclasses import dataclass, field

# --------------------------------------------------------------------- text


def normalize(text: str) -> str:
    """Lowercase, strip diacritics and punctuation, collapse whitespace."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9:.,x]+", " ", text)
    text = text.replace(",", " ")
    return re.sub(r"\s+", " ", text).strip()


def singular(word: str) -> str:
    if len(word) > 3 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("ses"):
        return word[:-2]
    if len(word) > 2 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokens(text: str) -> list[str]:
    return [singular(t) for t in normalize(text).split() if t]


WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "ninety": 90,
    "half": 0.5, "couple": 2, "par": 2, "jedna": 1, "jeden": 1, "dva": 2,
    "dve": 2, "tri": 3, "ctyri": 4, "pet": 5, "sest": 6, "sedm": 7, "osm": 8,
    "devet": 9, "deset": 10, "dvanact": 12, "patnact": 15, "dvacet": 20,
    "tricet": 30, "ctyricet": 40, "padesat": 50,
}


def number_at(toks: list[str], i: int) -> float | None:
    if i >= len(toks):
        return None
    tok = toks[i]
    if re.fullmatch(r"\d+(?:\.\d+)?", tok):
        return float(tok)
    return WORDS.get(tok)


# ------------------------------------------------------------------- intents

INTENT_WORDS = {
    "log_run": ("ran", "run", "jog", "jogged", "beh", "behl", "behla", "kilometer"),
    "log_set": ("did", "done", "log", "add", "zapsat", "zapis", "udelal", "udelala",
                "splnil", "dneska jsem", "i did", "record that"),
    "query_total": ("sum", "total", "how many", "kolik", "celkem", "soucet", "combined",
                    "altogether", "count"),
    "query_best": ("best", "max", "personal record", "rekord", "nejlepsi", "pr", "record"),
    "query_streak": ("streak", "series", "serie", "dni v rade", "consistency"),
    "query_progress": ("progress", "level", "xp", "rank", "pokrok", "uroven", "how am i doing"),
    "suggest": ("should i", "should i train", "recommend", "suggest", "what next", "doporuc",
                "co trenovat", "what to train", "advice", "next skill"),
    "explain": ("what is", "what are", "how do i", "explain", "co je", "jak se dela",
                "tell me about", "how to"),
    "list_workouts": ("workouts", "my workouts", "treninky", "sestavy"),
    "help": ("help", "pomoc", "commands", "what can you do", "co umis"),
    "greet": ("hey", "hi", "hello", "yo", "hiya", "sup", "ahoj", "cau", "cus", "nazdar",
              "zdravim", "dobry den", "good morning", "good evening", "morning"),
    "thanks": ("thanks", "thank you", "thx", "cheers", "diky", "dik", "diky moc"),
    "bye": ("bye", "goodbye", "see you", "see ya", "mej se", "dobrou noc"),
    "identity": ("who are you", "what are you", "kdo jsi", "co jsi", "are you chatgpt",
                 "are you an ai", "are you a bot", "jsi ai"),
    "last_session": ("last workout", "last session", "what did i do", "yesterday i",
                     "posledni trenink", "co jsem delal", "last time"),
    "trained_today": ("did i train", "have i trained", "trained today", "trenoval jsem",
                      "did i work out", "have i worked out"),
    "mood": ("how are you", "hows it going", "how do you feel", "jak se mas", "jak ti je"),
    "undo": ("undo", "delete that", "delete the last", "smazat", "vratit", "take that back"),
    "correct": ("no", "not", "actually", "meant", "spravne", "oprava"),
    "plan": ("plan", "give me a workout", "workout for", "routine", "sestav", "navrhni",
             "starter", "what should i do"),
    "followup": ("and ", "more", "again", "same", "stejne", "jeste"),
    "level": ("next level", "how much xp", "xp to", "do dalsi urovne", "kolik xp"),
    "compare": ("vs", "versus", "compare", "last week", "minuly tyden", "oproti"),
}

WINDOWS = {
    "today": ("today", "dnes", "tonight"),
    "yesterday": ("yesterday", "vcera"),
    "week": ("week", "this week", "tyden", "tento tyden"),
    "last_week": ("last week", "minuly tyden"),
    "month": ("month", "this month", "mesic"),
    "year": ("year", "this year", "rok"),
}

ALIASES = {
    # english slang / spelling
    "pushup": "pushup", "push up": "pushup", "press up": "pushup",
    "pullup": "pullup", "pull up": "pullup", "chin up": "chinup", "chinup": "chinup",
    "squat": "squat", "pistol": "pistol_squat", "dip": "dip", "row": "row",
    "plank": "plank", "hollow": "hollow_body", "lsit": "l_sit", "l sit": "l_sit",
    "handstand": "handstand", "muscleup": "muscle_up", "muscle up": "muscle_up",
    "front lever": "front_lever", "back lever": "back_lever", "flag": "human_flag",
    # czech
    "klik": "pushup", "kliky": "pushup", "kliku": "pushup",
    "shyb": "pullup", "shyby": "pullup", "shybu": "pullup",
    "drep": "squat", "drepy": "squat", "dreps": "squat",
    "prkno": "plank", "planku": "plank",
    "stojka": "handstand", "svicka": "handstand",
    "beh": "run", "bezim": "run", "behan": "run",
    "veslovani": "row", "anglicak": "row",
}


def detect_intent(text: str, toks: list[str], has_numbers: bool, exercise) -> tuple[str, float]:
    low = f" {normalize(text)} "
    scores: dict[str, float] = {}
    for intent, words in INTENT_WORDS.items():
        hit = 0.0
        for w in words:
            if f" {w} " in low or low.strip().startswith(w + " "):
                hit += 2.0 * max(1, len(w.split()))      # a phrase beats a single keyword
        if hit:
            scores[intent] = hit
    if detect_run_entities(text, toks):
        scores["log_run"] = scores.get("log_run", 0) + 4.0
    if exercise and (has_numbers or re.search(r"\d+\s*x\s*\d+", normalize(text))):
        scores["log_set"] = scores.get("log_set", 0) + 1.5 + (2.0 if not scores else 0.0)
    if not scores:
        if exercise and has_numbers:
            return "log_set", 0.6
        if any(w in toks for w in ("hi", "hello", "ahoj", "cau")):
            return "greet", 0.9
        return "unknown", 0.2
    best = max(scores, key=scores.get)
    total = sum(scores.values())
    return best, round(min(0.99, scores[best] / max(total, 1) + 0.25), 2)


# ------------------------------------------------------------------ entities


@dataclass
class Match:
    kind: str                 # "exercise" | "skill"
    id: str
    name: str
    score: float = 0.0
    extra: dict = field(default_factory=dict)


def _similarity(query: list[str], name: str) -> float:
    """Token overlap plus a typo-tolerant ratio on the joined phrase."""
    target = tokens(name)
    if not query or not target:
        return 0.0
    q, t = " ".join(query), " ".join(target)
    ratio = difflib.SequenceMatcher(None, q, t).ratio()
    overlap = len(set(query) & set(target)) / max(len(set(target)), 1)
    starts = 1.0 if t.startswith(query[0]) else 0.0
    return 0.55 * overlap + 0.35 * ratio + 0.10 * starts


class Vocabulary:
    """Names and aliases of everything the coach can recognise."""

    def __init__(self, wrepo, graph):
        self.exercises: dict[str, dict] = {}
        self.skills: dict[str, dict] = {}
        try:
            for ex in wrepo.exercises():
                self.exercises[ex["id"]] = ex
        except Exception:
            pass
        if graph is not None:
            for sid in graph.order:
                s = graph.skills[sid]
                self.skills[sid] = {
                    "id": sid, "name": s.name, "category": s.category,
                    "desc": getattr(s, "desc", ""), "steps": list(getattr(s, "steps", ()) or ()),
                    "unit": getattr(s, "unit", ""), "target": getattr(s, "target", 0),
                    "prereqs": list(getattr(s, "prereqs", ()) or ()),
                }
        self.aliases = dict(ALIASES)

    def find(self, toks: list[str], kinds=("exercise", "skill")) -> Match | None:
        if not toks:
            return None
        words = [w for w in toks if w not in STOP and not any(c.isdigit() for c in w)]
        if not words:
            return None
        joined = " ".join(words)
        best: Match | None = None
        candidates = []
        for kind in kinds:
            pool = self.exercises if kind == "exercise" else self.skills
            for ident, item in pool.items():
                candidates.append((kind, ident, item))
        # a part of a longer name: "muscle up" -> "Bar Muscle-Up" (+ alternatives)
        subset = [(kind, ident, item) for kind, ident, item in candidates
                  if set(words) <= set(tokens(item["name"]))]
        if subset:
            subset.sort(key=lambda c: len(tokens(c[2]["name"])))
            kind, ident, item = subset[0]
            extra = dict(item)
            if len(subset) > 1:
                extra["also"] = [c[2]["name"] for c in subset[1:4]]
            return Match(kind, ident, item["name"], 0.88, extra=extra)
        # exact alias (only once no full name fits: "wall push up" beats "push up")
        word_set = set(words)
        for phrase, target in self.aliases.items():
            phrase_toks = tokens(phrase)
            if phrase_toks and (set(phrase_toks) <= word_set or " ".join(phrase_toks) == joined):
                hit = self._by_id(target, kinds)
                if hit:
                    hit.score = 1.0
                    return hit
        for kind, ident, item in candidates:
            score = _similarity(words, item["name"])
            if score >= 0.62 and (best is None or score > best.score):
                best = Match(kind, ident, item["name"], score, extra=item)
        # longest matching suffix window: "3x12 wall push ups" -> "wall push up"
        if best is None or best.score < 0.9:
            for kind, ident, item in candidates:
                name_toks = tokens(item["name"])
                for start in range(len(words)):
                    window = words[start:start + len(name_toks)]
                    if len(window) < len(name_toks):
                        break
                    if window == name_toks:
                        return Match(kind, ident, item["name"], 1.0, extra=item)
        return best

    def _by_id(self, ident: str, kinds) -> Match | None:
        for kind in kinds:
            pool = self.exercises if kind == "exercise" else self.skills
            if ident in pool:
                return Match(kind, ident, pool[ident]["name"], 1.0, extra=pool[ident])
        # alias may point at a family prefix, e.g. "pushup" -> "pushup"
        return None

    def suggest_names(self, toks: list[str], limit=3) -> list[str]:
        words = [w for w in toks if w not in STOP and not any(c.isdigit() for c in w)]
        scored = []
        for pool in (self.exercises, self.skills):
            for item in pool.values():
                scored.append((_similarity(words, item["name"]), item["name"]))
        scored.sort(reverse=True)
        return [name for score, name in scored[:limit] if score > 0.3]


GREETINGS = {"hey", "hi", "hello", "yo", "hiya", "sup", "ahoj", "cau", "cus", "nazdar",
             "zdravim", "morning", "heya", "hello!"}

STOP = set("""a an the i im ive me my we you it of on in at to for and or with did do
does done just today yesterday this that these those sets set reps rep times time
plus more again log add record ran run sum total how many was were is are be
what whats how do does can could should would tell about ever so far got get
there their them he she his her our your""".split())


def detect_run_entities(text: str, toks: list[str]):
    """Distance and duration of a run sentence, or None."""
    low = digits_from_words(text)
    dist = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:km|kilomet\w*|k)\b", low)
    if m:
        dist = float(m.group(1)) * 1000
    elif re.search(r"(\d+)\s*(?:m|metr)", low):
        m2 = re.search(r"(\d+)\s*(?:m|metr)", low)
        dist = float(m2.group(1))
    dur = None
    m = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", low)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if m.group(3):
            dur = a * 3600 + b * 60 + int(m.group(3))
        else:
            dur = a * 60 + b
    if dur is None:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(h|hod|hour)", low)
        if m:
            dur = int(float(m.group(1)) * 3600)
        else:
            m = re.search(r"(\d+)\s*(?:min|minut)", low)
            if m:
                dur = int(m.group(1)) * 60
    if dist and dur:
        return dist, dur
    return None


@dataclass
class Action:
    kind: str                      # "set" | "run" | "status"
    exercise_id: str = ""
    exercise_name: str = ""
    skill_id: str = ""
    sets: int = 1
    reps: int = 0
    hold: int = 0
    distance_m: int = 0
    seconds: int = 0
    status: str = ""

    def describe(self) -> str:
        if self.kind == "run":
            return f"{self.distance_m / 1000:.2f} km in {fmt_time(self.seconds)}"
        if self.kind == "status":
            return f"{self.exercise_name} → {self.status}"
        if self.hold:
            return f"{self.sets} x {self.hold} s hold" if self.sets > 1 else f"{self.hold} s hold"
        return f"{self.sets} x {self.reps} reps" if self.sets > 1 else f"{self.reps} reps"


@dataclass
class Reply:
    text: str
    intent: str = "unknown"
    confidence: float = 0.0
    actions: list[Action] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    followups: list[str] = field(default_factory=list)

    @property
    def writes(self) -> bool:
        return bool(self.actions)


def _pick(text: str, options: list[str]) -> str:
    """Deterministic variety: same input always answers the same, different inputs differ."""
    return options[sum(ord(c) for c in (text or "x")) % len(options)]


def fmt_time(sec: int) -> str:
    m, s = divmod(int(max(0, sec)), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# -------------------------------------------------------------------- parsing


def digits_from_words(text: str) -> str:
    """"three sets of eight" -> "3 sets of 8" (English and Czech number words)."""
    out = []
    for tok in normalize(text).split():
        if tok in WORDS and float(WORDS[tok]).is_integer():
            out.append(str(int(WORDS[tok])))
        else:
            out.append(tok)
    return " ".join(out)


def parse_sets_reps(toks: list[str], text: str) -> tuple[int, int, int]:
    """(sets, reps, hold_seconds) — whatever the sentence contains."""
    low = digits_from_words(text)
    sets = reps = hold = 0
    m = re.search(r"(\d+)\s*(?:x|×)\s*(\d+)", low)
    if m:
        sets, reps = int(m.group(1)), int(m.group(2))
    if not reps:
        m = re.search(r"(\d+)\s*(?:sets?|serie|series|sety|setu)?\s*(?:of|po|krat|times|x)?\s*(\d+)", low)
        if m and re.search(r"sets?|serie|sety|krat|x", low):
            sets, reps = int(m.group(1)), int(m.group(2))
    if not reps:
        m = re.search(r"(\d+)\s*(?:reps?|opakovani|opak|krat)", low)
        if m:
            reps = int(m.group(1))
    if not sets and reps:
        sets = 1
    # holds: "1:30", "90 s", "90 sekund", "2 min"
    m = re.search(r"(\d{1,2}):(\d{2})", low)
    if m:
        hold = int(m.group(1)) * 60 + int(m.group(2))
    if not hold:
        m = re.search(r"(\d+)\s*(?:s\b|sec|sekund|seconds?|vterin)", low)
        if m:
            hold = int(m.group(1))
    if not hold:
        m = re.search(r"(\d+)\s*(?:min|minut)", low)
        if m and not detect_run_entities(text, toks):
            hold = int(m.group(1)) * 60
    if hold and not reps:
        reps = 0
    return sets or 1, reps, hold


def parse_window(text: str) -> tuple[str, str]:
    """(start_date_iso, label) for the sentence's time window."""
    low = f" {normalize(text)} "
    today = dt.date.today()
    for key, words in WINDOWS.items():
        if any(f" {w} " in low for w in words):
            if key == "today":
                return today.isoformat(), "today"
            if key == "yesterday":
                d = today - dt.timedelta(days=1)
                return d.isoformat(), "yesterday"
            if key == "week":
                return (today - dt.timedelta(days=today.weekday())).isoformat(), "this week"
            if key == "last_week":
                start = today - dt.timedelta(days=today.weekday() + 7)
                return start.isoformat(), "last week"
            if key == "month":
                return today.replace(day=1).isoformat(), "this month"
            if key == "year":
                return today.replace(month=1, day=1).isoformat(), "this year"
    m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.?", normalize(text))
    if m:
        try:
            d = dt.date(today.year, int(m.group(2)), int(m.group(1)))
            return d.isoformat(), d.strftime("%d.%m.")
        except ValueError:
            pass
    return "", "all time"


# --------------------------------------------------------------------- coach


class Coach:
    """Answers questions and prepares writes against the local database."""

    def __init__(self, store, wrepo=None, sess=None, srepo=None, ranks=None, xp=None, graph=None):
        self.store, self.wrepo, self.sess = store, wrepo, sess
        self.srepo, self.ranks, self.xp, self.graph = srepo, ranks, xp, graph
        self.vocab = Vocabulary(wrepo, graph) if wrepo is not None else None
        self.last_action: Action | None = None
        self.history: list[Action] = []

    # ------------------------------------------------------------- public
    def handle(self, text: str) -> Reply:
        text = (text or "").strip()
        if not text:
            return Reply("Say something like “did 3x12 push ups” or “sum of reps this week”.",
                         intent="help", confidence=1.0, followups=self.default_followups())
        # "did 3x12 push ups and 3x10 rows" -> two sets in one sentence
        parts = [p.strip() for p in re.split(r"\s*(?:,|;|\+|\band\b|\bthen\b|\ba\b|\bpak\b)\s*", text) if p.strip()]
        if len(parts) > 1:
            singles = [self._single(p) for p in parts]
            actions = [a for r in singles for a in r.actions]
            if len(actions) == len(singles) and all(r.intent in ("log_set", "log_run") for r in singles):
                text_out = "I'll log " + ", ".join(f"{a.exercise_name} {a.describe()}" for a in actions) + "."
                return Reply(text_out, intent=singles[0].intent, confidence=0.85,
                             actions=actions,
                             entities=[a.exercise_name for a in actions],
                             followups=self.default_followups())
        return self._single(text)

    def _single(self, text: str) -> Reply:
        # "hey, what's my best pull up?" -> the greeting is noise, the question is not
        words = normalize(text).split()
        while len(words) > 1 and singular(words[0]) in GREETINGS:
            words.pop(0)
        text = " ".join(words)
        toks = [singular(w) for w in words]
        if len(words) == 1 and singular(words[0]) in GREETINGS:
            reply = self._do_greet(text, toks, None)
            reply.intent, reply.confidence = "greet", 0.97
            return reply
        match = self.vocab.find(toks) if self.vocab else None
        has_numbers = (any(any(c.isdigit() for c in t) for t in toks)
                       or any(number_at(toks, i) is not None for i in range(len(toks))))
        intent, conf = detect_intent(text, toks, has_numbers, match)
        entities = [match.name] if match else []

        handler = getattr(self, f"_do_{intent}", None)
        if handler is None:
            return self._fallback(text, toks, match, conf)
        reply = handler(text, toks, match)
        reply.intent, reply.confidence = intent, conf
        reply.entities = entities + [e for e in reply.entities if e not in entities]
        if not reply.followups:
            reply.followups = self.default_followups()
        return reply

    def apply(self, action: Action) -> str:
        """Perform a prepared action and return a short confirmation line."""
        if action.kind == "run" and self.srepo is not None:
            from run_repo import RunRepo
            RunRepo(self.store).log(action.distance_m, action.seconds)
        elif action.kind == "set":
            self._log_performance(action)
        elif action.kind == "status":
            self.store.set_status(action.skill_id or action.exercise_id, action.status or None)
        if self.xp is not None:
            try:
                self.xp.sync()
            except Exception:
                pass
        self.last_action = action
        return f"Logged {action.exercise_name or 'run'}: {action.describe()}."

    # ------------------------------------------------------------ handlers
    def _do_log_run(self, text, toks, match):
        run = detect_run_entities(text, toks)
        if not run:
            return Reply("Tell me the distance and time — e.g. “ran 5 km in 26:30”.",
                         followups=["ran 5 km in 26:30", "ran 3k in 18 min"])
        dist, dur = run
        a = Action(kind="run", distance_m=int(dist), seconds=int(dur), exercise_name="Run")
        return Reply(f"I'll log a run of {a.describe()} (pace {self._pace(a)}).",
                     actions=[a], entities=["Run"])

    def _do_log_set(self, text, toks, match):
        if match is None:
            guess = self.vocab.suggest_names(toks) if self.vocab else []
            hint = f" Did you mean {', '.join(guess)}?" if guess else ""
            return Reply(f"I couldn't tell which exercise that is.{hint}",
                         followups=guess[:2] or ["did 3x12 push ups"])
        sets, reps, hold = parse_sets_reps(toks, text)
        if not reps and not hold:
            default = (match.extra or {}).get("default_amount") or 0
            units = (match.extra or {}).get("unit") or ""
            if default:
                reps = 0 if units.lower().startswith("s") else int(default)
                hold = int(default) if units.lower().startswith("s") else 0
            else:
                return Reply(f"How many {match.name}? e.g. “{match.name} 3x10”.",
                             entities=[match.name], followups=[f"{match.name} 3x10"])
        kind = "hold" if hold and not reps else "reps"
        a = Action(kind="set", exercise_id=match.id, exercise_name=match.name,
                   skill_id=(match.extra or {}).get("skill_id") or (match.id if match.kind == "skill" else ""),
                   sets=sets, reps=reps, hold=hold)
        best = self._best_for(match.id) if match.kind == "exercise" else self.store.best(match.id)
        extra = ""
        if best:
            better = (hold or reps) > best
            extra = f" (previous best {int(best)}{' s' if kind == 'hold' else ' reps'}" \
                    f"{' — new PR!' if better else ''})"
        return Reply(f"I'll log {match.name} — {a.describe()}.{extra}",
                     actions=[a], entities=[match.name])

    def _do_query_total(self, text, toks, match):
        since, label = parse_window(text)
        reps, holds, sets = self._totals(since, match.id if match else None,
                                         match.kind if match else None)
        if not (reps or holds or sets):
            return Reply(f"No logged sets for {label}.", entities=[match.name] if match else [])
        bits = []
        if reps:
            bits.append(f"{reps:,} reps")
        if holds:
            bits.append(f"{fmt_time(holds)} of holds")
        if sets:
            bits.append(f"{sets} sets")
        subject = f" for {match.name}" if match else ""
        text_out = f"{' + '.join(bits)} logged{subject} — {label}."
        if self.sess is not None:
            sessions = self._session_count(since)
            if sessions:
                text_out += f" That's {sessions} workout{'s' if sessions != 1 else ''}."
        return Reply(text_out, entities=[match.name] if match else [])

    def _do_query_best(self, text, toks, match):
        if match is None:
            top = self._top_records(5)
            if not top:
                return Reply("No records logged yet. Try “did 3x12 push ups”.")
            lines = ", ".join(f"{n} {int(v)}{' s' if self._is_hold(n) else ''}" for n, v in top)
            return Reply(f"Your bests: {lines}.")
        if match.kind == "skill":
            best = self.store.best(match.id)
        else:
            best = self._best_for(match.id)
        if not best:
            return Reply(f"No record for {match.name} yet.", entities=[match.name],
                         followups=[f"{match.name} 3x10"])
        goal = (match.extra or {}).get("target") or 0
        tail = f" Target is {int(goal)}." if goal else ""
        return Reply(f"Your best {match.name} is {int(best)}"
                     f"{' s' if self._is_hold(match.name) else ' reps'}.{tail}",
                     entities=[match.name])

    def _do_query_streak(self, text, toks, match):
        import stats
        dates = [dt.date.fromisoformat(r[0]) for r in self.store.db.execute(
            "SELECT session_date FROM sessions WHERE status='completed'")]
        n = stats.streak(dates, dt.date.today())
        wk = stats.this_week(dates, dt.date.today())
        if not n:
            return Reply(f"No training day in a row right now — {wk} workout(s) this week. "
                         f"One session today restarts the streak.")
        return Reply(f"🔥 {n} day{'s' if n != 1 else ''} in a row, {wk} workout(s) this week.")

    def _do_query_progress(self, text, toks, match):
        level = self.xp.level() if self.xp is not None else None
        done = int(self.store.db.execute(
            "SELECT COUNT(*) FROM progress WHERE status='completed'").fetchone()[0])
        total = len(self.graph.skills) if self.graph else done
        bits = [f"{done}/{total} skills completed"]
        if level is not None:
            bits.insert(0, f"Level {level.level} · {level.title} · {level.total} XP")
        return Reply(" · ".join(bits) + ".")

    def _do_suggest(self, text, toks, match):
        progress = self.store.progress()
        picks = []
        if self.graph is not None:
            for sid in self.graph.order:
                st = self.graph.status(sid, progress)
                if st == "training":
                    picks.append((0, sid))
                elif st == "available" and sid not in {p for _, p in picks}:
                    picks.append((1, sid))
        picks.sort(key=lambda p: (p[0], self.graph.depth[p[1]]))
        names = [self.graph.skills[sid].name for _, sid in picks[:3]]
        if not names:
            return Reply("Everything in the tree is locked or done — nice. Try a free workout?")
        streak = self._streak()
        lead = f"{streak} days in a row — " if streak else ""
        return Reply(f"{lead}next up in the tree: {', '.join(names)}. "
                     f"A session of 3 x 5–8 reps each is a solid start.",
                     entities=names[:2], followups=[f"did 3x6 {names[0]}", "sum of reps this week"])

    def _do_explain(self, text, toks, match):
        if match is None:
            return self._fallback(text, toks, match, 0.3)
        info = match.extra or {}
        if match.kind == "skill":
            desc = info.get("desc") or ""
            steps = info.get("steps") or []
            body = desc
            if steps:
                body += "\n\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps[:4]))
            return Reply(body or f"{match.name} is a skill in the tree.", entities=[match.name])
        how = info.get("instructions") or ""
        cat = info.get("category", "")
        also = info.get("also") or []
        tail = f"\n\nAlso in the tree: {', '.join(also)}." if also else ""
        return Reply(f"{match.name} ({cat}, difficulty {int(info.get('difficulty', 0)) + 1}/4). {how}{tail}",
                     entities=[match.name])

    def _do_list_workouts(self, text, toks, match):
        if self.wrepo is None:
            return Reply("Workout list is unavailable.")
        ws = self.wrepo.workouts()
        if not ws:
            return Reply("No workouts saved yet — build one on the Workout Builder page.")
        names = ", ".join(f"{w['name']} ({len(w.get('entries', []))} exercises)" for w in ws[:6])
        return Reply(f"Your workouts: {names}.")

    def _do_followup(self, text, toks, match):
        """“and 10 more”, “same again”, “20 reps” right after a set."""
        last = self.last_action
        if last is None:
            return self._fallback(text, toks, match, 0.3)
        nums = [int(n) for n in re.findall(r"\d+", normalize(text))]
        if last.kind == "run":
            if len(nums) >= 2:
                a = Action(kind="run", distance_m=int(nums[0] * (1000 if nums[0] < 100 else 1)),
                           seconds=int(nums[1] * 60 if nums[1] < 100 else nums[1]), exercise_name="Run")
                return Reply(f"Another run: {a.describe()}.", actions=[a], entities=["Run"])
            return Reply("How far and how long? e.g. “again 5k in 25:00”.")
        amount = nums[-1] if nums else (last.hold or last.reps)
        sets = nums[0] if len(nums) >= 2 else last.sets
        a = Action(kind="set", exercise_id=last.exercise_id, exercise_name=last.exercise_name,
                   skill_id=last.skill_id, sets=max(1, sets),
                   reps=0 if last.hold else amount, hold=amount if last.hold else 0)
        return Reply(f"Again: {last.exercise_name} — {a.describe()}.", actions=[a],
                     entities=[last.exercise_name])

    def _do_correct(self, text, toks, match):
        """“no, 15 reps” / “actually I did 8” — undo the last entry and log the right one."""
        last = self.last_action
        if last is None or last.kind != "set":
            return Reply("Nothing to correct yet — log a set first.")
        nums = [int(n) for n in re.findall(r"\d+", normalize(text))]
        if not nums:
            return Reply("What's the right number? e.g. “no, 15 reps”.")
        amount = nums[-1]
        sets = nums[0] if len(nums) >= 2 else last.sets
        undone = self._undo_last()
        a = Action(kind="set", exercise_id=last.exercise_id, exercise_name=last.exercise_name,
                   skill_id=last.skill_id, sets=max(1, sets),
                   reps=0 if last.hold else amount, hold=amount if last.hold else 0)
        return Reply(f"Fixed: removed the {last.describe()} entry, logging {a.describe()} instead.",
                     actions=[a], entities=[last.exercise_name])

    def _do_undo(self, text, toks, match):
        if self._undo_last():
            return Reply("Removed the last entry I logged.")
        return Reply("There's nothing of mine to undo.")

    def _do_level(self, text, toks, match):
        if self.xp is None:
            return Reply("Level data is unavailable.")
        level = self.xp.level()
        if level.need <= 0:
            return Reply("You're at the top level already.")
        left = level.need - level.into
        if level.next_title:
            return Reply(f"Level {level.level} · {level.title}: {level.into}/{level.need} XP, "
                         f"{left} XP to go for {level.next_title} (level {level.next_title_level}). "
                         f"One qualifying workout is worth about 25 XP.")
        return Reply(f"Level {level.level} · {level.title}: {level.into}/{level.need} XP, "
                     f"{left} to the next level. One qualifying workout is worth about 25 XP.")

    def _do_compare(self, text, toks, match):
        import datetime as _dt
        today = _dt.date.today()
        monday = today - _dt.timedelta(days=today.weekday())
        prev = monday - _dt.timedelta(days=7)
        def count(start, end):
            return self.store.db.execute(
                "SELECT COUNT(*), COALESCE(SUM(elapsed_sec),0) FROM sessions WHERE status='completed' "
                "AND session_date>=? AND session_date<?", (start.isoformat(), end.isoformat())).fetchone()
        (this_n, this_s), (last_n, last_s) = count(monday, today + _dt.timedelta(days=1)), count(prev, monday)
        delta = this_n - last_n
        trend = "same as" if delta == 0 else (f"{abs(delta)} more than" if delta > 0 else f"{abs(delta)} fewer than")
        return Reply(f"This week: {this_n} workouts ({this_s // 60} min) — {trend} last week "
                     f"({last_n} workouts, {last_s // 60} min).")

    def _do_plan(self, text, toks, match):
        """Suggest a small workout from the library, filtered by a category if named."""
        cat = next((c for c in ("push", "pull", "core", "legs", "static", "balance",
                                "skill", "explosive") if f" {c} " in f" {normalize(text)} "), None)
        if self.vocab is None:
            return Reply("The exercise library is unavailable.")
        pool = [e for e in self.vocab.exercises.values()
                if (cat is None or e["category"] == cat) and int(e.get("difficulty", 0)) <= 1]
        pool.sort(key=lambda e: (e["category"], e["name"]))
        if not pool:
            return Reply(f"No beginner exercises for {cat} in the library.")
        picks = pool[:3]
        lines = "\n".join(f"• {e['name']} — {e['default_sets']} x {e['default_amount']}"
                          f"{' s' if e['kind'] == 'hold' else ' reps'}" for e in picks)
        label = f"{cat.capitalize()} starter" if cat else "Full-body starter"
        return Reply(f"{label}:\n{lines}\nRest {picks[0]['default_rest']} s between sets. "
                     f"Log it with “did 3x8 {picks[0]['name'].lower()}”.",
                     entities=[e["name"] for e in picks])

    def _do_help(self, text, toks, match):
        return Reply(
            "I read your training notes locally — no model, no network.\n"
            "• “did 3x12 push ups”, “plank 1:30”, “ran 5k in 26:30” — log it\n"
            "• “sum of reps this week”, “how many pull ups in total”\n"
            "• “what's my best pull up?”, “how am i doing?”\n"
            "• “what should I train today?”, “what is a muscle up?”",
            followups=self.default_followups())

    def _do_greet(self, text, toks, match):
        level = self.xp.level() if self.xp is not None else None
        who = f"Level {level.level} {level.title}" if level is not None else "Ready"
        streak = self._streak()
        today = "already trained today" if self._trained_today() else "no session logged today yet"
        options = [
            f"Hey. {who} · {today}. What are we doing?",
            f"Hi! {who}, {streak} day{'s' if streak != 1 else ''} in a row, {today}.",
            f"Yo. {today.capitalize()}. Log a set, ask for a total, or ask what's next.",
        ]
        pick = sum(ord(c) for c in text) % len(options)
        return Reply(options[pick], followups=self.default_followups())

    def _do_mood(self, text, toks, match):
        streak = self._streak()
        mood = (_pick(text, ["Running fine — no cloud, no model, just your log.",
                             "All systems local. How about you?",
                             "Good. Everything I know is in your own database."]))
        tail = f" You're on a {streak}-day streak." if streak else ""
        return Reply(mood + tail, followups=self.default_followups())

    def _do_thanks(self, text, toks, match):
        return Reply(_pick(text, ["Anytime.", "You got it.", "That's what I'm here for."]),
                     followups=self.default_followups())

    def _do_bye(self, text, toks, match):
        return Reply(_pick(text, ["See you next session.", "Rest up. See you soon."]))

    def _do_identity(self, text, toks, match):
        return Reply("A rule engine, not a model: I match names, numbers and keywords against "
                     "your own database, on this machine. No network, nothing sent anywhere.",
                     followups=["what can you do?", "how am i doing?"])

    def _do_trained_today(self, text, toks, match):
        rows = self.store.db.execute(
            "SELECT workout_name, elapsed_sec FROM sessions WHERE status='completed' "
            "AND session_date=date('now','localtime') ORDER BY id DESC").fetchall()
        if not rows:
            return Reply("Not yet today. " + (_pick(text, ["Want to log something?",
                                                          "One set counts."])))
        names = ", ".join(sorted({r[0] for r in rows}))
        mins = sum(int(r[1] or 0) for r in rows) // 60
        return Reply(f"Yes — {len(rows)} session{'s' if len(rows) != 1 else ''} today "
                     f"({names}), about {mins} min. Good work.")

    def _do_last_session(self, text, toks, match):
        row = self.store.db.execute(
            "SELECT id, workout_name, session_date, elapsed_sec, distance_m FROM sessions "
            "WHERE status='completed' ORDER BY started DESC LIMIT 1").fetchone()
        if not row:
            return Reply("No finished session yet — the History page will fill up as you train.")
        sid, name, day, secs, dist = row
        sets = self.store.db.execute(
            "SELECT COUNT(*), COALESCE(SUM(CASE WHEN kind='reps' THEN reps ELSE 0 END),0) "
            "FROM session_sets WHERE session_id=? AND done=1", (sid,)).fetchone()
        if dist:
            return Reply(f"Last one: a {dist / 1000:.2f} km run on {day} in {fmt_time(secs)}.")
        names = [r[0] for r in self.store.db.execute(
            "SELECT exercise_name FROM session_sets WHERE session_id=? AND done=1 "
            "GROUP BY exercise_name ORDER BY MIN(ex_pos) LIMIT 4", (sid,))]
        body = ", ".join(names) if names else "no sets ticked"
        return Reply(f"Last one: {name} on {day} — {sets[0]} sets ({body}), {sets[1]} reps, "
                     f"{fmt_time(secs)}.")

    # ------------------------------------------------------------ helpers
    def _fallback(self, text, toks, match, conf):
        guess = self.vocab.suggest_names(toks) if self.vocab else []
        if guess:
            return Reply(f"I'm not sure what you want with {', '.join(guess[:2])}. "
                         f"Try “did 3x10 {guess[0].lower()}” or “what's my best {guess[0].lower()}?”.",
                         confidence=conf, followups=[f"did 3x10 {guess[0]}", "help"])
        return Reply("I didn't catch that. I understand sets (“3x12 push ups”), holds "
                     "(“plank 1:30”), runs (“ran 5k in 26:30”), totals, bests and “what next?”.",
                     confidence=conf, followups=self.default_followups())

    def default_followups(self):
        streak = self._streak()
        out = ["sum of reps this week", "what's my best pull up?"]
        if streak:
            out.insert(0, "how am i doing?")
        return out[:3]

    def _trained_today(self) -> bool:
        row = self.store.db.execute(
            "SELECT 1 FROM sessions WHERE status='completed' "
            "AND session_date=date('now','localtime') LIMIT 1").fetchone()
        return bool(row)

    def _streak(self):
        import stats
        dates = [dt.date.fromisoformat(r[0]) for r in self.store.db.execute(
            "SELECT session_date FROM sessions WHERE status='completed'")]
        return stats.streak(dates, dt.date.today())

    def _session_count(self, since: str) -> int:
        sql = "SELECT COUNT(*) FROM sessions WHERE status='completed'"
        params: tuple = ()
        if since:
            sql += " AND session_date>=?"
            params = (since,)
        return int(self.store.db.execute(sql, params).fetchone()[0])

    def _totals(self, since: str, ident: str | None, kind: str | None):
        reps = holds = sets = 0
        sql = """SELECT COALESCE(SUM(CASE WHEN ss.kind='reps' THEN ss.reps ELSE 0 END),0),
                        COALESCE(SUM(CASE WHEN ss.kind='hold' THEN ss.hold ELSE 0 END),0),
                        COUNT(*)
                 FROM session_sets ss JOIN sessions s ON s.id=ss.session_id
                 WHERE s.status='completed' AND ss.done=1"""
        params: list = []
        if since:
            sql += " AND s.session_date>=?"
            params.append(since)
        if ident:
            if kind == "skill":
                sql += """ AND ss.exercise_id IN (SELECT id FROM exercises WHERE skill_id=?)"""
            else:
                sql += " AND ss.exercise_id=?"
            params.append(ident)
        row = self.store.db.execute(sql, tuple(params)).fetchone()
        if row:
            reps, holds, sets = int(row[0]), int(row[1]), int(row[2])
        return reps, holds, sets

    def _best_for(self, exercise_id: str):
        rows = [v for v in self._performances(exercise_id)]
        row = self.store.db.execute(
            "SELECT MAX(value) FROM performances WHERE exercise_id=?", (exercise_id,)).fetchone()
        if row and row[0] is not None:
            rows.append(float(row[0]))
        sets = self.store.db.execute(
            """SELECT MAX(CASE WHEN kind='reps' THEN reps ELSE hold END)
               FROM session_sets ss JOIN sessions s ON s.id=ss.session_id
               WHERE ss.exercise_id=? AND ss.done=1 AND s.status='completed'""",
            (exercise_id,)).fetchone()
        if sets and sets[0] is not None:
            rows.append(float(sets[0]))
        return max(rows) if rows else None

    def _performances(self, exercise_id: str):
        return [float(r[0]) for r in self.store.db.execute(
            "SELECT value FROM performances WHERE exercise_id=?", (exercise_id,))]

    def _top_records(self, limit=5):
        rows = self.store.db.execute(
            "SELECT skill_id, MAX(value) AS v FROM records GROUP BY skill_id ORDER BY v DESC LIMIT ?",
            (limit,)).fetchall()
        names = []
        for sid, val in rows:
            name = self.graph.skills[sid].name if self.graph and sid in self.graph.skills else sid
            names.append((name, val))
        return names

    def _is_hold(self, name: str) -> bool:
        low = (name or "").lower()
        return any(w in low for w in ("plank", "hold", "hang", "lever", "handstand",
                                      "l-sit", "lsit", "flag", "support", "prkno"))

    def _log_performance(self, a: Action) -> None:
        """Write the set into today's log: performances, skill record and the session it belongs to."""
        value = float(a.hold or a.reps)
        ts = dt.date.today().isoformat()
        db = self.store.db
        if a.exercise_id:
            db.execute("INSERT INTO performances(exercise_id,value,logged,source,note) "
                       "VALUES(?,?,?,'coach',?)", (a.exercise_id, value, ts, a.describe()))
        if a.skill_id:
            db.execute("INSERT INTO records(skill_id,value,logged) VALUES(?,?,?)",
                       (a.skill_id, value, ts))
        sid = self._coach_session(ts)
        if a.exercise_id:
            pos = db.execute("SELECT COALESCE(MAX(ex_pos),-1)+1 FROM session_sets WHERE session_id=?",
                             (sid,)).fetchone()[0]
            kind = "hold" if a.hold and not a.reps else "reps"
            for i in range(max(1, a.sets)):
                db.execute(
                    "INSERT INTO session_sets(session_id,ex_pos,set_idx,exercise_id,exercise_name,kind,"
                    "target_reps,target_hold,reps,hold,rest_sec,done,done_at,confirmed)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?,0,1,datetime('now','localtime'),1)",
                    (sid, pos, i, a.exercise_id, a.exercise_name or a.exercise_id, kind,
                     a.reps, a.hold, a.reps, a.hold))
        db.commit()

    def _undo_last(self) -> bool:
        """Delete the newest row the coach itself wrote (set, record, performance)."""
        db = self.store.db
        last = self.last_action
        if last is None:
            return False
        if last.kind == "run":
            row = db.execute("SELECT id FROM sessions WHERE workout_name='Run' AND status='completed' "
                             "ORDER BY id DESC LIMIT 1").fetchone()
            if row:
                db.execute("DELETE FROM sessions WHERE id=?", (row[0],))
                db.commit()
                return True
            return False
        sid_row = db.execute("SELECT id FROM sessions WHERE workout_name='Coach log' "
                             "ORDER BY id DESC LIMIT 1").fetchone()
        if sid_row:
            db.execute("DELETE FROM session_sets WHERE id=(SELECT MAX(id) FROM session_sets "
                       "WHERE session_id=?)", (sid_row[0],))
        db.execute("DELETE FROM performances WHERE id=(SELECT MAX(id) FROM performances WHERE source='coach')")
        db.execute("DELETE FROM records WHERE id=(SELECT MAX(id) FROM records)")
        db.commit()
        self.last_action = None
        return True

    def _coach_session(self, day: str) -> int:
        """One 'Coach log' session per day, so the sets show up in History and in the totals."""
        db = self.store.db
        row = db.execute("SELECT id FROM sessions WHERE workout_name='Coach log' AND session_date=? "
                         "ORDER BY id DESC LIMIT 1", (day,)).fetchone()
        if row:
            return int(row[0])
        cur = db.execute(
            "INSERT INTO sessions(workout_id,workout_name,session_date,started,ended,status,"
            "elapsed_sec,state_json,entry_id) VALUES(NULL,'Coach log',?,?,?,'completed',0,'{}',NULL)",
            (day, day + "T00:00:00", day + "T00:00:00"))
        return int(cur.lastrowid)

    def _pace(self, a: Action) -> str:
        if not a.distance_m or not a.seconds:
            return "–"
        sec = a.seconds * 1000.0 / a.distance_m
        return f"{int(sec) // 60}:{int(sec) % 60:02d} /km"
