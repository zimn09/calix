//! Workouts: build a workout, then run it set by set. Finishing a session
//! stores it, records your best sets and pays XP.
use crate::app::{App, WorkoutEditor};
use crate::db;
use crate::logic::fmt_clock;
use crate::theme;
use eframe::egui::{self, Color32, RichText, ScrollArea, Ui, Vec2};
use std::time::{Duration, Instant};

enum Action {
    Select(i64),
    New,
    Delete(i64),
    Save,
    Start(i64),
    AddExercise(String),
    RemoveEntry(usize),
}

impl App {
    pub fn page_workouts(&mut self, ui: &mut Ui) {
        let t = self.theme.clone();
        if self.workouts.session_id.is_none() {
            if let Some((sid, _, elapsed, _)) = db::active_session(&self.conn) {
                self.workouts.session_id = Some(sid);
                self.workouts.session_sets = db::session_sets(&self.conn, sid);
                self.workouts.elapsed = elapsed;
                self.workouts.started = Some(Instant::now() - Duration::from_secs(elapsed.max(0) as u64));
            }
        }

        self.page_title(ui, "Workouts", "Build a workout, start it and tick off your sets");
        ui.add_space(6.0);

        if self.workouts.session_id.is_some() {
            self.session_runner(ui);
            return;
        }

        let workouts = db::workouts(&self.conn);
        let full = ui.available_size();
        let mut action: Option<Action> = None;

        ui.horizontal_top(|ui| {
            ui.allocate_ui_with_layout(Vec2::new(250.0, full.y), egui::Layout::top_down(egui::Align::Min), |ui| {
                ui.label(t.section("Your workouts"));
                ui.add_space(4.0);
                ScrollArea::vertical().id_source("workout-list").max_height(full.y - 60.0).show(ui, |ui| {
                    for w in &workouts {
                        let selected = self.workouts.chosen == Some(w.id);
                        let frame = egui::Frame::none()
                            .fill(if selected { theme::alpha(t.accent, 40) } else { t.surface2 })
                            .stroke(egui::Stroke::new(1.0, if selected { theme::alpha(t.accent, 130) } else { t.line }))
                            .rounding(t.radius)
                            .inner_margin(egui::Margin::symmetric(10, 8));
                        let resp = frame
                            .show(ui, |ui| {
                                ui.set_width(ui.available_width());
                                ui.label(RichText::new(&w.name).strong().color(t.text));
                                ui.label(t.dim(format!("{} exercises · {}", w.count, w.style)));
                            })
                            .response;
                        if resp.interact(egui::Sense::click()).clicked() {
                            action = Some(Action::Select(w.id));
                        }
                        ui.add_space(4.0);
                    }
                });
                if ui.button("+ New workout").clicked() {
                    action = Some(Action::New);
                }
            });
            ui.add_space(12.0);
            ui.allocate_ui_with_layout(
                Vec2::new(ui.available_width(), full.y),
                egui::Layout::top_down(egui::Align::Min),
                |ui| {
                    ScrollArea::vertical().id_source("workout-editor").auto_shrink([false, false]).show(ui, |ui| {
                        if self.workouts.editor.is_none() {
                            if let Some(w) = workouts.first() {
                                if let Some(full_w) = db::workout(&self.conn, w.id) {
                                    self.workouts.chosen = Some(w.id);
                                    self.workouts.editor = Some(WorkoutEditor {
                                        id: full_w.id,
                                        name: full_w.name,
                                        description: full_w.description,
                                        style: full_w.style,
                                        entries: full_w.entries,
                                    });
                                }
                            }
                        }
                        if let Some(editor) = self.workouts.editor.as_mut() {
                            theme::card(ui, &t, "Workout", |ui| {
                                ui.horizontal(|ui| {
                                    ui.label(t.dim("Name"));
                                    ui.add(egui::TextEdit::singleline(&mut editor.name).desired_width(200.0));
                                    ui.label(t.dim("Note"));
                                    ui.add(egui::TextEdit::singleline(&mut editor.description).desired_width(260.0));
                                });
                                ui.horizontal_wrapped(|ui| {
                                    ui.label(t.dim("Style"));
                                    for style in ["strength", "endurance", "skill", "fullbody"] {
                                        if theme::pill_button(ui, &t, style, editor.style == style).clicked() {
                                            editor.style = style.to_string();
                                        }
                                    }
                                });
                            });
                            ui.add_space(8.0);

                            theme::card(ui, &t, "Exercises", |ui| {
                                if editor.entries.is_empty() {
                                    ui.label(t.dim("Add an exercise below to start building."));
                                }
                                let mut remove = None;
                                for (i, entry) in editor.entries.iter_mut().enumerate() {
                                    let Some(ex) = self.d.exercise(&entry.exercise_id).cloned() else { continue };
                                    let color = theme::hex(self.d.exercise_category_color(&ex.category));
                                    ui.horizontal(|ui| {
                                        ui.label(RichText::new("●").color(color).size(10.0));
                                        ui.label(RichText::new(&ex.name).strong().color(t.text));
                                        ui.add_space(6.0);
                                        ui.label(t.dim("sets"));
                                        ui.add(egui::DragValue::new(&mut entry.sets).range(1..=20));
                                        if ex.kind == "reps" {
                                            ui.label(t.dim("reps"));
                                            ui.add(egui::DragValue::new(&mut entry.reps).range(0..=500));
                                        } else {
                                            ui.label(t.dim("hold s"));
                                            ui.add(egui::DragValue::new(&mut entry.hold_sec).range(0..=3600));
                                        }
                                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                            if ui.small_button("remove").clicked() {
                                                remove = Some(i);
                                            }
                                        });
                                    });
                                    ui.add_space(2.0);
                                }
                                if let Some(i) = remove {
                                    editor.entries.remove(i);
                                }
                                ui.add_space(6.0);
                                ui.separator();
                                ui.add_space(4.0);
                                ui.horizontal(|ui| {
                                    ui.label(t.dim("Add"));
                                    for cat in ["push", "pull", "core", "legs", "static", "balance", "skill", "explosive"] {
                                        let selected = self.workouts.pick_category == cat;
                                        let color = theme::hex(self.d.exercise_category_color(cat));
                                        let label = self.d.exercise_category_label(cat).to_string();
                                        let button = egui::Button::new(
                                            RichText::new(label).size(11.5 * t.scale).color(if selected { Color32::WHITE } else { color }),
                                        )
                                        .fill(if selected { theme::alpha(color, 55) } else { Color32::TRANSPARENT })
                                        .rounding(t.radius);
                                        if ui.add(button).clicked() {
                                            self.workouts.pick_category = cat.to_string();
                                        }
                                    }
                                });
                                ui.add_space(4.0);
                                ScrollArea::vertical().max_height(150.0).id_source("add-ex").show(ui, |ui| {
                                    for ex in self.d.exercises_in_category(&self.workouts.pick_category) {
                                        ui.horizontal(|ui| {
                                            ui.label(t.body(ex.name.clone()));
                                            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                                if ui.add(egui::Button::new("+ Add").small()).clicked() {
                                                    action = Some(Action::AddExercise(ex.id.clone()));
                                                }
                                            });
                                        });
                                    }
                                });
                            });
                            ui.add_space(8.0);

                            let editor_id = editor.id;
                            let can_start = self.workouts.chosen.is_some() && !editor.entries.is_empty();
                            ui.horizontal(|ui| {
                                if ui.add(egui::Button::new("Save workout")).clicked() {
                                    action = Some(Action::Save);
                                }
                                if ui.add_enabled(can_start, egui::Button::new("Start workout")).clicked() {
                                    if let Some(id) = self.workouts.chosen {
                                        action = Some(Action::Start(id));
                                    }
                                }
                                if let Some(id) = editor_id {
                                    if ui.button("Delete").clicked() {
                                        action = Some(Action::Delete(id));
                                    }
                                }
                            });
                        }
                    });
                },
            );
        });

        if let Some(action) = action {
            self.workout_action(action);
        }
    }

    fn workout_action(&mut self, action: Action) {
        match action {
            Action::Select(id) => {
                if let Some(w) = db::workout(&self.conn, id) {
                    self.workouts.chosen = Some(id);
                    self.workouts.editor = Some(WorkoutEditor {
                        id: w.id,
                        name: w.name,
                        description: w.description,
                        style: w.style,
                        entries: w.entries,
                    });
                }
            }
            Action::New => {
                self.workouts.chosen = None;
                self.workouts.editor = Some(WorkoutEditor {
                    id: None,
                    name: "New workout".into(),
                    description: String::new(),
                    style: "strength".into(),
                    entries: Vec::new(),
                });
            }
            Action::AddExercise(ex_id) => {
                if let (Some(editor), Some(ex)) = (self.workouts.editor.as_mut(), self.d.exercise(&ex_id).cloned()) {
                    editor.entries.push(db::Entry {
                        exercise_id: ex_id,
                        sets: ex.default_sets,
                        reps: if ex.kind == "reps" { ex.default_amount } else { 0 },
                        hold_sec: if ex.kind == "hold" { ex.default_amount } else { 0 },
                        rest_sets: 60,
                        rest_after: 90,
                    });
                }
            }
            Action::RemoveEntry(i) => {
                if let Some(editor) = self.workouts.editor.as_mut() {
                    if i < editor.entries.len() {
                        editor.entries.remove(i);
                    }
                }
            }
            Action::Save => {
                if let Some(editor) = self.workouts.editor.clone() {
                    let w = db::WorkoutFull {
                        id: editor.id,
                        name: editor.name.clone(),
                        description: editor.description.clone(),
                        style: editor.style.clone(),
                        entries: editor.entries.clone(),
                    };
                    match db::save_workout(&self.conn, &w) {
                        Ok(id) => {
                            self.workouts.chosen = Some(id);
                            if let Some(e) = self.workouts.editor.as_mut() {
                                e.id = Some(id);
                            }
                            self.notify(format!("Saved {}", editor.name));
                        }
                        Err(err) => self.notify(format!("Could not save: {err}")),
                    }
                }
            }
            Action::Delete(id) => {
                db::delete_workout(&self.conn, id);
                self.workouts.chosen = None;
                self.workouts.editor = None;
                self.notify("Workout deleted");
            }
            Action::Start(id) => {
                if let Some(w) = db::workout(&self.conn, id) {
                    if let Some(sid) = db::start_session(&self.conn, &w) {
                        self.workouts.session_id = Some(sid);
                        self.workouts.session_sets = db::session_sets(&self.conn, sid);
                        self.workouts.started = Some(Instant::now());
                        self.workouts.elapsed = 0;
                        self.notify(format!("Started {}", w.name));
                    } else {
                        self.notify("A session is already in progress");
                    }
                }
            }
        }
    }

    fn session_runner(&mut self, ui: &mut Ui) {
        let t = self.theme.clone();
        let Some(sid) = self.workouts.session_id else { return };
        let Some((_, name, _, _)) = db::active_session(&self.conn) else {
            self.workouts.session_id = None;
            return;
        };
        let elapsed = self.workouts.elapsed;
        let sets = self.workouts.session_sets.clone();

        theme::card(ui, &t, "", |ui| {
            ui.horizontal(|ui| {
                ui.label(RichText::new(name).size(22.0 * t.scale).strong().color(Color32::WHITE));
                theme::chip(ui, &t, "in progress", Color32::from_rgb(0xff, 0xa9, 0x4d));
                ui.add_space(10.0);
                ui.label(RichText::new(fmt_clock(elapsed)).size(24.0 * t.scale).strong().color(theme::hex("#ffd43b")));
                if let Some(until) = self.workouts.rest_until {
                    let left = until.saturating_duration_since(Instant::now()).as_secs() as i64;
                    if left > 0 {
                        theme::chip(ui, &t, &format!("rest {}s", left), theme::hex("#4dd0e1"));
                    }
                }
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    if ui.button("Discard").clicked() {
                        db::discard_session(&self.conn, sid);
                        self.workouts.session_id = None;
                        self.workouts.session_sets.clear();
                        self.workouts.started = None;
                        self.notify("Session discarded");
                    }
                    if ui.add(egui::Button::new("Finish workout")).clicked() {
                        let summary = db::finish_session(&self.conn, self.d, sid, elapsed);
                        self.workouts.session_id = None;
                        self.workouts.session_sets.clear();
                        self.workouts.started = None;
                        self.workouts.elapsed = 0;
                        self.workouts.rest_until = None;
                        match summary {
                            Some(text) => {
                                self.notify(text);
                                self.sync_xp();
                            }
                            None => self.notify("Nothing was ticked, the session was discarded"),
                        }
                    }
                });
            });
        });
        ui.add_space(8.0);

        let done = sets.iter().filter(|s| s.done).count();
        ui.label(t.dim(format!("{} of {} sets done", done, sets.len())));
        ui.add_space(4.0);

        let mut toggle: Option<(i64, bool, i64, i64, i64)> = None;
        ScrollArea::vertical().auto_shrink([false, false]).show(ui, |ui| {
            let mut current_pos = i64::MIN;
            for set in &sets {
                if set.ex_pos != current_pos {
                    current_pos = set.ex_pos;
                    ui.add_space(6.0);
                    ui.label(t.section(&set.exercise_name));
                }
                let target = if set.kind == "reps" { format!("{} reps", set.reps) } else { format!("{} s", set.hold) };
                egui::Frame::none()
                    .fill(if set.done { theme::alpha(theme::hex("#38d9a9"), 26) } else { t.surface2 })
                    .stroke(egui::Stroke::new(1.0, if set.done { theme::alpha(theme::hex("#38d9a9"), 120) } else { t.line }))
                    .rounding(t.radius)
                    .inner_margin(egui::Margin::symmetric(10, 6))
                    .show(ui, |ui| {
                        ui.set_width(ui.available_width());
                        ui.horizontal(|ui| {
                            let mark = if set.done { "✓" } else { "○" };
                            if ui.add(egui::Button::new(mark).min_size(Vec2::new(30.0, 24.0))).clicked() {
                                toggle = Some((set.id, !set.done, set.reps, set.hold, set.rest_sec));
                            }
                            ui.label(t.body(format!("Set {}", set.set_idx + 1)));
                            ui.label(t.dim(target));
                        });
                    });
                ui.add_space(4.0);
            }
        });

        if let Some((set_id, done, reps, hold, rest)) = toggle {
            db::update_set(&self.conn, set_id, reps, hold, done);
            if done && rest > 0 {
                self.workouts.rest_until = Some(Instant::now() + Duration::from_secs(rest as u64));
                self.workouts.rest_total = rest;
            }
            self.workouts.session_sets = db::session_sets(&self.conn, sid);
        }
    }
}
