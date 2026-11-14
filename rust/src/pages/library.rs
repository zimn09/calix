//! Exercise library: searchable list plus the full technique sheet.
use crate::app::App;
use crate::theme;
use eframe::egui::{self, Color32, RichText, ScrollArea, Stroke, Ui, Vec2};

impl App {
    pub fn page_library(&mut self, ui: &mut Ui) {
        let t = self.theme.clone();
        self.page_title(ui, "Exercise Library", "Technique, muscles, mistakes and progressions for every movement");
        ui.add_space(6.0);

        ui.horizontal(|ui| {
            ui.add(
                egui::TextEdit::singleline(&mut self.library.query)
                    .hint_text("Search exercises…")
                    .desired_width(260.0),
            );
            if theme::pill_button(ui, &t, "All", self.library.category.is_none()).clicked() {
                self.library.category = None;
            }
            for cat in &self.d.exercises.category_order {
                let selected = self.library.category.as_deref() == Some(cat.as_str());
                let color = theme::hex(self.d.exercise_category_color(cat));
                let label = self.d.exercise_category_label(cat).to_string();
                let button = egui::Button::new(
                    RichText::new(label).size(12.5 * t.scale).color(if selected { Color32::WHITE } else { color }),
                )
                .fill(if selected { theme::alpha(color, 60) } else { Color32::TRANSPARENT })
                .rounding(t.radius);
                if ui.add(button).clicked() {
                    self.library.category = Some(cat.clone());
                }
            }
        });
        ui.add_space(8.0);

        let query = self.library.query.to_lowercase();
        let matches: Vec<_> = self
            .d
            .exercises
            .items
            .iter()
            .filter(|e| self.library.category.as_deref().map(|c| e.category == c).unwrap_or(true))
            .filter(|e| {
                query.is_empty()
                    || e.name.to_lowercase().contains(&query)
                    || e.instructions.to_lowercase().contains(&query)
                    || self
                        .d
                        .detail(&e.id)
                        .map(|d| d.muscles.join(" ").to_lowercase().contains(&query))
                        .unwrap_or(false)
            })
            .cloned()
            .collect();

        if self.library.selected.is_none() {
            self.library.selected = matches.first().map(|e| e.id.clone());
        }

        let full = ui.available_size();
        let list_w = 360.0_f32.min(full.x * 0.42);
        ui.horizontal_top(|ui| {
            ui.allocate_ui_with_layout(Vec2::new(list_w, full.y), egui::Layout::top_down(egui::Align::Min), |ui| {
                ui.label(t.dim(format!("{} exercises", matches.len())));
                ScrollArea::vertical().id_source("library-list").auto_shrink([false, false]).show(ui, |ui| {
                    for ex in &matches {
                        let selected = self.library.selected.as_deref() == Some(ex.id.as_str());
                        let color = theme::hex(self.d.exercise_category_color(&ex.category));
                        let frame = egui::Frame::none()
                            .fill(if selected { theme::alpha(color, 34) } else { t.surface2 })
                            .stroke(Stroke::new(1.0, if selected { theme::alpha(color, 140) } else { t.line }))
                            .rounding(t.radius)
                            .inner_margin(egui::Margin::symmetric(10, 8));
                        let resp = frame
                            .show(ui, |ui| {
                                ui.set_width(ui.available_width());
                                ui.horizontal(|ui| {
                                    ui.label(RichText::new("●").size(11.0).color(color));
                                    ui.label(RichText::new(&ex.name).size(13.5 * t.scale).strong().color(t.text));
                                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                        ui.label(t.dim(self.d.difficulty(ex.difficulty)));
                                    });
                                });
                            })
                            .response;
                        if resp.interact(egui::Sense::click()).clicked() {
                            self.library.selected = Some(ex.id.clone());
                        }
                        ui.add_space(4.0);
                    }
                });
            });
            ui.add_space(10.0);
            ui.allocate_ui_with_layout(
                Vec2::new(ui.available_width(), full.y),
                egui::Layout::top_down(egui::Align::Min),
                |ui| {
                    ScrollArea::vertical().id_source("library-detail").auto_shrink([false, false]).show(ui, |ui| {
                        self.library_detail(ui);
                    });
                },
            );
        });
    }

    fn library_detail(&mut self, ui: &mut Ui) {
        let t = self.theme.clone();
        let Some(id) = self.library.selected.clone() else {
            ui.label(t.dim("Pick an exercise to read its sheet."));
            return;
        };
        let Some(ex) = self.d.exercise(&id) else { return };
        let ex = ex.clone();
        let detail = self.d.detail(&id).cloned().unwrap_or_default();
        let color = theme::hex(self.d.exercise_category_color(&ex.category));

        theme::card(ui, &t, "", |ui| {
            ui.label(RichText::new(&ex.name).size(22.0 * t.scale).strong().color(Color32::WHITE));
            ui.horizontal(|ui| {
                theme::chip(ui, &t, self.d.exercise_category_label(&ex.category), color);
                theme::chip(ui, &t, self.d.difficulty(ex.difficulty), theme::hex("#9aa4b2"));
                theme::chip(ui, &t, if ex.kind == "reps" { "Reps" } else { "Hold" }, theme::hex("#4dd0e1"));
                if !detail.equipment.is_empty() {
                    theme::chip(ui, &t, &detail.equipment, theme::hex("#ffc078"));
                }
            });
            ui.add_space(4.0);
            ui.label(t.body(&ex.instructions));
        });
        ui.add_space(8.0);

        if !detail.muscles.is_empty() {
            theme::card(ui, &t, "Muscles", |ui| ui.label(t.body(detail.muscles.join(" · "))));
            ui.add_space(8.0);
        }
        if !detail.mistakes.is_empty() {
            theme::card(ui, &t, "Common mistakes", |ui| {
                for m in &detail.mistakes {
                    ui.label(t.body(format!("• {}", m)));
                }
            });
            ui.add_space(8.0);
        }
        if !detail.tips.is_empty() {
            theme::card(ui, &t, "Coaching cues", |ui| {
                for tip in &detail.tips {
                    ui.label(t.body(format!("• {}", tip)));
                }
            });
            ui.add_space(8.0);
        }

        theme::card(ui, &t, "Prescription", |ui| {
            ui.label(t.body(format!(
                "{} sets × {} {}",
                ex.default_sets,
                ex.default_amount,
                if ex.kind == "reps" { "reps" } else { "s hold" }
            )));
            ui.label(t.dim(format!("Rest between sets: {} s", ex.default_rest)));
        });
        ui.add_space(8.0);

        let names = |ids: &Vec<String>| -> String {
            ids.iter()
                .filter_map(|id| self.d.exercise(id).map(|e| e.name.clone()))
                .collect::<Vec<_>>()
                .join(" · ")
        };
        if !detail.easier.is_empty() || !detail.harder.is_empty() {
            theme::card(ui, &t, "Progressions", |ui| {
                if !detail.easier.is_empty() {
                    ui.label(t.dim(format!("Easier: {}", names(&detail.easier))));
                }
                if !detail.harder.is_empty() {
                    ui.label(t.dim(format!("Harder: {}", names(&detail.harder))));
                }
            });
            ui.add_space(8.0);
        }
        if !detail.related.is_empty() {
            theme::card(ui, &t, "Related", |ui| ui.label(t.dim(names(&detail.related))));
        }
    }
}
