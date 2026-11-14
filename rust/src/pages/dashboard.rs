//! Dashboard: level, training tiles, skill progress and personal records.
use crate::app::App;
use crate::db;
use crate::logic::{self, Status};
use crate::theme;
use eframe::egui::{self, Color32, RichText, ScrollArea, Ui};

impl App {
    pub fn page_dashboard(&mut self, ui: &mut Ui) {
        let t = self.theme.clone();
        self.page_title(ui, "Dashboard", "Your progress at a glance");
        ui.add_space(6.0);

        let total = db::total_xp(&self.conn);
        let level = logic::level_info(self.d, total);
        theme::card(ui, &t, "", |ui| {
            ui.horizontal(|ui| {
                ui.vertical(|ui| {
                    ui.label(RichText::new(format!("Level {}", level.level)).size(26.0 * t.scale).strong().color(Color32::WHITE));
                    ui.label(RichText::new(&level.title).size(14.0 * t.scale).color(theme::hex(&level.color)));
                });
                ui.add_space(18.0);
                ui.vertical(|ui| {
                    ui.set_width(ui.available_width() - 10.0);
                    ui.label(t.dim(format!("{} XP total", level.total)));
                    theme::bar(ui, &t, level.progress, theme::hex(&level.color), 10.0);
                    let note = if level.next_level > 0 {
                        format!("{} / {} XP into level {} · next title: {} at level {}", level.into, level.need, level.level, level.next_title, level.next_level)
                    } else {
                        "Maximum level reached".to_string()
                    };
                    ui.label(t.dim(note));
                    let unlocked = db::achievement_state(&self.conn).values().filter(|(_, u)| u.is_some()).count();
                    ui.label(t.dim(format!("Achievements unlocked: {} / {}", unlocked, self.d.achievements.items.len())));
                });
            });
        });
        ui.add_space(10.0);

        let st = db::stats(&self.conn);
        let done = self.progress.values().filter(|s| s.as_str() == "completed").count();
        ui.horizontal(|ui| {
            theme::stat_tile(ui, &t, "Workouts", &format!("{}", st.sessions), &format!("{} min trained", st.seconds / 60));
            theme::stat_tile(ui, &t, "This week", &format!("{}", st.this_week), "since Monday");
            theme::stat_tile(ui, &t, "Streak", &format!("{}", st.streak), "days in a row");
            theme::stat_tile(ui, &t, "Skills completed", &format!("{} / {}", done, self.d.skills.items.len()), "in the skill tree");
        });
        ui.add_space(10.0);

        let full = ui.available_size();
        ui.horizontal_top(|ui| {
            ui.allocate_ui_with_layout(egui::Vec2::new(full.x * 0.46, full.y), egui::Layout::top_down(egui::Align::Min), |ui| {
                theme::card(ui, &t, "Skill progress", |ui| {
                    for cat in &self.d.skills.category_order {
                        let total = self.d.skills.items.iter().filter(|s| &s.category == cat).count();
                        let complete = self
                            .d
                            .skills
                            .items
                            .iter()
                            .filter(|s| &s.category == cat && self.progress.get(&s.id).map(|v| v == "completed").unwrap_or(false))
                            .count();
                        let color = theme::hex(self.d.category_color(cat));
                        ui.horizontal(|ui| {
                            ui.label(RichText::new(self.d.category_label(cat)).color(t.text).size(12.5 * t.scale));
                            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                ui.label(t.dim(format!("{complete}/{total}")));
                            });
                        });
                        theme::bar(ui, &t, complete as f32 / total.max(1) as f32, color, 6.0);
                        ui.add_space(4.0);
                    }
                });
                ui.add_space(8.0);
                theme::card(ui, &t, "Personal records", |ui| {
                    let mut bests: Vec<_> = self
                        .bests
                        .iter()
                        .filter_map(|(sid, (value, date))| self.d.skill(sid).map(|s| (s.name.clone(), *value, s.unit.clone(), date.clone())))
                        .collect();
                    bests.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
                    if bests.is_empty() {
                        ui.label(t.dim("No records yet. Log reps or holds from a skill's panel."));
                    }
                    for (name, value, unit, date) in bests.into_iter().take(8) {
                        ui.horizontal(|ui| {
                            ui.label(t.body(name));
                            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                ui.label(t.dim(date));
                                ui.label(RichText::new(format!("{} {}", logic::fmt_num(value), unit)).color(theme::hex("#69db7c")));
                            });
                        });
                    }
                });
            });
            ui.add_space(10.0);
            ui.allocate_ui_with_layout(
                egui::Vec2::new(ui.available_width(), full.y),
                egui::Layout::top_down(egui::Align::Min),
                |ui| {
                    ScrollArea::vertical().id_source("dash-next").auto_shrink([false, false]).show(ui, |ui| {
                        theme::card(ui, &t, "Next up", |ui| {
                            let mut ready: Vec<&crate::data::Skill> = self
                                .d
                                .skills
                                .items
                                .iter()
                                .filter(|s| logic::status(self.d, &self.progress, &s.id) == Status::Available)
                                .collect();
                            if ready.is_empty() {
                                ui.label(t.dim("Everything available is already in training."));
                            }
                            for skill in ready.drain(..).take(10) {
                                let color = theme::hex(self.d.category_color(&skill.category));
                                ui.horizontal(|ui| {
                                    ui.label(RichText::new("○").color(color));
                                    ui.label(t.body(skill.name.clone()));
                                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                        ui.label(t.dim(self.d.tier(skill.tier)));
                                    });
                                });
                            }
                        });
                        ui.add_space(8.0);
                        theme::card(ui, &t, "XP breakdown", |ui| {
                            let breakdown = db::xp_breakdown(&self.conn);
                            let labels = [
                                ("workout", "Workouts"),
                                ("set", "Sets & exercises"),
                                ("record", "Personal records"),
                                ("rank", "Ranks"),
                                ("skill", "Skill tree"),
                                ("achievement", "Achievements"),
                            ];
                            if breakdown.is_empty() {
                                ui.label(t.dim("Finish a workout to start earning XP."));
                            }
                            for (key, label) in labels {
                                if let Some(xp) = breakdown.get(key) {
                                    ui.horizontal(|ui| {
                                        ui.label(t.body(label));
                                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                            ui.label(RichText::new(format!("{} XP", xp)).color(t.text));
                                        });
                                    });
                                }
                            }
                        });
                        ui.add_space(8.0);
                        theme::card(ui, &t, "Library", |ui| {
                            ui.label(t.dim(format!(
                                "{} exercises · {} trained · {} categories",
                                self.d.exercises.items.len(),
                                st.trained.len(),
                                self.d.exercises.category_order.len()
                            )));
                            theme::bar(
                                ui,
                                &t,
                                st.trained.len() as f32 / self.d.exercises.items.len().max(1) as f32,
                                Color32::from_rgb(0x4d, 0xab, 0xf7),
                                6.0,
                            );
                        });
                    });
                },
            );
        });
    }
}
