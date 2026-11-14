//! Achievements: catalogue progress against real training data.
use crate::app::App;
use crate::db;
use crate::logic;
use crate::theme;
use eframe::egui::{self, RichText, ScrollArea, Ui};

impl App {
    pub fn page_achievements(&mut self, ui: &mut Ui) {
        let t = self.theme.clone();
        let state = db::achievement_state(&self.conn);
        let unlocked = state.values().filter(|(_, u)| u.is_some()).count();
        self.page_title(
            ui,
            "Achievements",
            &format!("{} of {} unlocked", unlocked, self.d.achievements.items.len()),
        );
        ui.add_space(6.0);

        let categories: Vec<String> = self.d.achievements.categories.keys().cloned().collect();
        let order = [
            "strength", "static", "skills", "training", "records", "consistency", "progression", "library",
        ];
        let mut ordered: Vec<String> = order.iter().filter(|k| categories.contains(&k.to_string())).map(|s| s.to_string()).collect();
        for cat in &categories {
            if !ordered.contains(cat) {
                ordered.push(cat.clone());
            }
        }

        ScrollArea::vertical().auto_shrink([false, false]).show(ui, |ui| {
            for cat in ordered {
                let items: Vec<_> = self.d.achievements.items.iter().filter(|a| a.category == cat).collect();
                if items.is_empty() {
                    continue;
                }
                ui.label(t.section(
                    self.d.achievements.categories.get(&cat).map(|s| s.as_str()).unwrap_or(&cat),
                ));
                ui.add_space(4.0);
                for a in items {
                    let (progress, date) = state.get(&a.id).cloned().unwrap_or((0.0, None));
                    let rarity = self.d.achievements.rarities.get(&a.rarity);
                    let color = rarity.map(|r| theme::hex(&r.color)).unwrap_or(t.muted);
                    let is_done = date.is_some();
                    egui::Frame::none()
                        .fill(if is_done { theme::blend(color, t.surface, 0.12) } else { t.surface2 })
                        .stroke(egui::Stroke::new(1.0, if is_done { theme::alpha(color, 150) } else { t.line }))
                        .rounding(t.radius + 2.0)
                        .inner_margin(egui::Margin::symmetric(12, 9))
                        .show(ui, |ui| {
                            ui.set_width(ui.available_width());
                            ui.horizontal(|ui| {
                                ui.label(RichText::new(&a.icon).size(16.0 * t.scale).color(color));
                                ui.vertical(|ui| {
                                    ui.horizontal(|ui| {
                                        ui.label(RichText::new(&a.name).size(13.5 * t.scale).strong().color(if is_done { color } else { t.text }));
                                        theme::chip(ui, &t, rarity.map(|r| r.label.as_str()).unwrap_or(&a.rarity), color);
                                    });
                                    ui.label(t.dim(&a.description));
                                });
                                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                    if let Some(date) = &date {
                                        ui.label(t.dim(format!("unlocked {date}")));
                                    } else {
                                        ui.label(t.dim(format!(
                                            "{} / {}",
                                            logic::fmt_num(progress.min(a.target)),
                                            logic::fmt_num(a.target)
                                        )));
                                        ui.add_space(8.0);
                                        ui.label(RichText::new(format!("+{} XP", a.xp)).color(t.muted).size(11.5 * t.scale));
                                    }
                                });
                            });
                            if !is_done {
                                ui.add_space(3.0);
                                theme::bar(ui, &t, (progress / a.target) as f32, color, 5.0);
                            }
                        });
                    ui.add_space(4.0);
                }
                ui.add_space(10.0);
            }
        });
    }
}
