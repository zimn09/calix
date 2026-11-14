//! Settings: appearance, plus where the data lives.
use crate::app::App;
use crate::db;
use crate::theme;
use eframe::egui::{self, Color32, RichText, Ui};

impl App {
    pub fn page_settings(&mut self, ui: &mut Ui) {
        let t = self.theme.clone();
        self.page_title(ui, "Settings", "The look is saved to your local database");
        ui.add_space(6.0);

        let mut changed = false;
        theme::card(ui, &t, "Accent", |ui| {
            ui.horizontal(|ui| {
                for (name, hex) in theme::ACCENTS {
                    let selected = self.settings.accent.eq_ignore_ascii_case(hex);
                    let color = theme::hex(hex);
                    let button = egui::Button::new(
                        RichText::new(name).color(if selected { Color32::WHITE } else { color }).size(12.5 * t.scale),
                    )
                    .fill(if selected { theme::alpha(color, 70) } else { Color32::TRANSPARENT })
                    .stroke(egui::Stroke::new(1.0, color))
                    .rounding(t.radius);
                    if ui.add(button).clicked() {
                        self.settings.accent = hex.to_string();
                        changed = true;
                    }
                }
            });
        });
        ui.add_space(8.0);

        theme::card(ui, &t, "Background", |ui| {
            ui.horizontal(|ui| {
                for (label, key) in theme::BACKGROUNDS {
                    if theme::pill_button(ui, &t, label, self.settings.background == key).clicked() {
                        self.settings.background = key.to_string();
                        changed = true;
                    }
                }
            });
        });
        ui.add_space(8.0);

        theme::card(ui, &t, "Shape & type", |ui| {
            ui.horizontal(|ui| {
                ui.label(t.dim("Corners"));
                for key in ["sharp", "rounded", "round"] {
                    if theme::pill_button(ui, &t, key, self.settings.corners == key).clicked() {
                        self.settings.corners = key.to_string();
                        changed = true;
                    }
                }
                ui.add_space(14.0);
                ui.label(t.dim("Font size"));
                if ui
                    .add(egui::Slider::new(&mut self.settings.font_size, 9.0..=13.0).step_by(0.5).suffix(" pt"))
                    .changed()
                {
                    changed = true;
                }
            });
            ui.add_space(4.0);
            ui.horizontal(|ui| {
                changed |= ui.checkbox(&mut self.settings.grid, "Dot grid on the skill tree").changed();
                ui.add_space(12.0);
                changed |= ui.checkbox(&mut self.settings.effects, "Glow & rank badges").changed();
            });
        });
        ui.add_space(8.0);

        theme::card(ui, &t, "Data", |ui| {
            ui.label(t.body(format!("Database: {}", db::db_path().display())));
            ui.label(t.dim(
                "CALIX keeps everything offline in SQLite. The schema matches the Python edition, so both apps can open the same file.",
            ));
            ui.add_space(6.0);
            ui.horizontal(|ui| {
                if ui.button("Recompute XP & achievements").clicked() {
                    self.sync_xp();
                    self.notify("XP and achievements brought up to date");
                }
            });
        });
        ui.add_space(8.0);

        theme::card(ui, &t, "About", |ui| {
            ui.label(t.body(format!("CALIX {} – Rust desktop edition", env!("CARGO_PKG_VERSION"))));
            ui.label(t.dim(format!(
                "{} skills · {} exercises · {} achievements · {} rank ladders",
                self.d.skills.items.len(),
                self.d.exercises.items.len(),
                self.d.achievements.items.len(),
                self.d.ranks.ranks.len() - 1
            )));
        });

        if changed {
            self.apply_theme(ui.ctx());
        }
    }
}
