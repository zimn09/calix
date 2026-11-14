//! CALIX Coach: a local, rule-based assistant. No model, no network.
//!
//! Reads training notes the way a coach skims them: the exercise you mean
//! (fuzzy, typo and slang tolerant), the numbers around it, the intent of the
//! sentence and the time window, then either answers from the database or
//! prepares a change for you to confirm.
//!
//!     did 3x12 push ups     -> log 3 sets x 12 reps of Push-Up
//!     plank 1:30            -> log a 90 s hold
//!     ran 5k in 26:30       -> log a 5 km run
//!     sum of reps this week -> answer from session_sets
//!     what's my best pull up? / what should I train today? / hey
use crate::data::{data, Data};
use crate::db;
use crate::logic;
use rusqlite::{params, Connection};
use std::collections::HashSet;

// ------------------------------------------------------------------- text

fn strip_diacritics(c: char) -> char {
    match c {
        'á' | 'à' | 'ä' | 'â' | 'ã' => 'a',
        'č' | 'ç' => 'c',
        'ď' => 'd',
        'é' | 'è' | 'ě' | 'ê' | 'ë' => 'e',
        'í' | 'ì' | 'î' | 'ï' | 'ý' => 'i',
        'ľ' | 'ĺ' => 'l',
        'ň' | 'ñ' => 'n',
        'ó' | 'ò' | 'ô' | 'ö' | 'õ' => 'o',
        'ř' => 'r',
        'š' => 's',
        'ť' => 't',
        'ú' | 'ů' | 'ù' | 'û' | 'ü' => 'u',
        'ž' => 'z',
        other => other,
    }
}

pub fn normalize(text: &str) -> String {
    let lowered: String = text
        .to_lowercase()
        .chars()
        .map(strip_diacritics)
        .map(|c| if c.is_alphanumeric() || c == ':' || c == '.' { c } else { ' ' })
        .collect();
    lowered
        .split_whitespace()
        .map(|w| w.trim_matches('.'))
        .filter(|w| !w.is_empty())
        .collect::<Vec<_>>()
        .join(" ")
}

pub fn singular(word: &str) -> String {
    if word.len() > 3 && word.ends_with("ies") {
        format!("{}y", &word[..word.len() - 3])
    } else if word.len() > 2 && word.ends_with('s') && !word.ends_with("ss") {
        word[..word.len() - 1].to_string()
    } else {
        word.to_string()
    }
}

pub fn tokens(text: &str) -> Vec<String> {
    normalize(text)
        .split_whitespace()
        .map(|w| singular(w.trim_matches(|c: char| c == '.' || c == ':' )))
        .filter(|w| !w.is_empty())
        .collect()
}

fn number_words() -> &'static [(&'static str, i64)] {
    &[
        ("zero", 0), ("one", 1), ("two", 2), ("three", 3), ("four", 4), ("five", 5),
        ("six", 6), ("seven", 7), ("eight", 8), ("nine", 9), ("ten", 10),
        ("eleven", 11), ("twelve", 12), ("fifteen", 15), ("twenty", 20),
        ("thirty", 30), ("forty", 40), ("fifty", 50), ("a", 1),
        ("jedna", 1), ("jeden", 1), ("dva", 2), ("dve", 2), ("tri", 3), ("ctyri", 4),
        ("pet", 5), ("sest", 6), ("sedm", 7), ("osm", 8), ("devet", 9), ("deset", 10),
        ("dvanact", 12), ("patnact", 15), ("dvacet", 20), ("tricet", 30),
    ]
}

fn as_number(tok: &str) -> Option<i64> {
    if let Ok(n) = tok.parse::<i64>() {
        return Some(n);
    }
    number_words().iter().find(|(w, _)| *w == tok).map(|(_, n)| *n)
}

fn digits_from_words(text: &str) -> Vec<String> {
    normalize(text)
        .split_whitespace()
        .map(|w| match as_number(w) {
            Some(n) => n.to_string(),
            None => w.to_string(),
        })
        .collect()
}

fn begins(tok: &str, stems: &[&str]) -> bool {
    stems.iter().any(|s| tok.starts_with(s))
}

// ----------------------------------------------------------------- intents

const GREETINGS: &[&str] = &[
    "hey", "hi", "hello", "yo", "hiya", "sup", "ahoj", "cau", "cus", "nazdar",
    "zdravim", "morning", "heya",
];

const STOP: &[&str] = &[
    "a", "an", "the", "i", "im", "ive", "me", "my", "we", "you", "it", "of", "on",
    "in", "at", "to", "for", "and", "or", "with", "did", "do", "does", "done",
    "just", "today", "yesterday", "this", "that", "these", "those", "set", "sets",
    "rep", "reps", "times", "time", "plus", "more", "again", "log", "add", "record",
    "ran", "run", "sum", "total", "how", "many", "was", "were", "is", "are", "be",
    "what", "whats", "can", "could", "should", "would", "tell", "about", "ever",
    "so", "far", "got", "get", "there", "their", "them", "he", "she", "his", "her",
    "our", "your", "am", "have", "has",
];

pub fn detect_run(text: &str) -> Option<(i64, i64)> {
    let toks = digits_from_words(text);
    let mut dist = None;
    let mut dur = None;
    let mut i = 0;
    while i < toks.len() {
        let tok = &toks[i];
        if let Some(colon) = tok.find(':') {
            let left: i64 = tok[..colon].parse().ok()?;
            let right: i64 = tok[colon + 1..].parse().ok()?;
            dur = Some(left * 60 + right);
            i += 1;
            continue;
        }
        // "5k", "3.2km", "18min" written as one token
        let split = tok.find(|c: char| !c.is_ascii_digit() && c != '.').unwrap_or(tok.len());
        if split > 0 && split < tok.len() {
            let num: f64 = tok[..split].parse().unwrap_or(-1.0);
            let suffix = &tok[split..];
            if suffix.starts_with("km") || suffix == "k" {
                if num > 0.0 {
                    dist = Some((num * 1000.0) as i64);
                }
            } else if suffix.starts_with("kilomet") {
                dist = Some((num * 1000.0) as i64);
            } else if suffix.starts_with("min") {
                dur = Some(dur.unwrap_or(0) + (num as i64) * 60);
            } else if suffix.starts_with("hod") || suffix == "h" {
                dur = Some(dur.unwrap_or(0) + (num as i64) * 3600);
            } else if suffix == "m" || suffix.starts_with("metr") {
                dist = Some(num as i64);
            }
        }
        if let Some(n) = tok.parse::<f64>().ok() {
            if let Some(next) = toks.get(i + 1) {
                if begins(next, &["km", "kilomet"]) {
                    dist = Some((n * 1000.0) as i64);
                } else if next == "k" {
                    dist = Some((n * 1000.0) as i64);
                } else if begins(next, &["metr"]) || next == "m" {
                    dist = Some(n as i64);
                } else if begins(next, &["min"]) {
                    dur = Some(dur.unwrap_or(0) + (n as i64) * 60);
                } else if begins(next, &["hod"]) || next == "h" {
                    dur = Some(dur.unwrap_or(0) + (n as i64) * 3600);
                } else if begins(next, &["s"]) && next.len() <= 6 {
                    dur = None;
                }
            }
        }
        i += 1;
    }
    match (dist, dur) {
        (Some(d), Some(s)) if d > 0 && s > 0 => Some((d, s)),
        _ => None,
    }
}

pub fn parse_sets_reps(text: &str) -> (i64, i64, i64) {
    let toks = digits_from_words(text);
    let mut sets = 0;
    let mut reps = 0;
    let mut hold = 0;
    let mut i = 0;
    while i < toks.len() {
        let tok = &toks[i];
        if let Some(colon) = tok.find(':') {
            if let (Ok(m), Ok(s)) = (tok[..colon].parse::<i64>(), tok[colon + 1..].parse::<i64>()) {
                hold = m * 60 + s;
            }
            i += 1;
            continue;
        }
        // "3x12" written as one token
        if let Some((left, right)) = tok.split_once('x') {
            if let (Ok(a), Ok(b)) = (left.parse::<i64>(), right.parse::<i64>()) {
                sets = a;
                reps = b;
                i += 1;
                continue;
            }
        }
        let split = tok.find(|c: char| !c.is_ascii_digit()).unwrap_or(tok.len());
        if split > 0 && split < tok.len() {
            if let Ok(n) = tok[..split].parse::<i64>() {
                let suffix = &tok[split..];
                if begins(suffix, &["s", "sec", "sekund", "vterin"]) {
                    hold = n;
                    i += 1;
                    continue;
                }
                if begins(suffix, &["min", "minut"]) && detect_run(text).is_none() {
                    hold = n * 60;
                    i += 1;
                    continue;
                }
            }
        }
        let n: Option<i64> = tok.parse().ok();
        if let Some(n) = n {
            let next = toks.get(i + 1).cloned().unwrap_or_default();
            if next == "x" {
                if let Some(m) = toks.get(i + 2).and_then(|t| t.parse::<i64>().ok()) {
                    sets = n;
                    reps = m;
                    i += 3;
                    continue;
                }
            }
            if begins(&next, &["set", "serie", "sety", "setu"]) {
                let mut j = i + 2;
                if toks.get(j).map(|t| t == "of" || t == "po").unwrap_or(false) {
                    j += 1;
                }
                if let Some(m) = toks.get(j).and_then(|t| t.parse::<i64>().ok()) {
                    sets = n;
                    reps = m;
                    i = j + 1;
                    continue;
                }
            }
            if begins(&next, &["rep", "opak", "krat"]) {
                reps = n;
            } else if begins(&next, &["sec", "sekund", "vterin", "s"]) && next.len() <= 7 {
                hold = n;
            } else if begins(&next, &["min", "minut"]) && detect_run(text).is_none() {
                hold = n * 60;
            }
        }
        i += 1;
    }
    if sets == 0 && (reps > 0 || hold > 0) {
        sets = 1;
    }
    if hold > 0 && reps == 0 {
        sets = sets.max(1);
    }
    (sets.max(1), reps, hold)
}

/// (ISO start date, human label) for the sentence's time window.
pub fn parse_window(text: &str) -> (Option<String>, &'static str) {
    let low = format!(" {} ", normalize(text));
    let today = chrono::Local::now().date_naive();
    let has = |words: &[&str]| words.iter().any(|w| low.contains(&format!(" {w} ")));
    let start = |d: chrono::NaiveDate| d.format("%Y-%m-%d").to_string();
    if has(&["today", "dnes", "tonight"]) {
        return (Some(start(today)), "today");
    }
    if has(&["yesterday", "vcera"]) {
        return (Some(start(today - chrono::Duration::days(1))), "yesterday");
    }
    if has(&["last week", "minuly tyden"]) {
        let monday = today - chrono::Duration::days(today.weekday().num_days_from_monday() as i64 + 7);
        return (Some(start(monday)), "last week");
    }
    if has(&["week", "this week", "tyden", "tento tyden"]) {
        let monday = today - chrono::Duration::days(today.weekday().num_days_from_monday() as i64);
        return (Some(start(monday)), "this week");
    }
    if has(&["month", "this month", "mesic"]) {
        return (Some(start(today.with_day(1).unwrap())), "this month");
    }
    if has(&["year", "this year", "rok"]) {
        return (Some(start(today.with_day(1).unwrap().with_month(1).unwrap())), "this year");
    }
    (None, "all time")
}

use chrono::Datelike;

// ---------------------------------------------------------------- matching

pub struct Hit {
    pub is_skill: bool,
    pub id: String,
    pub name: String,
    pub score: f32,
    pub also: Vec<String>,
}

fn levenshtein(a: &str, b: &str) -> usize {
    let a: Vec<char> = a.chars().collect();
    let b: Vec<char> = b.chars().collect();
    let mut prev: Vec<usize> = (0..=b.len()).collect();
    let mut cur = vec![0; b.len() + 1];
    for i in 1..=a.len() {
        cur[0] = i;
        for j in 1..=b.len() {
            let cost = if a[i - 1] == b[j - 1] { 0 } else { 1 };
            cur[j] = (prev[j] + 1).min(cur[j - 1] + 1).min(prev[j - 1] + cost);
        }
        std::mem::swap(&mut prev, &mut cur);
    }
    prev[b.len()]
}

fn similarity(words: &[String], name: &str) -> f32 {
    let target = tokens(name);
    if words.is_empty() || target.is_empty() {
        return 0.0;
    }
    let wset: HashSet<&String> = words.iter().collect();
    let overlap = target.iter().filter(|t| wset.contains(t)).count() as f32 / target.len() as f32;
    let q = words.join(" ");
    let t = target.join(" ");
    let dist = levenshtein(&q, &t) as f32;
    let ratio = 1.0 - dist / q.len().max(t.len()).max(1) as f32;
    let prefix = if t.starts_with(words[0].as_str()) { 1.0 } else { 0.0 };
    0.55 * overlap + 0.35 * ratio + 0.10 * prefix
}

fn aliases() -> &'static [(&'static str, &'static str)] {
    &[
        ("pushup", "pushup"), ("push up", "pushup"), ("press up", "pushup"),
        ("pullup", "pullup"), ("pull up", "pullup"), ("chin up", "chinup"),
        ("squat", "squat"), ("dip", "dip"), ("row", "row"), ("plank", "plank"),
        ("hollow", "hollow_body"), ("l sit", "l_sit"), ("handstand", "handstand"),
        ("muscle up", "bar_muscle_up"), ("front lever", "front_lever"),
        ("back lever", "back_lever"), ("flag", "human_flag"),
        ("klik", "pushup"), ("kliky", "pushup"), ("shyb", "pullup"),
        ("shyby", "pullup"), ("drep", "squat"), ("drepy", "squat"),
        ("prkno", "plank"), ("stojka", "handstand"), ("anglicak", "row"),
    ]
}

pub fn find(words: &[String], d: &Data) -> Option<Hit> {
    let words: Vec<String> = words
        .iter()
        .filter(|w| !STOP.contains(&w.as_str()) && !w.chars().any(|c| c.is_ascii_digit()))
        .cloned()
        .collect();
    if words.is_empty() {
        return None;
    }
    // a full name made of the query words: "wall push up" beats "push up"
    let mut subset: Vec<(usize, Hit)> = Vec::new();
    for ex in &d.exercises.items {
        let name_toks = tokens(&ex.name);
        if words.iter().all(|w| name_toks.contains(w)) {
            subset.push((name_toks.len(), Hit {
                is_skill: false, id: ex.id.clone(), name: ex.name.clone(), score: 0.9, also: vec![],
            }));
        }
    }
    for sk in &d.skills.items {
        let name_toks = tokens(&sk.name);
        if words.iter().all(|w| name_toks.contains(w)) {
            subset.push((name_toks.len(), Hit {
                is_skill: true, id: sk.id.clone(), name: sk.name.clone(), score: 0.9, also: vec![],
            }));
        }
    }
    if !subset.is_empty() {
        subset.sort_by_key(|(len, _)| *len);
        let (_, mut best) = subset.remove(0);
        best.also = subset.iter().take(3).map(|(_, h)| h.name.clone()).collect();
        return Some(best);
    }
    // slang and Czech names
    let joined = words.join(" ");
    for (phrase, target) in aliases() {
        let phrase_toks = tokens(phrase);
        if phrase_toks.iter().all(|t| words.contains(t)) || joined == *phrase {
            if let Some(ex) = d.exercise(target) {
                return Some(Hit { is_skill: false, id: ex.id.clone(), name: ex.name.clone(), score: 1.0, also: vec![] });
            }
            if let Some(sk) = d.skill(target) {
                return Some(Hit { is_skill: true, id: sk.id.clone(), name: sk.name.clone(), score: 1.0, also: vec![] });
            }
        }
    }
    let mut best: Option<Hit> = None;
    let mut consider = |is_skill: bool, id: &str, name: &str| {
        let score = similarity(&words, name);
        if score >= 0.62 && best.as_ref().map(|b| score > b.score).unwrap_or(true) {
            best = Some(Hit { is_skill, id: id.to_string(), name: name.to_string(), score, also: vec![] });
        }
    };
    for ex in &d.exercises.items {
        consider(false, &ex.id, &ex.name);
    }
    for sk in &d.skills.items {
        consider(true, &sk.id, &sk.name);
    }
    best
}

// ----------------------------------------------------------------- actions

#[derive(Clone)]
pub enum Action {
    Set { exercise_id: String, exercise_name: String, skill_id: Option<String>, sets: i64, reps: i64, hold: i64 },
    Run { distance_m: i64, seconds: i64 },
}

impl Action {
    pub fn describe(&self) -> String {
        match self {
            Action::Run { distance_m, seconds } => {
                format!("{:.2} km in {}", *distance_m as f64 / 1000.0, fmt_time(*seconds))
            }
            Action::Set { sets, reps, hold, .. } => {
                if *hold > 0 {
                    if *sets > 1 { format!("{} x {} s hold", sets, hold) } else { format!("{} s hold", hold) }
                } else if *sets > 1 {
                    format!("{} x {} reps", sets, reps)
                } else {
                    format!("{} reps", reps)
                }
            }
        }
    }

    pub fn label(&self) -> String {
        match self {
            Action::Run { .. } => "Run".to_string(),
            Action::Set { exercise_name, .. } => exercise_name.clone(),
        }
    }
}

pub fn fmt_time(sec: i64) -> String {
    let (h, m, s) = (sec / 3600, (sec % 3600) / 60, sec % 60);
    if h > 0 { format!("{h}:{m:02}:{s:02}") } else { format!("{m}:{s:02}") }
}

pub struct Answer {
    pub text: String,
    pub intent: &'static str,
    pub confidence: f32,
    pub entities: Vec<String>,
    pub actions: Vec<Action>,
    /// the caller should forget its last action (the entry was removed)
    pub undo: bool,
}

impl Answer {
    fn say(text: impl Into<String>) -> Self {
        Answer {
            text: text.into(),
            intent: "unknown",
            confidence: 0.3,
            entities: vec![],
            actions: vec![],
            undo: false,
        }
    }
    fn with(mut self, intent: &'static str, confidence: f32) -> Self {
        self.intent = intent;
        self.confidence = confidence;
        self
    }
}

fn pick<'a>(seed: &str, options: &'a [&'a str]) -> &'a str {
    let sum: usize = seed.chars().map(|c| c as usize).sum();
    options[sum % options.len()]
}

// ------------------------------------------------------------------- brain

pub fn ask(conn: &Connection, text: &str) -> Answer {
    ask_with(conn, text, None)
}

/// Same as [`ask`], but with the previous action for follow-ups and corrections.
pub fn ask_with(conn: &Connection, text: &str, last: Option<&Action>) -> Answer {
    let text = text.trim();
    if text.is_empty() {
        return Answer::say("Say something like “did 3x12 push ups” or “sum of reps this week”.")
            .with("help", 1.0);
    }
    // "did 3x12 push ups and 3x10 rows" -> several sets in one sentence
    let parts: Vec<String> = text
        .split(|c| c == ',' || c == ';' || c == '+')
        .flat_map(|p| p.split(" and ").flat_map(|q| q.split(" then ")).map(|s| s.to_string()))
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();
    if parts.len() > 1 {
        let singles: Vec<Answer> = parts.iter().map(|p| single(conn, p, last)).collect();
        let actions: Vec<Action> = singles.iter().flat_map(|a| a.actions.clone()).collect();
        if !actions.is_empty() && actions.len() == singles.len() {
            let body = actions
                .iter()
                .map(|a| format!("{} {}", a.label(), a.describe()))
                .collect::<Vec<_>>()
                .join(", ");
            return Answer {
                text: format!("I'll log {body}."),
                intent: singles[0].intent,
                confidence: 0.85,
                entities: actions.iter().map(|a| a.label()).collect(),
                actions,
                undo: false,
            };
        }
    }
    single(conn, text, last)
}

fn single(conn: &Connection, text: &str, last: Option<&Action>) -> Answer {
    let d = data();
    // a greeting in front of a real question is noise
    let mut words: Vec<String> = normalize(text).split_whitespace().map(|s| s.to_string()).collect();
    while words.len() > 1 && GREETINGS.contains(&singular(&words[0]).as_str()) {
        words.remove(0);
    }
    let clean = words.join(" ");
    if words.len() == 1 && GREETINGS.contains(&singular(&words[0]).as_str()) {
        return greet(conn, &clean).with("greet", 0.97);
    }

    let toks: Vec<String> = words.iter().map(|w| singular(w)).collect();
    let hit = find(&toks, d);
    let low = format!(" {} ", normalize(&clean));
    let has = |w: &str| low.contains(&format!(" {w} ")) || low.trim_start().starts_with(&format!("{w} "));
    let numbers = toks.iter().any(|t| t.chars().any(|c| c.is_ascii_digit()));

    let mut scores: Vec<(&'static str, f32)> = Vec::new();
    let mut add = |intent: &'static str, words_: &[&str]| {
        let mut weight = 0.0;
        for w in words_ {
            if has(w) {
                weight += 2.0 * w.split_whitespace().count().max(1) as f32;
            }
        }
        if weight > 0.0 {
            scores.push((intent, weight));
        }
    };
    add("greet", GREETINGS);
    add("thanks", &["thanks", "thank you", "thx", "cheers", "diky", "dik"]);
    add("bye", &["bye", "goodbye", "see you", "see ya", "mej se"]);
    add("identity", &["who are you", "what are you", "kdo jsi", "are you an ai", "are you a bot"]);
    add("mood", &["how are you", "hows it going", "jak se mas"]);
    add("help", &["help", "pomoc", "what can you do", "commands", "co umis"]);
    add("trained_today", &["did i train", "have i trained", "trained today", "did i work out", "trenoval jsem"]);
    add("last_session", &["last workout", "last session", "last time", "what did i do", "posledni trenink"]);
    add("suggest", &["should i train", "what next", "recommend", "suggest", "what should", "co trenovat", "advice"]);
    add("explain", &["what is", "what are", "how do i", "explain", "co je", "tell me about", "how to"]);
    add("query_streak", &["streak", "series", "dni v rade"]);
    add("query_progress", &["progress", "level", "xp", "rank", "how am i doing", "pokrok"]);
    add("query_best", &["best", "personal record", "rekord", "nejlepsi", "max"]);
    add("query_total", &["sum", "total", "how many", "kolik", "celkem", "altogether"]);
    add("list_workouts", &["my workouts", "workouts", "treninky"]);
    add("log_run", &["ran", "run", "jog", "beh", "behl", "kilometer"]);
    add("log_set", &["did", "done", "log", "add", "zapsat", "udelal", "splnil"]);
    add("undo", &["undo", "delete that", "delete the last", "smazat", "take that back"]);
    add("correct", &["no", "not", "actually", "meant", "spravne", "oprava"]);
    add("followup", &["and", "more", "again", "same", "stejne", "jeste"]);
    add("level", &["next level", "how much xp", "xp to", "kolik xp"]);
    add("compare", &["vs", "versus", "compare", "last week", "oproti"]);
    add("plan", &["plan", "give me a workout", "workout for", "routine", "sestav", "navrhni"]);

    if detect_run(&clean).is_some() {
        scores.push(("log_run", 8.0));
    }
    if hit.is_some() && numbers {
        scores.push(("log_set", 3.0));
    }
    scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    let (intent, weight) = scores.first().cloned().unwrap_or(("unknown", 0.0));
    let total: f32 = scores.iter().map(|(_, w)| w).sum();
    let confidence = if total > 0.0 { (weight / total + 0.25).min(0.99) } else { 0.2 };

    let mut answer = match intent {
        "greet" => greet(conn, &clean),
        "thanks" => Answer::say(pick(&clean, &["Anytime.", "You got it.", "That's what I'm here for."])),
        "bye" => Answer::say(pick(&clean, &["See you next session.", "Rest up. See you soon."])),
        "identity" => Answer::say(
            "A rule engine, not a model: I match names, numbers and keywords against your own \
             database, on this machine. No network, nothing sent anywhere.",
        ),
        "mood" => {
            let st = db::stats(conn);
            let tail = if st.streak > 0 { format!(" You're on a {}-day streak.", st.streak) } else { String::new() };
            Answer::say(format!(
                "{}{}",
                pick(&clean, &["Running fine — no cloud, no model, just your log.",
                               "All systems local. How about you?",
                               "Good. Everything I know is in your own database."]),
                tail
            ))
        }
        "help" => Answer::say(HELP),
        "trained_today" => trained_today(conn, &clean),
        "last_session" => last_session(conn),
        "suggest" => suggest(conn),
        "explain" => explain(conn, hit.as_ref()),
        "query_streak" => streak_answer(conn),
        "query_progress" => progress_answer(conn),
        "query_best" => best_answer(conn, hit.as_ref()),
        "query_total" => totals_answer(conn, &clean, hit.as_ref()),
        "list_workouts" => list_workouts(conn),
        "log_run" => log_run_answer(&clean),
        "log_set" => log_set_answer(conn, &clean, hit.as_ref()),
        "followup" => followup_answer(&clean, last),
        "correct" => correct_answer(conn, &clean, last),
        "undo" => undo_answer(conn, last),
        "level" => level_answer(conn),
        "compare" => compare_answer(conn),
        "plan" => plan_answer(&clean),
        _ => fallback(&toks),
    };
    answer.intent = intent;
    answer.confidence = confidence;
    if let Some(h) = &hit {
        if !answer.entities.contains(&h.name) {
            answer.entities.insert(0, h.name.clone());
        }
    }
    answer
}

const HELP: &str = "I read your training notes locally — no model, no network.\n\
• “did 3x12 push ups”, “plank 1:30”, “ran 5k in 26:30” — log it\n\
• “sum of reps this week”, “how many pull ups in total”\n\
• “what's my best pull up?”, “how am i doing?”\n\
• “what should I train today?”, “what is a muscle up?”\n\
• “hey”, “did I train today?”, “what did I do last time?”";

fn greet(conn: &Connection, seed: &str) -> Answer {
    let st = db::stats(conn);
    let level = logic::level_info(data(), db::total_xp(conn));
    let trained = conn
        .query_row(
            "SELECT 1 FROM sessions WHERE status='completed' AND session_date=date('now','localtime') LIMIT 1",
            [],
            |_| Ok(()),
        )
        .is_ok();
    let today = if trained { "already trained today" } else { "no session logged today yet" };
    let streak = if st.streak == 1 { "1 day".to_string() } else { format!("{} days", st.streak) };
    let text = pick(seed, &[
        "Hey. Level {level} {title} · {today}. What are we doing?",
        "Hi! {streak} in a row, {today}. Need a total, a record or a plan?",
        "Yo. {today}. Log a set, ask for a total, or ask what's next.",
    ]);
    Answer::say(
        text.replace("{level}", &level.level.to_string())
            .replace("{title}", &level.title)
            .replace("{streak}", &streak)
            .replace("{today}", today),
    )
}

fn trained_today(conn: &Connection, seed: &str) -> Answer {
    let mut stmt = match conn.prepare(
        "SELECT workout_name, elapsed_sec FROM sessions WHERE status='completed' \
         AND session_date=date('now','localtime')") {
        Ok(s) => s,
        Err(_) => return Answer::say("I couldn't read the session log."),
    };
    let rows: Vec<(String, i64)> = stmt
        .query_map([], |r| Ok((r.get(0)?, r.get(1)?)))
        .map(|rows| rows.filter_map(|r| r.ok()).collect())
        .unwrap_or_default();
    if rows.is_empty() {
        return Answer::say(format!("Not yet today. {}", pick(seed, &["Want to log something?", "One set counts."])));
    }
    let names: HashSet<&str> = rows.iter().map(|(n, _)| n.as_str()).collect();
    let mins: i64 = rows.iter().map(|(_, s)| *s).sum::<i64>() / 60;
    Answer::say(format!(
        "Yes — {} session(s) today ({}), about {} min. Good work.",
        rows.len(),
        names.into_iter().collect::<Vec<_>>().join(", "),
        mins
    ))
}

fn last_session(conn: &Connection) -> Answer {
    let row: Option<(i64, String, String, i64, i64)> = conn
        .query_row(
            "SELECT id, workout_name, session_date, elapsed_sec, distance_m FROM sessions \
             WHERE status='completed' ORDER BY started DESC LIMIT 1",
            [],
            |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?, r.get(4)?)),
        )
        .ok();
    let Some((sid, name, day, secs, dist)) = row else {
        return Answer::say("No finished session yet — the History page fills up as you train.");
    };
    if dist > 0 {
        return Answer::say(format!("Last one: a {:.2} km run on {} in {}.", dist as f64 / 1000.0, day, fmt_time(secs)));
    }
    let (sets, reps): (i64, i64) = conn
        .query_row(
            "SELECT COUNT(*), COALESCE(SUM(CASE WHEN kind='reps' THEN reps ELSE 0 END),0) \
             FROM session_sets WHERE session_id=? AND done=1",
            params![sid],
            |r| Ok((r.get(0)?, r.get(1)?)),
        )
        .unwrap_or((0, 0));
    let mut stmt = conn
        .prepare("SELECT exercise_name FROM session_sets WHERE session_id=? AND done=1 GROUP BY exercise_name LIMIT 4")
        .ok();
    let names: Vec<String> = stmt
        .as_mut()
        .and_then(|s| s.query_map(params![sid], |r| r.get::<_, String>(0)).ok())
        .map(|rows| rows.filter_map(|r| r.ok()).collect())
        .unwrap_or_default();
    Answer::say(format!(
        "Last one: {} on {} — {} sets ({}), {} reps, {}.",
        name, day, sets, names.join(", "), reps, fmt_time(secs)
    ))
}

fn streak_answer(conn: &Connection) -> Answer {
    let st = db::stats(conn);
    if st.streak == 0 {
        return Answer::say(format!(
            "No training day in a row right now — {} workout(s) this week. One session today restarts the streak.",
            st.this_week
        ));
    }
    Answer::say(format!("🔥 {} day{} in a row, {} workout(s) this week.",
                        st.streak, if st.streak == 1 { "" } else { "s" }, st.this_week))
}

fn progress_answer(conn: &Connection) -> Answer {
    let level = logic::level_info(data(), db::total_xp(conn));
    let done = db::progress_map(conn).values().filter(|s| s.as_str() == "completed").count();
    Answer::say(format!(
        "Level {} · {} · {} XP · {}/{} skills completed.",
        level.level, level.title, level.total, done, data().skills.items.len()
    ))
}

fn best_answer(conn: &Connection, hit: Option<&Hit>) -> Answer {
    let Some(hit) = hit else {
        let bests = db::bests(conn);
        let mut rows: Vec<(String, f64)> = bests
            .iter()
            .map(|(id, (v, _))| (data().skill(id).map(|s| s.name.clone()).unwrap_or_else(|| id.clone()), *v))
            .collect();
        rows.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        if rows.is_empty() {
            return Answer::say("No records logged yet. Try “did 3x12 push ups”.");
        }
        let list = rows.iter().take(5).map(|(n, v)| format!("{n} {}", *v as i64)).collect::<Vec<_>>().join(", ");
        return Answer::say(format!("Your bests: {list}."));
    };
    let value = if hit.is_skill {
        db::bests(conn).get(&hit.id).map(|(v, _)| *v)
    } else {
        best_for(conn, &hit.id)
    };
    match value {
        Some(v) => {
            let unit = if is_hold(&hit.name) { " s" } else { " reps" };
            Answer::say(format!("Your best {} is {}{}.", hit.name, v as i64, unit))
        }
        None => Answer::say(format!("No record for {} yet.", hit.name)),
    }
}

fn best_for(conn: &Connection, exercise_id: &str) -> Option<f64> {
    let perf: Option<f64> = conn
        .query_row("SELECT MAX(value) FROM performances WHERE exercise_id=?", params![exercise_id], |r| r.get(0))
        .ok();
    let sets: Option<f64> = conn
        .query_row(
            "SELECT MAX(CASE WHEN kind='reps' THEN reps ELSE hold END) FROM session_sets ss \
             JOIN sessions s ON s.id=ss.session_id WHERE ss.exercise_id=? AND ss.done=1 \
             AND s.status='completed'",
            params![exercise_id],
            |r| r.get(0),
        )
        .ok();
    [perf, sets].into_iter().flatten().fold(None, |acc, v| Some(acc.map_or(v, |a: f64| a.max(v))))
}

fn totals_answer(conn: &Connection, text: &str, hit: Option<&Hit>) -> Answer {
    let (since, label) = parse_window(text);
    let mut sql = String::from(
        "SELECT COALESCE(SUM(CASE WHEN ss.kind='reps' THEN ss.reps ELSE 0 END),0), \
                COALESCE(SUM(CASE WHEN ss.kind='hold' THEN ss.hold ELSE 0 END),0), \
                COUNT(*) \
         FROM session_sets ss JOIN sessions s ON s.id=ss.session_id \
         WHERE s.status='completed' AND ss.done=1",
    );
    let mut args: Vec<String> = Vec::new();
    if let Some(since) = &since {
        sql.push_str(" AND s.session_date>=?");
        args.push(since.clone());
    }
    if let Some(h) = hit {
        if h.is_skill {
            sql.push_str(" AND ss.exercise_id IN (SELECT id FROM exercises WHERE skill_id=?)");
        } else {
            sql.push_str(" AND ss.exercise_id=?");
        }
        args.push(h.id.clone());
    }
    let row: Option<(i64, i64, i64)> = conn
        .query_row(&sql, rusqlite::params_from_iter(args.iter()), |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)))
        .ok();
    let Some((reps, hold, sets)) = row else {
        return Answer::say("I couldn't read the session log.");
    };
    if reps == 0 && hold == 0 && sets == 0 {
        return Answer::say(format!("No logged sets for {label}."));
    }
    let mut bits = Vec::new();
    if reps > 0 { bits.push(format!("{reps} reps")); }
    if hold > 0 { bits.push(format!("{} of holds", fmt_time(hold))); }
    if sets > 0 { bits.push(format!("{sets} sets")); }
    let subject = hit.map(|h| format!(" for {}", h.name)).unwrap_or_default();
    Answer::say(format!("{} logged{} — {}.", bits.join(" + "), subject, label))
}

fn explain(conn: &Connection, hit: Option<&Hit>) -> Answer {
    let _ = conn;
    let d = data();
    let Some(hit) = hit else {
        return Answer::say("Which movement? Try “what is a muscle up?” or “what is an l-sit?”.");
    };
    if hit.is_skill {
        if let Some(sk) = d.skill(&hit.id) {
            let mut body = sk.description.clone();
            for (i, step) in sk.steps.iter().take(4).enumerate() {
                body.push_str(&format!("\n{}. {}", i + 1, step));
            }
            if !hit.also.is_empty() {
                body.push_str(&format!("\n\nAlso in the tree: {}.", hit.also.join(", ")));
            }
            return Answer::say(body);
        }
    }
    if let Some(ex) = d.exercise(&hit.id) {
        return Answer::say(format!(
            "{} ({}, {}). {}",
            ex.name,
            d.exercise_category_label(&ex.category),
            d.difficulty(ex.difficulty),
            ex.instructions
        ));
    }
    Answer::say(format!("I don't have details on {} yet.", hit.name))
}

fn suggest(conn: &Connection) -> Answer {
    let d = data();
    let progress = db::progress_map(conn);
    let mut picks: Vec<(usize, &str, String)> = Vec::new();
    for sk in &d.skills.items {
        let unlocked = sk.prereqs.iter().all(|p| progress.get(p).map(|s| s == "completed").unwrap_or(false));
        let done = progress.get(&sk.id).map(|s| s == "completed").unwrap_or(false);
        if done || !unlocked {
            continue;
        }
        let training = progress.get(&sk.id).map(|s| s == "training").unwrap_or(false);
        picks.push((if training { 0 } else { 1 }, &sk.id, sk.name.clone()));
    }
    picks.sort_by(|a, b| a.0.cmp(&b.0).then(a.2.cmp(&b.2)));
    if picks.is_empty() {
        return Answer::say("Everything in the tree is locked or done — nice. Try a free workout?");
    }
    let names: Vec<String> = picks.iter().take(3).map(|(_, _, n)| n.clone()).collect();
    let st = db::stats(conn);
    let lead = if st.streak > 0 { format!("{} days in a row — ", st.streak) } else { String::new() };
    Answer::say(format!(
        "{lead}next up in the tree: {}. A session of 3 x 5–8 reps each is a solid start.",
        names.join(", ")
    ))
}

fn list_workouts(conn: &Connection) -> Answer {
    let ws = db::workouts(conn);
    if ws.is_empty() {
        return Answer::say("No workouts saved yet — build one on the Workouts page.");
    }
    let names = ws
        .iter()
        .take(6)
        .map(|w| format!("{} ({} exercises)", w.name, w.count))
        .collect::<Vec<_>>()
        .join(", ");
    Answer::say(format!("Your workouts: {names}."))
}

fn log_run_answer(text: &str) -> Answer {
    match detect_run(text) {
        Some((dist, dur)) => {
            let pace = dur as f64 * 1000.0 / dist as f64;
            Answer {
                text: format!(
                    "I'll log a run of {:.2} km in {} (pace {}:{:02} /km).",
                    dist as f64 / 1000.0,
                    fmt_time(dur),
                    (pace as i64) / 60,
                    (pace as i64) % 60
                ),
                intent: "log_run",
                confidence: 0.9,
                entities: vec!["Run".into()],
                actions: vec![Action::Run { distance_m: dist, seconds: dur }],
                undo: false,
            }
        }
        None => Answer::say("Tell me the distance and time — e.g. “ran 5 km in 26:30”."),
    }
}

fn log_set_answer(conn: &Connection, text: &str, hit: Option<&Hit>) -> Answer {
    let d = data();
    let Some(hit) = hit else {
        return Answer::say("I couldn't tell which exercise that is. Try “did 3x12 push ups”.");
    };
    let (mut sets, mut reps, hold) = parse_sets_reps(text);
    if reps == 0 && hold == 0 {
        if let Some(ex) = d.exercise(&hit.id) {
            if ex.default_amount > 0 {
                if ex.kind == "hold" { sets = ex.default_sets; } else { reps = ex.default_amount; }
            }
        }
        if reps == 0 && hold == 0 {
            return Answer::say(format!("How many {}? e.g. “{} 3x10”.", hit.name, hit.name));
        }
    }
    let skill_id = d
        .exercise(&hit.id)
        .and_then(|e| e.skill_id.clone())
        .or_else(|| hit.is_skill.then(|| hit.id.clone()));
    let previous = if hit.is_skill { db::bests(conn).get(&hit.id).map(|(v, _)| *v) } else { best_for(conn, &hit.id) };
    let mut note = String::new();
    if let Some(best) = previous {
        let value = if hold > 0 { hold as f64 } else { reps as f64 };
        if value > best {
            note = format!(" (previous best {} — new PR!)", best as i64);
        } else {
            note = format!(" (previous best {})", best as i64);
        }
    }
    let action = Action::Set {
        exercise_id: hit.id.clone(),
        exercise_name: hit.name.clone(),
        skill_id,
        sets: sets.max(1),
        reps,
        hold,
    };
    Answer {
        text: format!("I'll log {} — {}.{}", hit.name, action.describe(), note),
        intent: "log_set",
        confidence: 0.9,
        entities: vec![hit.name.clone()],
        actions: vec![action],
        undo: false,
    }
}

fn followup_answer(text: &str, last: Option<&Action>) -> Answer {
    let Some(last) = last else {
        return Answer::say("Nothing to repeat yet — log a set first.");
    };
    let nums: Vec<i64> = normalize(text)
        .split_whitespace()
        .filter_map(|w| w.parse::<i64>().ok())
        .collect();
    match last {
        Action::Run { .. } => {
            if nums.len() >= 2 {
                let dist = if nums[0] < 100 { nums[0] * 1000 } else { nums[0] };
                let secs = if nums[1] < 100 { nums[1] * 60 } else { nums[1] };
                let a = Action::Run { distance_m: dist, seconds: secs };
                Answer { text: format!("Another run: {}.", a.describe()), actions: vec![a], ..Answer::say("") }
            } else {
                Answer::say("How far and how long? e.g. “again 5k in 25:00”.")
            }
        }
        Action::Set { exercise_id, exercise_name, skill_id, sets, reps, hold } => {
            let amount = *nums.last().unwrap_or(if *hold > 0 { hold } else { reps });
            let n_sets = if nums.len() >= 2 { nums[0] } else { *sets };
            let a = Action::Set {
                exercise_id: exercise_id.clone(),
                exercise_name: exercise_name.clone(),
                skill_id: skill_id.clone(),
                sets: n_sets.max(1),
                reps: if *hold > 0 { 0 } else { amount },
                hold: if *hold > 0 { amount } else { 0 },
            };
            Answer {
                text: format!("Again: {} — {}.", exercise_name, a.describe()),
                entities: vec![exercise_name.clone()],
                actions: vec![a],
                ..Answer::say("")
            }
        }
    }
}

fn correct_answer(conn: &Connection, text: &str, last: Option<&Action>) -> Answer {
    let Some(last) = last else {
        return Answer::say("Nothing to correct yet — log a set first.");
    };
    let nums: Vec<i64> = normalize(text)
        .split_whitespace()
        .filter_map(|w| w.parse::<i64>().ok())
        .collect();
    let Some(amount) = nums.last().copied() else {
        return Answer::say("What's the right number? e.g. “no, 15 reps”.");
    };
    match last {
        Action::Set { exercise_id, exercise_name, skill_id, sets, hold, .. } => {
            undo_rows(conn, last);
            let n_sets = if nums.len() >= 2 { nums[0] } else { *sets };
            let a = Action::Set {
                exercise_id: exercise_id.clone(),
                exercise_name: exercise_name.clone(),
                skill_id: skill_id.clone(),
                sets: n_sets.max(1),
                reps: if *hold > 0 { 0 } else { amount },
                hold: if *hold > 0 { amount } else { 0 },
            };
            Answer {
                text: format!("Fixed: removed the last {} entry, logging {} instead.", exercise_name, a.describe()),
                entities: vec![exercise_name.clone()],
                actions: vec![a],
                ..Answer::say("")
            }
        }
        Action::Run { .. } => Answer::say("Runs are logged as a whole — say it again with the right numbers."),
    }
}

fn undo_answer(conn: &Connection, last: Option<&Action>) -> Answer {
    match last {
        Some(action) => {
            undo_rows(conn, action);
            Answer { text: "Removed the last entry I logged.".into(), undo: true, ..Answer::say("") }
        }
        None => Answer::say("There's nothing of mine to undo."),
    }
}

fn undo_rows(conn: &Connection, action: &Action) {
    match action {
        Action::Run { .. } => {
            let _ = conn.execute(
                "DELETE FROM sessions WHERE id=(SELECT id FROM sessions WHERE workout_name='Run'                  AND status='completed' ORDER BY id DESC LIMIT 1)", []);
        }
        Action::Set { .. } => {
            let _ = conn.execute(
                "DELETE FROM session_sets WHERE id=(SELECT MAX(ss.id) FROM session_sets ss                  JOIN sessions s ON s.id=ss.session_id WHERE s.workout_name='Coach log')", []);
            let _ = conn.execute(
                "DELETE FROM performances WHERE id=(SELECT MAX(id) FROM performances WHERE source='coach')", []);
            let _ = conn.execute("DELETE FROM records WHERE id=(SELECT MAX(id) FROM records)", []);
        }
    }
}

fn level_answer(conn: &Connection) -> Answer {
    let level = logic::level_info(data(), db::total_xp(conn));
    if level.need <= 0 {
        return Answer::say("You're at the top level already.");
    }
    Answer::say(format!(
        "Level {} · {}: {}/{} XP, {} to go for {} (level {}).",
        level.level,
        level.title,
        level.into,
        level.need,
        level.need - level.into,
        if level.next_title.is_empty() { "the next level" } else { &level.next_title },
        level.next_level
    ))
}

fn compare_answer(conn: &Connection) -> Answer {
    let today = chrono::Local::now().date_naive();
    let monday = today - chrono::Duration::days(today.weekday().num_days_from_monday() as i64);
    let prev = monday - chrono::Duration::days(7);
    let count = |start: &str, end: &str| -> (i64, i64) {
        conn.query_row(
            "SELECT COUNT(*), COALESCE(SUM(elapsed_sec),0) FROM sessions WHERE status='completed'              AND session_date>=? AND session_date<?",
            params![start, end],
            |r| Ok((r.get(0)?, r.get(1)?)),
        )
        .unwrap_or((0, 0))
    };
    let fmt = |d: chrono::NaiveDate| d.format("%Y-%m-%d").to_string();
    let tomorrow = today + chrono::Duration::days(1);
    let (this_n, this_s) = count(&fmt(monday), &fmt(tomorrow));
    let (last_n, last_s) = count(&fmt(prev), &fmt(monday));
    let trend = if this_n == last_n {
        "same as".to_string()
    } else if this_n > last_n {
        format!("{} more than", this_n - last_n)
    } else {
        format!("{} fewer than", last_n - this_n)
    };
    Answer::say(format!(
        "This week: {} workouts ({} min) — {} last week ({} workouts, {} min).",
        this_n,
        this_s / 60,
        trend,
        last_n,
        last_s / 60
    ))
}

fn plan_answer(text: &str) -> Answer {
    let d = data();
    let low = format!(" {} ", normalize(text));
    let cat = ["push", "pull", "core", "legs", "static", "balance", "skill", "explosive"]
        .into_iter()
        .find(|c| low.contains(&format!(" {c} ")));
    let mut picks: Vec<&crate::data::Exercise> = d
        .exercises
        .items
        .iter()
        .filter(|e| cat.map(|c| e.category == c).unwrap_or(true) && e.difficulty <= 1)
        .collect();
    picks.sort_by(|a, b| (a.category.clone(), a.name.clone()).cmp(&(b.category.clone(), b.name.clone())));
    if picks.is_empty() {
        return Answer::say("No beginner exercises for that category in the library.");
    }
    let lines: Vec<String> = picks
        .iter()
        .take(3)
        .map(|e| {
            format!(
                "• {} — {} x {}{}",
                e.name,
                e.default_sets,
                e.default_amount,
                if e.kind == "hold" { " s" } else { " reps" }
            )
        })
        .collect();
    let label = match cat {
        Some(c) => format!("{} starter", d.exercise_category_label(c)),
        None => "Full-body starter".to_string(),
    };
    Answer::say(format!(
        "{label}:\n{}\nRest {} s between sets.",
        lines.join("\n"),
        picks[0].default_rest
    ))
}

fn fallback(toks: &[String]) -> Answer {
    Answer::say(format!(
        "I didn't catch that.{} I understand sets (“3x12 push ups”), holds (“plank 1:30”), \
         runs (“ran 5k in 26:30”), totals, bests, “hey”, “did I train today?” and “what next?”.",
        if toks.is_empty() { "" } else { "" }
    ))
}

fn is_hold(name: &str) -> bool {
    let low = name.to_lowercase();
    ["plank", "hold", "hang", "lever", "handstand", "l-sit", "lsit", "flag", "support", "prkno"]
        .iter()
        .any(|w| low.contains(w))
}

// ------------------------------------------------------------------ writes

/// Performs the prepared actions and returns one confirmation line per action.
pub fn apply(conn: &Connection, actions: &[Action]) -> Vec<String> {
    let mut out = Vec::new();
    for action in actions {
        match action {
            Action::Run { distance_m, seconds } => {
                if db::log_run(conn, *distance_m, *seconds).is_ok() {
                    out.push(format!("Logged run: {}.", action.describe()));
                }
            }
            Action::Set { exercise_id, exercise_name, skill_id, sets, reps, hold } => {
                let value = if *hold > 0 { *hold as f64 } else { *reps as f64 };
                let today = chrono::Local::now().date_naive().to_string();
                let _ = conn.execute(
                    "INSERT INTO performances(exercise_id,value,logged,source,note) VALUES(?,?,?,'coach',?)",
                    params![exercise_id, value, today, action.describe()],
                );
                if let Some(skill) = skill_id {
                    db::add_record(conn, skill, value);
                }
                let sid = coach_session(conn, &today);
                let pos: i64 = conn
                    .query_row(
                        "SELECT COALESCE(MAX(ex_pos),-1)+1 FROM session_sets WHERE session_id=?",
                        params![sid],
                        |r| r.get(0),
                    )
                    .unwrap_or(0);
                let kind = if *hold > 0 { "hold" } else { "reps" };
                for i in 0..(*sets).max(1) {
                    let _ = conn.execute(
                        "INSERT INTO session_sets(session_id,ex_pos,set_idx,exercise_id,exercise_name,kind,\
                         target_reps,target_hold,reps,hold,rest_sec,done,done_at,confirmed) \
                         VALUES(?,?,?,?,?,?,?,?,?,?,0,1,datetime('now','localtime'),1)",
                        params![sid, pos, i, exercise_id, exercise_name, kind, reps, hold, reps, hold],
                    );
                }
                out.push(format!("Logged {}: {}.", exercise_name, action.describe()));
            }
        }
    }
    out
}

fn coach_session(conn: &Connection, day: &str) -> i64 {
    let existing: Option<i64> = conn
        .query_row(
            "SELECT id FROM sessions WHERE workout_name='Coach log' AND session_date=? ORDER BY id DESC LIMIT 1",
            params![day],
            |r| r.get(0),
        )
        .ok();
    if let Some(id) = existing {
        return id;
    }
    conn.execute(
        "INSERT INTO sessions(workout_id,workout_name,session_date,started,ended,status,elapsed_sec,\
         state_json,entry_id) VALUES(NULL,'Coach log',?,?,?,'completed',0,'{}',NULL)",
        params![day, format!("{day}T00:00:00"), format!("{day}T00:00:00")],
    )
    .map(|_| conn.last_insert_rowid())
    .unwrap_or(0)
}

// ------------------------------------------------------------------- chat

pub struct Chat {
    pub messages: Vec<(bool, String)>,
    pub last: Option<Action>,
    pub input: String,
    pub pending: Vec<Action>,
    pub pending_text: String,
    pub detail: String,
}

impl Default for Chat {
    fn default() -> Self {
        Self {
            messages: vec![(
                false,
                "Hey. I'm right here on this machine — nothing leaves the app.\n\
                 Tell me what you trained, correct me, or ask me anything about your numbers."
                    .into(),
            )],
            last: None,
            input: String::new(),
            pending: Vec::new(),
            pending_text: String::new(),
            detail: "Waiting for the first message.".into(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Tests share the process-wide data directory, so they run one at a time and each
    /// starts from its own empty database.
    static LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

    fn conn(tag: &str) -> (std::sync::MutexGuard<'static, ()>, Connection) {
        let guard = LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let dir = std::env::temp_dir().join(format!("calix-coach-{tag}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).ok();
        std::env::set_var("SKILLTREE_DATA", &dir);
        (guard, db::open().expect("open test database"))
    }

    #[test]
    fn coach_follows_up_corrects_and_undoes() {
        let (_lock, conn) = conn("follow");
        let first = ask(&conn, "did 3x12 push ups");
        assert_eq!(first.actions.len(), 1);
        apply(&conn, &first.actions);
        let last = first.actions.first().cloned();

        let more = ask_with(&conn, "and 10 more", last.as_ref());
        assert_eq!(more.intent, "followup");
        assert_eq!(more.actions.len(), 1);
        assert_eq!(more.actions[0].describe(), "3 x 10 reps");

        let fixed = ask_with(&conn, "no, 15 reps", last.as_ref());
        assert_eq!(fixed.intent, "correct");
        assert_eq!(fixed.actions[0].describe(), "3 x 15 reps");

        let undo = ask_with(&conn, "undo", last.as_ref());
        assert!(undo.undo);
        assert!(undo.actions.is_empty());
    }

    #[test]
    fn coach_plans_and_compares() {
        let (_lock, conn) = conn("plan");
        let plan = ask(&conn, "plan a pull workout");
        assert_eq!(plan.intent, "plan");
        assert!(plan.text.contains("Pull"), "{}", plan.text);
        assert!(plan.text.contains('•'), "{}", plan.text);

        let compare = ask(&conn, "compare this week vs last week");
        assert_eq!(compare.intent, "compare");
        assert!(compare.text.contains("last week"), "{}", compare.text);

        let level = ask(&conn, "how much xp to next level");
        assert_eq!(level.intent, "level");
        assert!(level.text.contains("XP"), "{}", level.text);
    }

    #[test]
    fn coach_understands_notes_and_questions() {
        let (_lock, c) = conn("notes");
        let hey = ask(&c, "hey");
        assert_eq!(hey.intent, "greet");
        assert!(!hey.text.is_empty());

        let thanks = ask(&c, "diky");
        assert_eq!(thanks.intent, "thanks");

        let set = ask(&c, "did 3x12 push ups");
        assert_eq!(set.intent, "log_set");
        match set.actions.first().expect("one action") {
            Action::Set { exercise_id, sets, reps, .. } => {
                assert_eq!(exercise_id, "pushup");
                assert_eq!((*sets, *reps), (3, 12));
            }
            _ => panic!("expected a set"),
        }

        let hold = ask(&c, "plank 1:30");
        match hold.actions.first().expect("hold action") {
            Action::Set { hold, reps, .. } => assert_eq!((*hold, *reps), (90, 0)),
            _ => panic!("expected a hold"),
        }

        let run = ask(&c, "ran 5k in 26:30");
        assert_eq!(run.intent, "log_run");
        match run.actions.first().expect("run action") {
            Action::Run { distance_m, seconds } => assert_eq!((*distance_m, *seconds), (5000, 1590)),
            _ => panic!("expected a run"),
        }

        // czech slang and typos
        let shyby = ask(&c, "shyby 3x5");
        assert_eq!(shyby.actions.first().map(|a| a.label()), Some("Pull-Up".to_string()));

        // write it, then ask about it
        apply(&c, &set.actions);
        let totals = ask(&c, "sum of reps this week");
        assert!(totals.text.contains("36 reps"), "{}", totals.text);
        let best = ask(&c, "what's my best push up?");
        assert!(best.text.contains("12"), "{}", best.text);
        let today = ask(&c, "did I train today?");
        assert!(today.text.starts_with("Yes"), "{}", today.text);

        let last = ask(&c, "what did I do last time?");
        assert!(last.text.contains("Coach log"), "{}", last.text);

        let suggest = ask(&c, "what should I train today?");
        assert_eq!(suggest.intent, "suggest");

        let explain = ask(&c, "what is a muscle up?");
        assert_eq!(explain.intent, "explain");
        assert!(explain.text.contains("Muscle-Up"), "{}", explain.text);

        assert_eq!(ask(&c, "what can you do").intent, "help");
        assert_eq!(ask(&c, "banana rocket").intent, "unknown");
    }
}
