//! Pure logic ported from the Python edition: the skill graph layout, skill
//! states, the level curve and the per-exercise rank ladders. No UI, no SQL.
use crate::data::{Data, LineStep};
use std::collections::{HashMap, HashSet};

pub const NODE_W: f32 = 170.0;
pub const NODE_H: f32 = 66.0;
pub const COL_W: f32 = 200.0;
pub const ROW_H: f32 = 150.0;
pub const LANE_GAP: f32 = 70.0;

// ------------------------------------------------------------------ skill tree
#[derive(Clone)]
pub struct Lane {
    pub category: String,
    pub left: f32,
    pub width: f32,
}

#[derive(Clone)]
pub struct TreeLayout {
    pub pos: HashMap<String, (f32, f32)>,
    pub lanes: Vec<Lane>,
    pub max_row: usize,
}

fn depth_of(d: &Data, id: &str, memo: &mut HashMap<String, usize>, stack: &mut Vec<String>) -> usize {
    if let Some(v) = memo.get(id) {
        return *v;
    }
    let Some(skill) = d.skill(id) else { return 0 };
    if stack.iter().any(|s| s == id) {
        return 0;
    }
    stack.push(id.to_string());
    let v = if skill.prereqs.is_empty() {
        0
    } else {
        1 + skill
            .prereqs
            .iter()
            .map(|p| depth_of(d, p, memo, stack))
            .max()
            .unwrap_or(0)
    };
    stack.pop();
    memo.insert(id.to_string(), v);
    v
}

pub fn layout(d: &Data) -> TreeLayout {
    let mut memo: HashMap<String, usize> = HashMap::new();
    for s in &d.skills.items {
        let mut stack = Vec::new();
        depth_of(d, &s.id, &mut memo, &mut stack);
    }

    let mut groups: HashMap<(String, usize), Vec<String>> = HashMap::new();
    for s in &d.skills.items {
        let depth = *memo.get(&s.id).unwrap_or(&0);
        groups.entry((s.category.clone(), depth)).or_default().push(s.id.clone());
    }

    let mut lanes: Vec<Lane> = Vec::new();
    let mut x = 0.0f32;
    for cat in &d.skills.category_order {
        let cols = groups
            .iter()
            .filter(|((c, _), v)| c == cat && !v.is_empty())
            .map(|(_, v)| v.len())
            .max()
            .unwrap_or(1);
        let width = cols as f32 * COL_W;
        lanes.push(Lane { category: cat.clone(), left: x, width });
        x += width + LANE_GAP;
    }

    let max_row = memo.values().copied().max().unwrap_or(0);
    let mut pos: HashMap<String, (f32, f32)> = HashMap::new();
    for row in 0..=max_row {
        for lane in &lanes {
            let mut ids = groups.get(&(lane.category.clone(), row)).cloned().unwrap_or_default();
            if ids.is_empty() {
                continue;
            }
            let center = lane.left + lane.width / 2.0;
            ids.sort_by(|a, b| {
                let want = |sid: &str| -> f32 {
                    let Some(skill) = d.skill(sid) else { return center };
                    let xs: Vec<f32> = skill.prereqs.iter().filter_map(|p| pos.get(p).map(|v| v.0)).collect();
                    if xs.is_empty() {
                        center
                    } else {
                        xs.iter().sum::<f32>() / xs.len() as f32
                    }
                };
                want(a).partial_cmp(&want(b)).unwrap_or(std::cmp::Ordering::Equal)
            });
            let n = ids.len() as f32;
            for (i, sid) in ids.iter().enumerate() {
                let px = center + (i as f32 - (n - 1.0) / 2.0) * COL_W;
                pos.insert(sid.clone(), (px, row as f32 * ROW_H));
            }
        }
    }
    TreeLayout { pos, lanes, max_row }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Status {
    Locked,
    Available,
    Training,
    Completed,
}

impl Status {
    pub fn key(self) -> &'static str {
        match self {
            Status::Locked => "locked",
            Status::Available => "available",
            Status::Training => "training",
            Status::Completed => "completed",
        }
    }

    pub fn label(self) -> &'static str {
        match self {
            Status::Locked => "Locked",
            Status::Available => "Available to train",
            Status::Training => "Training",
            Status::Completed => "Completed",
        }
    }
}

pub fn status(d: &Data, progress: &HashMap<String, String>, sid: &str) -> Status {
    let done = |id: &str| progress.get(id).map(|s| s == "completed").unwrap_or(false);
    if done(sid) {
        return Status::Completed;
    }
    let Some(skill) = d.skill(sid) else { return Status::Locked };
    if skill.prereqs.iter().all(|p| done(p)) {
        if progress.get(sid).map(|s| s == "training").unwrap_or(false) {
            Status::Training
        } else {
            Status::Available
        }
    } else {
        Status::Locked
    }
}

pub fn missing_prereqs<'a>(d: &'a Data, progress: &HashMap<String, String>, sid: &str) -> Vec<&'a str> {
    let Some(skill) = d.skill(sid) else { return Vec::new() };
    skill
        .prereqs
        .iter()
        .filter(|p| progress.get(*p).map(|s| s != "completed").unwrap_or(true))
        .filter_map(|p| d.skill(p).map(|s| s.name.as_str()))
        .collect()
}

// --------------------------------------------------------------------- levels
#[derive(Clone)]
pub struct LevelInfo {
    pub level: i64,
    pub title: String,
    pub color: String,
    pub total: i64,
    pub into: i64,
    pub need: i64,
    pub progress: f32,
    pub next_title: String,
    pub next_level: i64,
}

pub fn xp_needed(level: i64) -> i64 {
    let k = level - 1;
    100 + 40 * k + 6 * k * k
}

pub fn cumulative(level: i64) -> i64 {
    let m = level - 1;
    100 * m + 20 * m * (m - 1) + (m - 1) * m * (2 * m - 1)
}

pub fn level_info(d: &Data, total: i64) -> LevelInfo {
    let total = total.max(0);
    let mut level = 1;
    while level < d.prog.max_level && total >= cumulative(level + 1) {
        level += 1;
    }
    let (title, color) = d
        .prog
        .titles
        .iter()
        .filter(|t| level >= t.level)
        .last()
        .map(|t| (t.title.clone(), t.color.clone()))
        .unwrap_or_else(|| ("Beginner".into(), "#9aa4b2".into()));
    let next = d.prog.titles.iter().find(|t| t.level > level).cloned();
    if level >= d.prog.max_level {
        return LevelInfo {
            level,
            title,
            color,
            total,
            into: 0,
            need: 0,
            progress: 1.0,
            next_title: String::new(),
            next_level: 0,
        };
    }
    let into = total - cumulative(level);
    let need = xp_needed(level);
    LevelInfo {
        level,
        title,
        color,
        total,
        into,
        need,
        progress: into as f32 / need as f32,
        next_title: next.as_ref().map(|t| t.title.clone()).unwrap_or_default(),
        next_level: next.map(|t| t.level).unwrap_or(0),
    }
}

// ---------------------------------------------------------------------- ranks
#[derive(Clone)]
pub struct Track {
    pub id: String,
    pub name: String,
    pub group: String,
    /// reps | hold | line
    pub kind: String,
    pub thresholds: Vec<f64>,
    pub unit: String,
    pub difficulty: usize,
    pub exercise_id: String,
    pub steps: Vec<LineStep>,
}

pub fn thresholds(top: f64, fractions: &[f64], integer: bool) -> Vec<f64> {
    let mut out: Vec<f64> = Vec::new();
    for f in fractions {
        let mut v = if integer { (top * f).round().max(1.0) } else { (top * f * 100.0).round() / 100.0 };
        if let Some(last) = out.last() {
            if v <= *last {
                v = last + if integer { 1.0 } else { 0.05 };
            }
        }
        out.push(v);
    }
    out
}

fn group_for(d: &Data, ex_id: &str) -> String {
    let Some(ex) = d.exercise(ex_id) else { return "other".into() };
    match ex.category.as_str() {
        "push" => "pushing".into(),
        "pull" => "pulling".into(),
        "core" => "core".into(),
        "legs" | "explosive" => "legs".into(),
        "static" | "balance" | "skill" => "static".into(),
        _ => "pulling".into(),
    }
}

pub fn build_tracks(d: &Data) -> Vec<Track> {
    let mut tracks = Vec::new();
    for ex in &d.exercises.items {
        let Some(top) = d.ranks.tops.get(&ex.id) else { continue };
        tracks.push(Track {
            id: ex.id.clone(),
            name: ex.name.clone(),
            group: group_for(d, &ex.id),
            kind: ex.kind.clone(),
            thresholds: thresholds(*top as f64, &d.ranks.single_fractions, true),
            unit: if ex.kind == "reps" { "reps".into() } else { "s".into() },
            difficulty: ex.difficulty,
            exercise_id: ex.id.clone(),
            steps: Vec::new(),
        });
    }
    for line in &d.ranks.lines {
        if line.steps.iter().any(|s| d.exercise(&s.exercise_id).is_none()) {
            continue;
        }
        let difficulty = line
            .steps
            .iter()
            .filter_map(|s| d.exercise(&s.exercise_id).map(|e| e.difficulty))
            .max()
            .unwrap_or(0);
        tracks.push(Track {
            id: line.id.clone(),
            name: line.name.clone(),
            group: line.group.clone(),
            kind: "line".into(),
            thresholds: thresholds(line.steps.len() as f64, &d.ranks.line_fractions, false),
            unit: "steps".into(),
            difficulty,
            exercise_id: String::new(),
            steps: line.steps.clone(),
        });
    }
    tracks
}

pub fn rank_for(thresholds: &[f64], value: f64) -> usize {
    thresholds.iter().filter(|t| value >= **t).count()
}

#[derive(Clone)]
pub struct TrackResult {
    pub track: Track,
    pub best: f64,
    pub rank: usize,
    pub progress: f32,
    pub target: Option<f64>,
    pub practiced: bool,
    pub goal: String,
}

fn line_score(steps: &[LineStep], bests: &HashMap<String, f64>, passed: &HashSet<String>) -> f64 {
    let mut hi: i32 = -1;
    for (i, s) in steps.iter().enumerate() {
        let passed_step = passed.contains(&s.exercise_id) || bests.get(&s.exercise_id).copied().unwrap_or(0.0) >= s.need;
        if passed_step {
            hi = i as i32;
        }
    }
    let mut score = (hi + 1) as f64;
    if (hi + 1) < steps.len() as i32 {
        let nxt = &steps[(hi + 1) as usize];
        score += (bests.get(&nxt.exercise_id).copied().unwrap_or(0.0) / nxt.need).min(0.99);
    }
    score
}

pub fn evaluate(
    track: &Track,
    bests: &HashMap<String, f64>,
    passed: &HashSet<String>,
    max_rank: usize,
) -> TrackResult {
    let value = if track.kind == "line" {
        line_score(&track.steps, bests, passed)
    } else {
        bests.get(&track.exercise_id).copied().unwrap_or(0.0)
    };
    let rank = rank_for(&track.thresholds, value);
    let (progress, target) = if rank >= max_rank {
        (1.0, None)
    } else {
        let lo = if rank == 0 { 0.0 } else { track.thresholds[rank - 1] };
        let hi = track.thresholds[rank];
        (((value - lo) / (hi - lo)).clamp(0.0, 1.0) as f32, Some(hi))
    };
    let practiced = value > 0.0;
    let goal = match target {
        None => format!("Top rank reached ({})", &track.name),
        Some(t) if practiced => format!("{} {} for the next rank", fmt_num(t), track.unit),
        Some(t) => format!("Log your first set, {} {} makes you an Initiate", fmt_num(t), track.unit),
    };
    TrackResult { track: track.clone(), best: value, rank, progress, target, practiced, goal }
}

pub fn fmt_num(v: f64) -> String {
    if (v - v.round()).abs() < 0.005 {
        format!("{}", v.round() as i64)
    } else {
        format!("{:.2}", v)
    }
}

pub fn fmt_clock(sec: i64) -> String {
    let sec = sec.max(0);
    let (h, m, s) = (sec / 3600, (sec % 3600) / 60, sec % 60);
    if h > 0 {
        format!("{}:{:02}:{:02}", h, m, s)
    } else {
        format!("{:02}:{:02}", m, s)
    }
}

pub fn fmt_pace(sec_per_km: Option<f64>) -> String {
    match sec_per_km {
        Some(v) if v > 0.0 => {
            let total = v.round() as i64;
            format!("{}:{:02}", total / 60, total % 60)
        }
        _ => "–".into(),
    }
}

pub fn pace_of(distance_m: i64, duration_s: i64) -> Option<f64> {
    if distance_m <= 0 || duration_s <= 0 {
        None
    } else {
        Some(duration_s as f64 * 1000.0 / distance_m as f64)
    }
}
