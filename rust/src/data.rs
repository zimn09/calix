//! Static catalogue data, embedded at compile time.
//!
//! The JSON files in `data/` are generated from the Python edition by
//! `tools/export_data.py`, so the Rust port ships exactly the same skill tree,
//! exercise library, achievements and rank ladders.
use serde::Deserialize;
use std::collections::HashMap;
use std::sync::OnceLock;

const SKILLS_JSON: &str = include_str!("../data/skills.json");
const EXERCISES_JSON: &str = include_str!("../data/exercises.json");
const DETAILS_JSON: &str = include_str!("../data/details.json");
const ACHIEVEMENTS_JSON: &str = include_str!("../data/achievements.json");
const RANKS_JSON: &str = include_str!("../data/ranks.json");
const PROGRESSION_JSON: &str = include_str!("../data/progression.json");

#[derive(Deserialize, Clone)]
pub struct Category {
    pub label: String,
    pub color: String,
}

#[derive(Deserialize, Clone)]
pub struct Skill {
    pub id: String,
    pub name: String,
    pub category: String,
    pub tier: usize,
    pub prereqs: Vec<String>,
    pub description: String,
    pub steps: Vec<String>,
    pub exercises: Vec<String>,
    pub regressions: Vec<String>,
    pub unit: String,
    pub target: f64,
    pub note: String,
}

#[derive(Deserialize)]
pub struct SkillsFile {
    pub categories: HashMap<String, Category>,
    pub category_order: Vec<String>,
    pub tiers: Vec<String>,
    pub tier_xp: Vec<i64>,
    pub items: Vec<Skill>,
}

#[derive(Deserialize, Clone)]
pub struct Exercise {
    pub id: String,
    pub name: String,
    pub category: String,
    pub difficulty: usize,
    /// "reps" or "hold"
    pub kind: String,
    pub default_sets: i64,
    pub default_amount: i64,
    pub default_rest: i64,
    pub instructions: String,
    #[serde(default)]
    pub skill_id: Option<String>,
    #[serde(default)]
    pub anim: String,
}

#[derive(Deserialize)]
pub struct ExercisesFile {
    pub categories: HashMap<String, Category>,
    pub category_order: Vec<String>,
    pub difficulty: Vec<String>,
    pub items: Vec<Exercise>,
}

#[derive(Deserialize, Default, Clone)]
pub struct Detail {
    #[serde(default)]
    pub muscles: Vec<String>,
    #[serde(default)]
    pub mistakes: Vec<String>,
    #[serde(default)]
    pub tips: Vec<String>,
    #[serde(default)]
    pub easier: Vec<String>,
    #[serde(default)]
    pub harder: Vec<String>,
    #[serde(default)]
    pub prereq: Vec<String>,
    #[serde(default)]
    pub related: Vec<String>,
    #[serde(default)]
    pub equipment: String,
}

#[derive(Deserialize, Clone)]
pub struct Achievement {
    pub id: String,
    pub name: String,
    pub description: String,
    pub category: String,
    pub rarity: String,
    pub xp: i64,
    pub metric: String,
    pub target: f64,
    pub icon: String,
    pub unit: String,
    pub exercises: Vec<String>,
    pub skills: Vec<String>,
}

#[derive(Deserialize, Clone)]
pub struct Rarity {
    pub label: String,
    pub color: String,
    pub order: i64,
}

#[derive(Deserialize)]
pub struct AchievementsFile {
    pub categories: HashMap<String, String>,
    pub rarities: HashMap<String, Rarity>,
    pub items: Vec<Achievement>,
}

#[derive(Deserialize, Clone)]
pub struct LineStep {
    pub exercise_id: String,
    pub need: f64,
}

#[derive(Deserialize, Clone)]
pub struct Line {
    pub id: String,
    pub name: String,
    pub group: String,
    pub steps: Vec<LineStep>,
}

#[derive(Deserialize)]
pub struct RanksFile {
    /// [(name, colour)]
    pub ranks: Vec<(String, String)>,
    pub max_rank: usize,
    pub groups: HashMap<String, String>,
    pub tops: HashMap<String, i64>,
    pub lines: Vec<Line>,
    pub single_fractions: Vec<f64>,
    pub line_fractions: Vec<f64>,
}

#[derive(Deserialize, Clone)]
pub struct Title {
    pub level: i64,
    pub title: String,
    pub color: String,
}

#[derive(Deserialize)]
pub struct Progression {
    pub max_level: i64,
    pub titles: Vec<Title>,
    pub xp_workout: i64,
    pub xp_scheduled: i64,
    pub xp_per_set: i64,
    pub max_set_xp: i64,
    pub xp_per_exercise: i64,
    pub max_exercises_xp: i64,
    pub xp_pr: HashMap<String, i64>,
    pub xp_rank: Vec<i64>,
    #[allow(dead_code)]
    pub line_rank_share: f64,
    pub xp_skill_unlock: Vec<i64>,
    pub xp_skill_done: Vec<i64>,
    pub session_daily_cap: i64,
    pub min_session_seconds: i64,
    pub min_sets_share: f64,
}

pub struct Data {
    pub skills: SkillsFile,
    pub exercises: ExercisesFile,
    pub details: HashMap<String, Detail>,
    pub achievements: AchievementsFile,
    pub ranks: RanksFile,
    pub prog: Progression,
    skill_index: HashMap<String, usize>,
    exercise_index: HashMap<String, usize>,
}

impl Data {
    pub fn skill(&self, id: &str) -> Option<&Skill> {
        self.skill_index.get(id).map(|i| &self.skills.items[*i])
    }

    pub fn exercise(&self, id: &str) -> Option<&Exercise> {
        self.exercise_index.get(id).map(|i| &self.exercises.items[*i])
    }

    pub fn detail(&self, id: &str) -> Option<&Detail> {
        self.details.get(id)
    }

    pub fn category_color(&self, cat: &str) -> &str {
        self.skills.categories.get(cat).map(|c| c.color.as_str()).unwrap_or("#8b95a7")
    }

    pub fn category_label<'a>(&'a self, cat: &'a str) -> &'a str {
        self.skills.categories.get(cat).map(|c| c.label.as_str()).unwrap_or(cat)
    }

    pub fn exercise_category_color(&self, cat: &str) -> &str {
        self.exercises.categories.get(cat).map(|c| c.color.as_str()).unwrap_or("#8b95a7")
    }

    pub fn exercise_category_label<'a>(&'a self, cat: &'a str) -> &'a str {
        self.exercises.categories.get(cat).map(|c| c.label.as_str()).unwrap_or(cat)
    }

    pub fn tier(&self, tier: usize) -> &str {
        self.skills.tiers.get(tier).map(|s| s.as_str()).unwrap_or("")
    }

    pub fn difficulty(&self, d: usize) -> &str {
        self.exercises.difficulty.get(d).map(|s| s.as_str()).unwrap_or("")
    }

    pub fn rank_name(&self, rank: usize) -> &str {
        self.ranks.ranks.get(rank).map(|r| r.0.as_str()).unwrap_or("")
    }

    pub fn rank_color(&self, rank: usize) -> &str {
        self.ranks.ranks.get(rank).map(|r| r.1.as_str()).unwrap_or("#4b5565")
    }

    pub fn exercises_in_category(&self, cat: &str) -> Vec<&Exercise> {
        self.exercises.items.iter().filter(|e| e.category == cat).collect()
    }
}

pub fn data() -> &'static Data {
    static ONCE: OnceLock<Data> = OnceLock::new();
    ONCE.get_or_init(|| {
        let skills: SkillsFile = serde_json::from_str(SKILLS_JSON).expect("skills.json");
        let exercises: ExercisesFile = serde_json::from_str(EXERCISES_JSON).expect("exercises.json");
        let details: HashMap<String, Detail> =
            serde_json::from_str(DETAILS_JSON).expect("details.json");
        let achievements: AchievementsFile =
            serde_json::from_str(ACHIEVEMENTS_JSON).expect("achievements.json");
        let ranks: RanksFile = serde_json::from_str(RANKS_JSON).expect("ranks.json");
        let prog: Progression = serde_json::from_str(PROGRESSION_JSON).expect("progression.json");
        let skill_index = skills
            .items
            .iter()
            .enumerate()
            .map(|(i, s)| (s.id.clone(), i))
            .collect();
        let exercise_index = exercises
            .items
            .iter()
            .enumerate()
            .map(|(i, e)| (e.id.clone(), i))
            .collect();
        Data { skills, exercises, details, achievements, ranks, prog, skill_index, exercise_index }
    })
}
