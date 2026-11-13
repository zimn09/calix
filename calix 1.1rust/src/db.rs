//! Local SQLite storage. The schema mirrors the Python edition (version 6), so
//! a `progress.db` written by either app can be read by the other.
use crate::data::Data;
use crate::logic;
use chrono::{Datelike, Local};
use rusqlite::{params, Connection, OptionalExtension};
use std::collections::{HashMap, HashSet};
use std::path::PathBuf;

pub fn data_dir() -> PathBuf {
    if let Ok(p) = std::env::var("SKILLTREE_DATA") {
        return PathBuf::from(p);
    }
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".into());
    PathBuf::from(home).join(".calisthenics_skill_tree")
}

/// The Python edition keeps up to three profiles in the same folder: slot 1 is
/// `progress.db`, slots 2 and 3 are `profile-2.db` / `profile-3.db`, and the last
/// used slot is remembered in `active_profile.json`. Open the active one so both
/// apps show the same training history.
pub fn db_path() -> PathBuf {
    let dir = data_dir();
    let slot = std::fs::read_to_string(dir.join("active_profile.json"))
        .ok()
        .and_then(|raw| serde_json::from_str::<serde_json::Value>(&raw).ok())
        .and_then(|v| v.get("active").and_then(|a| a.as_i64()))
        .unwrap_or(1);
    if slot > 1 {
        let path = dir.join(format!("profile-{slot}.db"));
        if path.exists() {
            return path;
        }
    }
    dir.join("progress.db")
}

fn today() -> String {
    Local::now().date_naive().to_string()
}

fn stamp() -> String {
    Local::now().format("%Y-%m-%dT%H:%M:%S").to_string()
}

pub fn open() -> rusqlite::Result<Connection> {
    let dir = data_dir();
    std::fs::create_dir_all(&dir).ok();
    let conn = Connection::open(db_path())?;
    conn.pragma_update(None, "foreign_keys", "ON")?;
    migrate(&conn)?;
    sync_builtin(&conn)?;
    seed_examples(&conn)?;
    Ok(conn)
}

fn migrate(conn: &Connection) -> rusqlite::Result<()> {
    conn.execute_batch(
        r#"
        CREATE TABLE IF NOT EXISTS progress(
            skill_id TEXT PRIMARY KEY, status TEXT NOT NULL, updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS records(
            id INTEGER PRIMARY KEY AUTOINCREMENT, skill_id TEXT NOT NULL,
            value REAL NOT NULL, logged TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS exercises(
            id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
            difficulty INTEGER NOT NULL, kind TEXT NOT NULL,
            default_sets INTEGER NOT NULL, default_amount INTEGER NOT NULL,
            default_rest INTEGER NOT NULL, instructions TEXT NOT NULL DEFAULT '',
            skill_id TEXT, builtin INTEGER NOT NULL DEFAULT 0, anim TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS workouts(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', style TEXT NOT NULL DEFAULT 'strength',
            created TEXT NOT NULL, updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS workout_exercises(
            id INTEGER PRIMARY KEY AUTOINCREMENT, workout_id INTEGER NOT NULL,
            position INTEGER NOT NULL, exercise_id TEXT NOT NULL,
            sets INTEGER NOT NULL, reps INTEGER NOT NULL DEFAULT 0,
            hold_sec INTEGER NOT NULL DEFAULT 0, rest_sets INTEGER NOT NULL DEFAULT 60,
            rest_after INTEGER NOT NULL DEFAULT 90, note TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS sessions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, workout_id INTEGER,
            workout_name TEXT NOT NULL, session_date TEXT NOT NULL, started TEXT NOT NULL,
            ended TEXT, status TEXT NOT NULL, elapsed_sec INTEGER NOT NULL DEFAULT 0,
            state_json TEXT NOT NULL DEFAULT '{}', entry_id INTEGER,
            distance_m INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS session_sets(
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL,
            ex_pos INTEGER NOT NULL, set_idx INTEGER NOT NULL,
            exercise_id TEXT NOT NULL, exercise_name TEXT NOT NULL, kind TEXT NOT NULL,
            target_reps INTEGER NOT NULL DEFAULT 0, target_hold INTEGER NOT NULL DEFAULT 0,
            reps INTEGER NOT NULL DEFAULT 0, hold INTEGER NOT NULL DEFAULT 0,
            rest_sec INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
            done INTEGER NOT NULL DEFAULT 0, done_at TEXT,
            confirmed INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS performances(
            id INTEGER PRIMARY KEY AUTOINCREMENT, exercise_id TEXT NOT NULL, value REAL NOT NULL,
            logged TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual',
            session_id INTEGER, note TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS xp_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL UNIQUE,
            amount INTEGER NOT NULL, reason TEXT NOT NULL, category TEXT NOT NULL,
            earned_on TEXT NOT NULL, awarded TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS achievements(
            id TEXT PRIMARY KEY, progress REAL NOT NULL DEFAULT 0, unlocked TEXT);
        CREATE TABLE IF NOT EXISTS exercise_details(
            exercise_id TEXT PRIMARY KEY, muscles TEXT NOT NULL DEFAULT '',
            technique TEXT NOT NULL DEFAULT '', mistakes TEXT NOT NULL DEFAULT '',
            tips TEXT NOT NULL DEFAULT '', easier TEXT NOT NULL DEFAULT '',
            harder TEXT NOT NULL DEFAULT '', prerequisites TEXT NOT NULL DEFAULT '',
            related TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT '',
            difficulty INTEGER NOT NULL DEFAULT 1, equipment TEXT NOT NULL DEFAULT '',
            updated TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS schedule_entries(
            id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
            weekday INTEGER, on_date TEXT, workout_id INTEGER,
            is_rest INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
            created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS schedule_skips(
            entry_id INTEGER NOT NULL, on_date TEXT NOT NULL,
            PRIMARY KEY(entry_id, on_date));
        CREATE INDEX IF NOT EXISTS idx_we_workout ON workout_exercises(workout_id, position);
        CREATE INDEX IF NOT EXISTS idx_ss_session ON session_sets(session_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(session_date, status);
        CREATE INDEX IF NOT EXISTS idx_perf_ex ON performances(exercise_id, logged);
        "#,
    )?;
    // Databases written by older editions (or by the Python app before 1.1) are
    // missing columns that CREATE TABLE IF NOT EXISTS cannot add. Patch them in.
    let patches: &[(&str, &str, &str)] = &[
        ("sessions", "elapsed_sec", "INTEGER NOT NULL DEFAULT 0"),
        ("sessions", "state_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("sessions", "entry_id", "INTEGER"),
        ("sessions", "distance_m", "INTEGER NOT NULL DEFAULT 0"),
        ("session_sets", "target_reps", "INTEGER NOT NULL DEFAULT 0"),
        ("session_sets", "target_hold", "INTEGER NOT NULL DEFAULT 0"),
        ("session_sets", "rest_sec", "INTEGER NOT NULL DEFAULT 0"),
        ("session_sets", "note", "TEXT NOT NULL DEFAULT ''"),
        ("session_sets", "done_at", "TEXT"),
        ("session_sets", "confirmed", "INTEGER NOT NULL DEFAULT 0"),
        ("workout_exercises", "rest_after", "INTEGER NOT NULL DEFAULT 90"),
        ("workout_exercises", "note", "TEXT NOT NULL DEFAULT ''"),
        ("exercises", "instructions", "TEXT NOT NULL DEFAULT ''"),
        ("exercises", "skill_id", "TEXT"),
        ("exercises", "anim", "TEXT NOT NULL DEFAULT ''"),
        ("exercises", "builtin", "INTEGER NOT NULL DEFAULT 0"),
        ("performances", "source", "TEXT NOT NULL DEFAULT 'manual'"),
        ("performances", "session_id", "INTEGER"),
        ("performances", "note", "TEXT NOT NULL DEFAULT ''"),
        ("achievements", "progress", "REAL NOT NULL DEFAULT 0"),
        ("achievements", "unlocked", "TEXT"),
        ("progress", "updated", "TEXT NOT NULL DEFAULT ''"),
    ];
    for (table, column, decl) in patches {
        ensure_column(conn, table, column, decl);
    }
    conn.pragma_update(None, "user_version", 6)?;
    Ok(())
}

fn has_column(conn: &Connection, table: &str, column: &str) -> bool {
    let Ok(mut stmt) = conn.prepare(&format!("PRAGMA table_info({table})")) else {
        return false;
    };
    let Ok(rows) = stmt.query_map([], |r| r.get::<_, String>(1)) else {
        return false;
    };
    let found = rows.flatten().any(|name| name.eq_ignore_ascii_case(column));
    found
}

fn ensure_column(conn: &Connection, table: &str, column: &str, decl: &str) {
    if !has_column(conn, table, column) {
        let _ = conn.execute_batch(&format!("ALTER TABLE {table} ADD COLUMN {column} {decl}"));
    }
}

// ------------------------------------------------------------------ catalogue
fn sync_builtin(conn: &Connection) -> rusqlite::Result<()> {
    let d = crate::data::data();
    let ts = stamp();
    for e in &d.exercises.items {
        conn.execute(
            "INSERT OR REPLACE INTO exercises(id,name,category,difficulty,kind,default_sets,
             default_amount,default_rest,instructions,skill_id,anim,builtin)
             VALUES(?,?,?,?,?,?,?,?,?,?,?,1)",
            params![
                e.id,
                e.name,
                e.category,
                e.difficulty as i64,
                e.kind,
                e.default_sets,
                e.default_amount,
                e.default_rest,
                e.instructions,
                e.skill_id,
                e.anim
            ],
        )?;
        if let Some(det) = d.detail(&e.id) {
            conn.execute(
                "INSERT OR REPLACE INTO exercise_details(exercise_id,muscles,technique,mistakes,tips,
                 easier,harder,prerequisites,related,category,difficulty,equipment,updated)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                params![
                    e.id,
                    det.muscles.join(", "),
                    e.instructions,
                    det.mistakes.join(" | "),
                    det.tips.join(" | "),
                    det.easier.join(", "),
                    det.harder.join(", "),
                    det.prereq.join(", "),
                    det.related.join(", "),
                    e.category,
                    e.difficulty as i64,
                    det.equipment,
                    ts
                ],
            )?;
        }
    }
    Ok(())
}

// ------------------------------------------------------------------- workouts
#[derive(Clone)]
pub struct Entry {
    pub exercise_id: String,
    pub sets: i64,
    pub reps: i64,
    pub hold_sec: i64,
    pub rest_sets: i64,
    pub rest_after: i64,
}

#[derive(Clone)]
pub struct WorkoutFull {
    pub id: Option<i64>,
    pub name: String,
    pub description: String,
    pub style: String,
    pub entries: Vec<Entry>,
}

#[derive(Clone)]
pub struct WorkoutRow {
    pub id: i64,
    pub name: String,
    pub description: String,
    pub style: String,
    pub count: i64,
}

pub fn workouts(conn: &Connection) -> Vec<WorkoutRow> {
    let mut stmt = conn
        .prepare("SELECT w.id, w.name, w.description, w.style, (SELECT COUNT(*) FROM workout_exercises x WHERE x.workout_id=w.id) FROM workouts w ORDER BY LOWER(w.name)")
        .unwrap();
    stmt.query_map([], |r| {
        Ok(WorkoutRow {
            id: r.get(0)?,
            name: r.get(1)?,
            description: r.get(2)?,
            style: r.get(3)?,
            count: r.get(4)?,
        })
    })
    .unwrap()
    .filter_map(|r| r.ok())
    .collect()
}

pub fn workout(conn: &Connection, id: i64) -> Option<WorkoutFull> {
    let (name, description, style) = conn
        .query_row("SELECT name, description, style FROM workouts WHERE id=?", params![id], |r| {
            Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?, r.get::<_, String>(2)?))
        })
        .optional()
        .ok()??;
    let mut stmt = conn
        .prepare("SELECT exercise_id, sets, reps, hold_sec, rest_sets, rest_after FROM workout_exercises WHERE workout_id=? ORDER BY position")
        .unwrap();
    let entries = stmt
        .query_map(params![id], |r| {
            Ok(Entry {
                exercise_id: r.get(0)?,
                sets: r.get(1)?,
                reps: r.get(2)?,
                hold_sec: r.get(3)?,
                rest_sets: r.get(4)?,
                rest_after: r.get(5)?,
            })
        })
        .unwrap()
        .filter_map(|r| r.ok())
        .collect();
    Some(WorkoutFull { id: Some(id), name, description, style, entries })
}

pub fn save_workout(conn: &Connection, w: &WorkoutFull) -> rusqlite::Result<i64> {
    let ts = stamp();
    let id = match w.id {
        Some(id) => {
            conn.execute(
                "UPDATE workouts SET name=?, description=?, style=?, updated=? WHERE id=?",
                params![w.name, w.description, w.style, ts, id],
            )?;
            conn.execute("DELETE FROM workout_exercises WHERE workout_id=?", params![id])?;
            id
        }
        None => {
            conn.execute(
                "INSERT INTO workouts(name,description,style,created,updated) VALUES(?,?,?,?,?)",
                params![w.name, w.description, w.style, ts, ts],
            )?;
            conn.last_insert_rowid()
        }
    };
    for (pos, e) in w.entries.iter().enumerate() {
        conn.execute(
            "INSERT INTO workout_exercises(workout_id,position,exercise_id,sets,reps,hold_sec,rest_sets,rest_after,note)
             VALUES(?,?,?,?,?,?,?,?, '')",
            params![id, pos as i64, e.exercise_id, e.sets, e.reps, e.hold_sec, e.rest_sets, e.rest_after],
        )?;
    }
    Ok(id)
}

pub fn delete_workout(conn: &Connection, id: i64) {
    let _ = conn.execute("DELETE FROM workouts WHERE id=?", params![id]);
}

fn seed_examples(conn: &Connection) -> rusqlite::Result<()> {
    let count: i64 = conn.query_row("SELECT COUNT(*) FROM workouts", [], |r| r.get(0))?;
    if count > 0 {
        return Ok(());
    }
    let examples: [(&str, &str, &str, &[(&str, i64, i64)]); 6] = [
        ("Push Day", "Chest, shoulders and triceps.", "strength",
         &[("pushup", 4, 10), ("pike_pushup", 3, 8), ("dip", 3, 6), ("diamond_pushup", 3, 8)]),
        ("Pull Day", "Back and biceps.", "strength",
         &[("pullup", 4, 6), ("australian_row", 3, 10), ("chinup", 3, 5), ("scap_pull", 3, 10), ("dead_hang", 3, 30)]),
        ("Legs & Core", "Lower body and trunk.", "endurance",
         &[("squat", 4, 15), ("bulgarian", 3, 8), ("glute_bridge", 3, 15), ("calf_raise", 3, 15),
           ("hanging_knee_raise", 3, 10), ("hollow_hold", 3, 25), ("plank", 3, 40)]),
        ("Cardio", "Bodyweight cardio and metabolic conditioning.", "endurance",
         &[("burpee", 3, 8), ("jump_squat", 3, 10), ("tuck_jump", 3, 6), ("plank", 2, 30)]),
        ("Run", "Steady-pace aerobic run (log it on the Running page).", "endurance", &[("run", 1, 1200)]),
        ("Skill Training", "Low-fatigue practice of handstands, levers and planche.", "skill",
         &[("wall_handstand", 5, 30), ("crow_pose", 4, 15), ("tuck_front_lever", 4, 8),
           ("planche_lean", 4, 15), ("skin_the_cat", 3, 4), ("tuck_l_sit", 4, 15)]),
    ];
    let d = crate::data::data();
    for (name, desc, style, items) in examples {
        let mut entries = Vec::new();
        for (ex_id, sets, amount) in items {
            let Some(ex) = d.exercise(ex_id) else { continue };
            entries.push(Entry {
                exercise_id: ex_id.to_string(),
                sets: *sets,
                reps: if ex.kind == "reps" { *amount } else { 0 },
                hold_sec: if ex.kind == "hold" { *amount } else { 0 },
                rest_sets: if style == "strength" { 90 } else { 45 },
                rest_after: if style == "strength" { 120 } else { 60 },
            });
        }
        let _ = save_workout(
            conn,
            &WorkoutFull {
                id: None,
                name: name.to_string(),
                description: desc.to_string(),
                style: style.to_string(),
                entries,
            },
        );
    }
    Ok(())
}

// ------------------------------------------------------------------- progress
pub fn progress_map(conn: &Connection) -> HashMap<String, String> {
    let mut stmt = conn.prepare("SELECT skill_id, status FROM progress").unwrap();
    stmt.query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?)))
        .unwrap()
        .filter_map(|r| r.ok())
        .collect()
}

pub fn set_status(conn: &Connection, skill_id: &str, status: Option<&str>) {
    let _ = match status {
        Some(s) => conn.execute(
            "INSERT OR REPLACE INTO progress(skill_id,status,updated) VALUES(?,?,?)",
            params![skill_id, s, stamp()],
        ),
        None => conn.execute("DELETE FROM progress WHERE skill_id=?", params![skill_id]),
    };
}

pub fn bests(conn: &Connection) -> HashMap<String, (f64, String)> {
    let mut out = HashMap::new();
    let mut stmt = conn.prepare("SELECT skill_id, value, logged FROM records ORDER BY value ASC, id ASC").unwrap();
    let rows = stmt
        .query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, f64>(1)?, r.get::<_, String>(2)?)))
        .unwrap();
    for row in rows.flatten() {
        out.insert(row.0, (row.1, row.2));
    }
    out
}

pub fn add_record(conn: &Connection, skill_id: &str, value: f64) {
    let _ = conn.execute(
        "INSERT INTO records(skill_id, value, logged) VALUES(?,?,?)",
        params![skill_id, value, today()],
    );
}

pub fn performances(conn: &Connection, exercise_id: &str) -> Vec<(String, f64)> {
    let mut stmt = conn
        .prepare("SELECT logged, value FROM performances WHERE exercise_id=? ORDER BY logged, id")
        .unwrap();
    stmt.query_map(params![exercise_id], |r| Ok((r.get::<_, String>(0)?, r.get::<_, f64>(1)?)))
        .unwrap()
        .filter_map(|r| r.ok())
        .collect()
}

/// Add a performance and pay XP for a new personal best (once per exercise/day).
fn add_performance(conn: &Connection, d: &Data, exercise_id: &str, value: f64, source: &str, session_id: Option<i64>) {
    if value <= 0.0 {
        return;
    }
    let previous: f64 = conn
        .query_row("SELECT COALESCE(MAX(value),0) FROM performances WHERE exercise_id=?", params![exercise_id], |r| r.get(0))
        .unwrap_or(0.0);
    let _ = conn.execute(
        "INSERT INTO performances(exercise_id,value,logged,source,session_id,note) VALUES(?,?,?,?,?, '')",
        params![exercise_id, value, today(), source, session_id],
    );
    if previous > 0.0 && value > previous {
        if let Some(ex) = d.exercise(exercise_id) {
            let xp = d.prog.xp_pr.get(&ex.difficulty.to_string()).copied().unwrap_or(10);
            award(
                conn,
                &format!("pr:{}:{}", exercise_id, today()),
                xp,
                &format!("Personal record: {} {} {}", ex.name, logic::fmt_num(value), if ex.kind == "reps" { "reps" } else { "s" }),
                "record",
            );
        }
    }
}

// ------------------------------------------------------------------- sessions
#[derive(Clone)]
pub struct SetRow {
    pub id: i64,
    pub ex_pos: i64,
    pub set_idx: i64,
    pub exercise_id: String,
    pub exercise_name: String,
    pub kind: String,
    pub reps: i64,
    pub hold: i64,
    pub rest_sec: i64,
    pub done: bool,
}

#[derive(Clone)]
pub struct SessionRow {
    pub id: i64,
    pub workout_name: String,
    pub session_date: String,
    pub elapsed_sec: i64,
    pub distance_m: i64,
    pub sets_total: i64,
    pub sets_done: i64,
    pub reps_total: i64,
    pub hold_total: i64,
}

pub fn active_session(conn: &Connection) -> Option<(i64, String, i64, String)> {
    conn.query_row(
        "SELECT id, workout_name, elapsed_sec, started FROM sessions WHERE status='active' ORDER BY id DESC LIMIT 1",
        [],
        |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?)),
    )
    .optional()
    .ok()?
}

pub fn start_session(conn: &Connection, w: &WorkoutFull) -> Option<i64> {
    if active_session(conn).is_some() {
        return None;
    }
    let ts = stamp();
    conn.execute(
        "INSERT INTO sessions(workout_id,workout_name,session_date,started,status,elapsed_sec,state_json,entry_id,distance_m)
         VALUES(?,?,?,?, 'active',0,'{}',NULL,0)",
        params![w.id, w.name, today(), ts],
    )
    .ok()?;
    let sid = conn.last_insert_rowid();
    let last = w.entries.len().saturating_sub(1);
    for (pos, e) in w.entries.iter().enumerate() {
        let Some(ex) = crate::data::data().exercise(&e.exercise_id) else { continue };
        for i in 0..e.sets {
            let last_set = i == e.sets - 1;
            let mut rest = if last_set { e.rest_after } else { e.rest_sets };
            if pos == last && last_set {
                rest = 0;
            }
            let _ = conn.execute(
                "INSERT INTO session_sets(session_id,ex_pos,set_idx,exercise_id,exercise_name,kind,
                 target_reps,target_hold,reps,hold,rest_sec,note,done)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?, '',0)",
                params![sid, pos as i64, i, e.exercise_id, ex.name, ex.kind, e.reps, e.hold_sec, e.reps, e.hold_sec, rest],
            );
        }
    }
    Some(sid)
}

pub fn session_sets(conn: &Connection, sid: i64) -> Vec<SetRow> {
    let mut stmt = conn
        .prepare("SELECT id, ex_pos, set_idx, exercise_id, exercise_name, kind, reps, hold, rest_sec, done
                  FROM session_sets WHERE session_id=? ORDER BY ex_pos, set_idx")
        .unwrap();
    stmt.query_map(params![sid], |r| {
        Ok(SetRow {
            id: r.get(0)?,
            ex_pos: r.get(1)?,
            set_idx: r.get(2)?,
            exercise_id: r.get(3)?,
            exercise_name: r.get(4)?,
            kind: r.get(5)?,
            reps: r.get(6)?,
            hold: r.get(7)?,
            rest_sec: r.get(8)?,
            done: r.get::<_, i64>(9)? != 0,
        })
    })
    .unwrap()
    .filter_map(|r| r.ok())
    .collect()
}

pub fn update_set(conn: &Connection, set_id: i64, reps: i64, hold: i64, done: bool) {
    let _ = conn.execute(
        "UPDATE session_sets SET reps=?, hold=?, done=?, done_at=? WHERE id=?",
        params![reps, hold, if done { 1 } else { 0 }, if done { Some(stamp()) } else { None }, set_id],
    );
}

pub fn discard_session(conn: &Connection, sid: i64) {
    let _ = conn.execute("DELETE FROM sessions WHERE id=?", params![sid]);
}

pub fn summary(conn: &Connection, sid: i64) -> Option<SessionRow> {
    conn.query_row(
        "SELECT s.id, s.workout_name, s.session_date, s.elapsed_sec, s.distance_m,
            COUNT(ss.id), COALESCE(SUM(ss.done),0),
            COALESCE(SUM(CASE WHEN ss.done=1 AND ss.kind='reps' THEN ss.reps ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN ss.done=1 AND ss.kind='hold' THEN ss.hold ELSE 0 END),0)
         FROM sessions s LEFT JOIN session_sets ss ON ss.session_id=s.id WHERE s.id=? GROUP BY s.id",
        params![sid],
        |r| {
            Ok(SessionRow {
                id: r.get(0)?,
                workout_name: r.get(1)?,
                session_date: r.get(2)?,
                elapsed_sec: r.get(3)?,
                distance_m: r.get(4)?,
                sets_total: r.get(5)?,
                sets_done: r.get(6)?,
                reps_total: r.get(7)?,
                hold_total: r.get(8)?,
            })
        },
    )
    .optional()
    .ok()?
}

/// Complete a session: records the best set of every exercise, updates the skill
/// records and returns a one-line summary for the toast.
pub fn finish_session(conn: &Connection, d: &Data, sid: i64, elapsed: i64) -> Option<String> {
    let sets = session_sets(conn, sid);
    if !sets.iter().any(|s| s.done) {
        discard_session(conn, sid);
        return None;
    }
    let mut best: HashMap<String, f64> = HashMap::new();
    for s in sets.iter().filter(|s| s.done) {
        let v = if s.kind == "reps" { s.reps as f64 } else { s.hold as f64 };
        let slot = best.entry(s.exercise_id.clone()).or_insert(0.0);
        if v > *slot {
            *slot = v;
        }
    }
    for (ex_id, value) in &best {
        add_performance(conn, d, ex_id, *value, "session", Some(sid));
        if let Some(ex) = d.exercise(ex_id) {
            if let Some(skill_id) = &ex.skill_id {
                let current = conn
                    .query_row("SELECT COALESCE(MAX(value),0) FROM records WHERE skill_id=?", params![skill_id], |r| r.get::<_, f64>(0))
                    .unwrap_or(0.0);
                if *value > current {
                    add_record(conn, skill_id, *value);
                }
            }
        }
    }
    let _ = conn.execute(
        "UPDATE sessions SET status='completed', ended=?, elapsed_sec=? WHERE id=?",
        params![stamp(), elapsed, sid],
    );
    let done = sets.iter().filter(|s| s.done).count();
    Some(format!("Workout saved – {done} of {} sets", sets.len()))
}

pub fn history(conn: &Connection) -> Vec<SessionRow> {
    let Ok(mut stmt) = conn.prepare(
        "SELECT s.id, s.workout_name, s.session_date, s.elapsed_sec, s.distance_m,
                COUNT(ss.id), COALESCE(SUM(ss.done),0),
                COALESCE(SUM(CASE WHEN ss.done=1 AND ss.kind='reps' THEN ss.reps ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN ss.done=1 AND ss.kind='hold' THEN ss.hold ELSE 0 END),0)
             FROM sessions s LEFT JOIN session_sets ss ON ss.session_id=s.id
             WHERE s.status='completed' GROUP BY s.id ORDER BY s.started DESC",
    ) else {
        return Vec::new();
    };
    let rows = stmt.query_map([], |r| {
        Ok(SessionRow {
            id: r.get(0)?,
            workout_name: r.get(1)?,
            session_date: r.get(2)?,
            elapsed_sec: r.get(3)?,
            distance_m: r.get(4)?,
            sets_total: r.get(5)?,
            sets_done: r.get(6)?,
            reps_total: r.get(7)?,
            hold_total: r.get(8)?,
        })
    });
    match rows {
        Ok(rows) => rows.filter_map(|r| r.ok()).collect(),
        Err(_) => Vec::new(),
    }
}

pub fn delete_session(conn: &Connection, sid: i64) {
    let _ = conn.execute("DELETE FROM sessions WHERE id=?", params![sid]);
}

// ----------------------------------------------------------------------- runs
pub fn log_run(conn: &Connection, distance_m: i64, duration_s: i64) -> rusqlite::Result<i64> {
    let ts = stamp();
    conn.execute(
        "INSERT INTO sessions(workout_id,workout_name,session_date,started,ended,status,elapsed_sec,state_json,entry_id,distance_m)
         VALUES(NULL,'Run',?,?,?,'completed',?,'{}',NULL,?)",
        params![today(), ts, ts, duration_s, distance_m],
    )?;
    Ok(conn.last_insert_rowid())
}

pub fn runs(conn: &Connection) -> Vec<SessionRow> {
    history(conn).into_iter().filter(|r| r.distance_m > 0).collect()
}

pub struct RunTotals {
    pub count: i64,
    pub distance_m: i64,
    pub seconds: i64,
    pub average: Option<f64>,
    pub best: Option<f64>,
}

pub fn run_totals(conn: &Connection) -> RunTotals {
    let (count, distance_m, seconds): (i64, i64, i64) = conn
        .query_row(
            "SELECT COUNT(*), COALESCE(SUM(distance_m),0), COALESCE(SUM(elapsed_sec),0)
             FROM sessions WHERE status='completed' AND distance_m>0",
            [],
            |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
        )
        .unwrap_or((0, 0, 0));
    let best: Option<f64> = conn
        .query_row(
            "SELECT MIN(elapsed_sec * 1000.0 / distance_m) FROM sessions
             WHERE status='completed' AND distance_m>0 AND elapsed_sec>0",
            [],
            |r| r.get(0),
        )
        .optional()
        .unwrap_or(None);
    RunTotals {
        count,
        distance_m,
        seconds,
        average: logic::pace_of(distance_m, seconds),
        best,
    }
}

// ------------------------------------------------------------------------ xp
pub fn total_xp(conn: &Connection) -> i64 {
    conn.query_row("SELECT COALESCE(SUM(amount),0) FROM xp_events", [], |r| r.get(0)).unwrap_or(0)
}

pub fn award(conn: &Connection, key: &str, amount: i64, reason: &str, category: &str) -> bool {
    if amount <= 0 {
        return false;
    }
    let changed = conn
        .execute(
            "INSERT OR IGNORE INTO xp_events(key,amount,reason,category,earned_on,awarded) VALUES(?,?,?,?,?,?)",
            params![key, amount, reason, category, today(), stamp()],
        )
        .unwrap_or(0);
    changed > 0
}

pub fn xp_breakdown(conn: &Connection) -> HashMap<String, i64> {
    let mut out = HashMap::new();
    let mut stmt = conn.prepare("SELECT category, SUM(amount) FROM xp_events GROUP BY category").unwrap();
    let rows = stmt.query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, i64>(1)?))).unwrap();
    for (k, v) in rows.flatten() {
        out.insert(k, v);
    }
    out
}

pub fn achievement_state(conn: &Connection) -> HashMap<String, (f64, Option<String>)> {
    let mut out = HashMap::new();
    let mut stmt = conn.prepare("SELECT id, progress, unlocked FROM achievements").unwrap();
    let rows = stmt
        .query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, f64>(1)?, r.get::<_, Option<String>>(2)?)))
        .unwrap();
    for (id, progress, unlocked) in rows.flatten() {
        out.insert(id, (progress, unlocked));
    }
    out
}

// ------------------------------------------------------------------ settings
pub fn get_setting(conn: &Connection, key: &str, default: &str) -> String {
    conn.query_row("SELECT value FROM settings WHERE key=?", params![key], |r| r.get::<_, String>(0))
        .optional()
        .unwrap_or(None)
        .unwrap_or_else(|| default.to_string())
}

pub fn set_setting(conn: &Connection, key: &str, value: &str) {
    let _ = conn.execute(
        "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
        params![key, value],
    );
}

// ------------------------------------------------------------------ analytics
pub struct Stats {
    pub sessions: i64,
    pub seconds: i64,
    pub sets: i64,
    pub reps: i64,
    pub hold: i64,
    pub this_week: i64,
    pub streak: i64,
    pub bests_by_exercise: HashMap<String, f64>,
    pub trained: HashSet<String>,
    pub max_hold: f64,
}

pub fn stats(conn: &Connection) -> Stats {
    let hist = history(conn);
    let sessions = hist.len() as i64;
    let seconds = hist.iter().map(|r| r.elapsed_sec).sum();
    let sets: i64 = hist.iter().map(|r| r.sets_done).sum();
    let reps: i64 = hist.iter().map(|r| r.reps_total).sum();
    let hold: i64 = hist.iter().map(|r| r.hold_total).sum();

    let mut dates: Vec<chrono::NaiveDate> = hist
        .iter()
        .filter_map(|r| chrono::NaiveDate::parse_from_str(&r.session_date, "%Y-%m-%d").ok())
        .collect();
    dates.sort();
    dates.dedup();
    let today = Local::now().date_naive();
    let monday = today - chrono::Duration::days(today.weekday().num_days_from_monday() as i64);
    let this_week = dates.iter().filter(|d| **d >= monday).count() as i64;
    let mut streak = 0i64;
    let mut cursor = if dates.contains(&today) { today } else { today - chrono::Duration::days(1) };
    while dates.contains(&cursor) {
        streak += 1;
        cursor -= chrono::Duration::days(1);
    }

    let mut bests: HashMap<String, f64> = HashMap::new();
    let mut stmt = conn.prepare("SELECT exercise_id, MAX(value) FROM performances GROUP BY exercise_id").unwrap();
    if let Ok(rows) = stmt.query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, f64>(1)?))) {
        for (ex, v) in rows.flatten() {
            bests.insert(ex, v);
        }
    }
    let mut trained = HashSet::new();
    let mut stmt = conn.prepare("SELECT DISTINCT exercise_id FROM performances").unwrap();
    if let Ok(rows) = stmt.query_map([], |r| r.get::<_, String>(0)) {
        for ex in rows.flatten() {
            trained.insert(ex);
        }
    }
    let max_hold = conn
        .query_row(
            "SELECT COALESCE(MAX(p.value),0) FROM performances p JOIN exercises e ON e.id=p.exercise_id WHERE e.kind='hold'",
            [],
            |r| r.get::<_, f64>(0),
        )
        .unwrap_or(0.0);

    Stats { sessions, seconds, sets, reps, hold, this_week, streak, bests_by_exercise: bests, trained, max_hold }
}

pub fn metrics(conn: &Connection, d: &Data, st: &Stats) -> HashMap<String, f64> {
    let mut m: HashMap<String, f64> = HashMap::new();
    let hist = history(conn);
    let qualifying: Vec<&SessionRow> = hist
        .iter()
        .filter(|r| r.elapsed_sec >= d.prog.min_session_seconds)
        .filter(|r| (r.sets_done as f64) >= (r.sets_total as f64 * d.prog.min_sets_share).max(1.0))
        .collect();
    m.insert("workouts".into(), qualifying.len() as f64);
    m.insert("scheduled".into(), 0.0);
    m.insert("sets".into(), st.sets as f64);
    m.insert("reps".into(), st.reps as f64);
    m.insert("hold_seconds".into(), st.hold as f64);
    let dates: Vec<chrono::NaiveDate> = qualifying
        .iter()
        .filter_map(|r| chrono::NaiveDate::parse_from_str(&r.session_date, "%Y-%m-%d").ok())
        .collect();
    let mut weeks: HashMap<chrono::NaiveDate, i64> = HashMap::new();
    for day in &dates {
        let monday = *day - chrono::Duration::days(day.weekday().num_days_from_monday() as i64);
        *weeks.entry(monday).or_insert(0) += 1;
    }
    m.insert("week_best".into(), weeks.values().copied().max().unwrap_or(0) as f64);
    let mut months: HashMap<(i32, u32), i64> = HashMap::new();
    for day in &dates {
        *months.entry((day.year(), day.month())).or_insert(0) += 1;
    }
    m.insert("month_best".into(), months.values().copied().max().unwrap_or(0) as f64);

    let mut uniq = dates.clone();
    uniq.sort();
    uniq.dedup();
    let mut best_run = 0i64;
    let mut run = 0i64;
    let mut prev: Option<chrono::NaiveDate> = None;
    for day in &uniq {
        run = match prev {
            Some(p) if (*day - p).num_days() == 1 => run + 1,
            _ => 1,
        };
        best_run = best_run.max(run);
        prev = Some(*day);
    }
    m.insert("streak_days".into(), best_run as f64);

    let mut week_list: Vec<chrono::NaiveDate> = weeks.iter().filter(|(_, n)| **n >= 3).map(|(w, _)| *w).collect();
    week_list.sort();
    let mut best_weeks = 0i64;
    let mut wrun = 0i64;
    let mut wprev: Option<chrono::NaiveDate> = None;
    for w in &week_list {
        wrun = match wprev {
            Some(p) if (*w - p).num_days() == 7 => wrun + 1,
            _ => 1,
        };
        best_weeks = best_weeks.max(wrun);
        wprev = Some(*w);
    }
    m.insert("week_streak".into(), best_weeks as f64);

    let progress = progress_map(conn);
    let done: HashSet<String> = progress
        .iter()
        .filter(|(_, s)| s.as_str() == "completed")
        .map(|(k, _)| k.clone())
        .collect();
    m.insert("skills_done".into(), done.len() as f64);
    for sid in &done {
        if let Some(skill) = d.skill(sid) {
            m.insert(format!("skill:{}", sid), 1.0);
            *m.entry(format!("skills_tier:{}", skill.tier)).or_insert(0.0) += 1.0;
            *m.entry(format!("skills_cat:{}", skill.category)).or_insert(0.0) += 1.0;
        }
    }
    m.insert("exercises_trained".into(), st.trained.len() as f64);
    let cats: HashSet<&str> = st
        .trained
        .iter()
        .filter_map(|id| d.exercise(id).map(|e| e.category.as_str()))
        .collect();
    m.insert("categories_trained".into(), cats.len() as f64);
    m.insert("max_hold".into(), st.max_hold);

    // ranks
    let tracks = logic::build_tracks(d);
    let mut singles_ge = vec![0i64; 9];
    for track in tracks.iter().filter(|t| t.kind != "line") {
        let res = logic::evaluate(track, &st.bests_by_exercise, &done, d.ranks.max_rank);
        for n in 1..=res.rank {
            singles_ge[n] += 1;
        }
    }
    for n in 1..=d.ranks.max_rank {
        m.insert(format!("ranks_ge:{}", n), singles_ge[n] as f64);
    }
    m
}

/// Credit session, skill, rank and achievement XP. Returns the newly unlocked
/// achievements (name, xp) so the UI can announce them.
pub fn sync_xp(conn: &Connection, d: &Data) -> Vec<(String, i64)> {
    let st = stats(conn);
    let hist = history(conn);
    let qualifying: Vec<&SessionRow> = hist
        .iter()
        .filter(|r| r.elapsed_sec >= d.prog.min_session_seconds)
        .filter(|r| (r.sets_done as f64) >= (r.sets_total as f64 * d.prog.min_sets_share).max(1.0))
        .collect();
    let mut per_day: HashMap<String, i64> = HashMap::new();
    for r in qualifying {
        let count = per_day.entry(r.session_date.clone()).or_insert(0);
        *count += 1;
        if *count > d.prog.session_daily_cap {
            continue;
        }
        award(conn, &format!("workout:{}", r.id), d.prog.xp_workout, &format!("Workout completed: {}", r.workout_name), "workout");
        let sets = r.sets_done.min(d.prog.max_set_xp);
        award(conn, &format!("sets:{}", r.id), sets * d.prog.xp_per_set, &format!("{} sets completed", r.sets_done), "set");
    }

    let progress = progress_map(conn);
    let done: HashSet<String> = progress.iter().filter(|(_, s)| s.as_str() == "completed").map(|(k, _)| k.clone()).collect();
    for sid in &done {
        if let Some(skill) = d.skill(sid) {
            let xp = d.prog.xp_skill_done.get(skill.tier).copied().unwrap_or(10);
            award(conn, &format!("skill_done:{}", sid), xp, &format!("Skill completed: {}", skill.name), "skill");
        }
    }
    for skill in &d.skills.items {
        if !skill.prereqs.is_empty() && skill.prereqs.iter().all(|p| done.contains(p)) {
            let xp = d.prog.xp_skill_unlock.get(skill.tier).copied().unwrap_or(5);
            award(conn, &format!("skill_unlock:{}", skill.id), xp, &format!("Skill unlocked: {}", skill.name), "skill");
        }
    }

    for track in logic::build_tracks(d) {
        let res = logic::evaluate(&track, &st.bests_by_exercise, &done, d.ranks.max_rank);
        for rank in 1..=res.rank {
            let base = d.prog.xp_rank.get(rank).copied().unwrap_or(0) as f64;
            let xp = (base * (1.0 + 0.25 * track.difficulty as f64)).round() as i64;
            award(
                conn,
                &format!("rank:{}:{}", track.id, rank),
                xp.max(1),
                &format!("Rank reached: {} → {}", track.name, d.rank_name(rank)),
                "rank",
            );
        }
    }

    // achievements
    let mut unlocked_now = Vec::new();
    let mut m = metrics(conn, d, &st);
    let level = logic::level_info(d, total_xp(conn));
    m.insert("level".into(), level.level as f64);
    let prs: i64 = conn
        .query_row("SELECT COUNT(*) FROM xp_events WHERE category='record'", [], |r| r.get(0))
        .unwrap_or(0);
    m.insert("prs".into(), prs as f64);
    let state = achievement_state(conn);
    m.insert(
        "achievements".into(),
        state.values().filter(|(_, u)| u.is_some()).count() as f64,
    );

    for a in &d.achievements.items {
        let value = m.get(&a.metric).copied().unwrap_or(0.0);
        let unlocked = state.get(&a.id).and_then(|(_, u)| u.clone());
        let mut unlocked = unlocked;
        if unlocked.is_none() && value >= a.target {
            unlocked = Some(today());
            award(conn, &format!("ach:{}", a.id), a.xp, &format!("Achievement: {}", a.name), "achievement");
            unlocked_now.push((a.name.clone(), a.xp));
        }
        let _ = conn.execute(
            "INSERT OR REPLACE INTO achievements(id,progress,unlocked) VALUES(?,?,?)",
            params![a.id, value.min(a.target), unlocked],
        );
    }
    unlocked_now
}

#[cfg(test)]
mod tests {
    #[test]
    fn migrates_legacy_sessions_table() {
        let conn = rusqlite::Connection::open_in_memory().unwrap();
        // a pre-1.1 database: no distance_m / state_json / entry_id
        conn.execute_batch(
            "CREATE TABLE sessions(id INTEGER PRIMARY KEY AUTOINCREMENT, workout_id INTEGER,
                workout_name TEXT NOT NULL, session_date TEXT, started TEXT, ended TEXT,
                status TEXT NOT NULL);
             INSERT INTO sessions(workout_name,session_date,started,status)
                VALUES('Old','2026-01-01','2026-01-01T10:00:00','completed');",
        )
        .unwrap();
        super::migrate(&conn).unwrap();
        for col in ["distance_m", "state_json", "entry_id", "elapsed_sec"] {
            assert!(super::has_column(&conn, "sessions", col), "missing {col}");
        }
        let rows = super::history(&conn);
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0].distance_m, 0);
    }

    use super::*;

    fn mem() -> Connection {
        let conn = Connection::open_in_memory().unwrap();
        migrate(&conn).unwrap();
        sync_builtin(&conn).unwrap();
        seed_examples(&conn).unwrap();
        conn
    }

    #[test]
    fn schema_seeds_and_runs() {
        let conn = mem();
        assert!(workouts(&conn).len() >= 6);
        let sid = log_run(&conn, 5000, 1500).unwrap();
        let totals = run_totals(&conn);
        assert_eq!(totals.count, 1);
        assert!((totals.average.unwrap() - 300.0).abs() < 0.01);
        assert_eq!(totals.best.unwrap(), 300.0);
        assert_eq!(summary(&conn, sid).unwrap().distance_m, 5000);
        delete_session(&conn, sid);
        assert_eq!(run_totals(&conn).count, 0);
    }

    #[test]
    fn session_lifecycle_awards_xp() {
        let conn = mem();
        let list = workouts(&conn);
        let push = list.iter().find(|w| w.name == "Push Day").unwrap().id;
        let full = workout(&conn, push).unwrap();
        let sid = start_session(&conn, &full).unwrap();
        let sets = session_sets(&conn, sid);
        assert!(!sets.is_empty());
        for s in &sets {
            update_set(&conn, s.id, s.reps.max(1), s.hold.max(1), true);
        }
        let msg = finish_session(&conn, crate::data::data(), sid, 900).unwrap();
        assert!(msg.contains("sets"));
        assert_eq!(history(&conn).len(), 1);
        sync_xp(&conn, crate::data::data());
        assert!(total_xp(&conn) > 0);
        assert!(!achievement_state(&conn).is_empty());
    }

    #[test]
    fn layout_ranks_and_metrics() {
        let d = crate::data::data();
        assert_eq!(logic::layout(d).pos.len(), d.skills.items.len());
        let tracks = logic::build_tracks(d);
        assert!(tracks.len() > 50);
        let mut bests = HashMap::new();
        bests.insert("pullup".to_string(), 12.0);
        let track = tracks.iter().find(|t| t.exercise_id == "pullup").unwrap();
        let res = logic::evaluate(track, &bests, &HashSet::new(), d.ranks.max_rank);
        assert!(res.rank >= 1, "12 pull-ups should earn a rank, got {}", res.rank);
        assert!(logic::level_info(d, 1000).level >= 3);
    }
}
