//! Body metrics (weight, body fat) and the 12-month consistency heatmap.
use crate::app::App;
use crate::db;
use crate::theme;
use chrono::Datelike;
use eframe::egui::{self, Color32, RichText, Sense, Ui, Vec2};

impl App {
    pub fn page_body(&mut self, ui: &mut Ui) {
        let t = self.theme.clone();
        self.page_title(ui, "Body & consistency", "Weight, body fat and every training day of the last year");
        ui.add_space(6.0);

        let log = db::body_log(&self.conn);
        let latest = log.last().cloned();
        let change = {
            let cutoff = chrono::Local::now().date_naive() - chrono::Duration::days(30);
            log.iter()
                .rev()
                .find(|r| {
                    chrono::NaiveDate::parse_from_str(&r.date, "%Y-%m-%d")
                        .map(|d| d <= cutoff)
                        .unwrap_or(false)
                })
                .map(|old| latest.as_ref().map(|n| n.weight - old.weight))
                .flatten()
        };
        let st = db::stats(&self.conn);

        ui.horizontal(|ui| {
            theme::stat_tile(
                ui,
                &t,
                "Weight",
                &latest.as_ref().map(|r| format!("{:.1} kg", r.weight)).unwrap_or_else(|| "–".into()),
                latest.as_ref().map(|r| r.date.as_str()).unwrap_or("no entry yet"),
            );
            theme::stat_tile(
                ui,
                &t,
                "Last 30 days",
                &change
                    .map(|d| format!("{:+.1} kg", d))
                    .unwrap_or_else(|| "–".into()),
                "change in weight",
            );
            theme::stat_tile(
                ui,
                &t,
                "Body fat",
                &latest
                    .as_ref()
                    .map(|r| if r.body_fat > 0.0 { format!("{:.1} %", r.body_fat) } else { "–".into() })
                    .unwrap_or_else(|| "–".into()),
                "latest entry",
            );
            theme::stat_tile(ui, &t, "Streak", &format!("{}", st.streak), "days in a row");
        });
        ui.add_space(10.0);

        let full = ui.available_size();
        ui.horizontal_top(|ui| {
            ui.allocate_ui_with_layout(
                Vec2::new(full.x * 0.4, full.y),
                egui::Layout::top_down(egui::Align::Min),
                |ui| {
                    let mut weight = self.body.weight.clone();
                    let mut fat = self.body.fat.clone();
                    let mut note = self.body.note.clone();
                    let mut save = false;
                    theme::card(ui, &t, "Log today", |ui| {
                        ui.label(t.dim("Weight (kg)"));
                        ui.add(
                            egui::TextEdit::singleline(&mut weight)
                                .hint_text("e.g. 78.4")
                                .desired_width(f32::INFINITY),
                        );
                        ui.label(t.dim("Body fat (%), optional"));
                        ui.add(
                            egui::TextEdit::singleline(&mut fat)
                                .hint_text("e.g. 14.5")
                                .desired_width(f32::INFINITY),
                        );
                        ui.label(t.dim("Note"));
                        ui.add(
                            egui::TextEdit::singleline(&mut note)
                                .hint_text("morning, after rest…")
                                .desired_width(f32::INFINITY),
                        );
                        ui.add_space(6.0);
                        if ui
                            .add(
                                egui::Button::new(RichText::new("Save entry").strong().color(Color32::WHITE))
                                    .fill(theme::blend(t.accent, Color32::BLACK, 0.72))
                                    .rounding(t.radius),
                            )
                            .clicked()
                        {
                            save = true;
                        }
                        ui.add_space(4.0);
                        ui.label(t.dim("One entry per day — saving again replaces today's numbers."));
                    });
                    self.body.weight = weight;
                    self.body.fat = fat;
                    self.body.note = note;
                    if save {
                        let w: f64 = self.body.weight.replace(',', ".").trim().parse().unwrap_or(0.0);
                        let f: f64 = self.body.fat.replace(',', ".").trim().parse().unwrap_or(0.0);
                        if w <= 0.0 {
                            self.notify("Enter your weight in kg first");
                        } else {
                            db::save_body(&self.conn, w, f.clamp(0.0, 80.0), self.body.note.trim());
                            self.body.weight.clear();
                            self.body.fat.clear();
                            self.body.note.clear();
                            self.notify(format!("Body metric saved: {w:.1} kg"));
                        }
                    }

                    ui.add_space(8.0);
                    theme::card(ui, &t, "Recent entries", |ui| {
                        if log.is_empty() {
                            ui.label(t.dim("No entries yet. Log your weight and the trend starts here."));
                            return;
                        }
                        let mut prev: Option<f64> = None;
                        for row in log.iter().rev().take(8) {
                            let delta = prev.map(|p| row.weight - p);
                            prev = Some(row.weight);
                            ui.horizontal(|ui| {
                                ui.label(t.body(row.date.clone()));
                                if !row.note.is_empty() {
                                    ui.label(t.dim(row.note.clone()));
                                }
                                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                    if let Some(d) = delta {
                                        let color = if d < 0.0 {
                                            Color32::from_rgb(0x4a, 0xd9, 0xa9)
                                        } else if d > 0.0 {
                                            Color32::from_rgb(0xff, 0xa9, 0x4d)
                                        } else {
                                            t.muted
                                        };
                                        ui.label(RichText::new(format!("{d:+.1}")).color(color).size(11.0 * t.scale));
                                    }
                                    ui.label(
                                        RichText::new(format!("{:.1} kg", row.weight))
                                            .strong()
                                            .color(t.text),
                                    );
                                });
                            });
                        }
                    });
                },
            );
            ui.add_space(10.0);
            ui.allocate_ui_with_layout(
                Vec2::new(ui.available_width(), full.y),
                egui::Layout::top_down(egui::Align::Min),
                |ui| {
                    let today = chrono::Local::now().date_naive();
                    let monday = today
                        - chrono::Duration::days(today.weekday().num_days_from_monday() as i64);
                    let start = monday - chrono::Duration::weeks(52);
                    let counts = db::day_counts(&self.conn, &start.to_string());
                    let trained = counts.len();
                    theme::card(ui, &t, "Consistency · last 12 months", |ui| {
                        ui.horizontal(|ui| {
                            ui.label(t.dim("Every column is a week, every square a day."));
                            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                ui.label(
                                    RichText::new(format!("{trained} training days"))
                                        .strong()
                                        .color(t.accent),
                                );
                            });
                        });
                        ui.add_space(8.0);
                        heatmap(ui, &t, &counts, start, 53);
                        ui.add_space(6.0);
                        ui.horizontal(|ui| {
                            ui.label(t.dim("less"));
                            for step in 0..5 {
                                let (rect, _) = ui.allocate_exact_size(Vec2::splat(10.0), Sense::hover());
                                let color = if step == 0 {
                                    t.surface2
                                } else {
                                    theme::alpha(t.accent, 55 + step as u8 * 50)
                                };
                                ui.painter().rect_filled(rect, 2.0, color);
                            }
                            ui.label(t.dim("more"));
                        });
                    });
                    ui.add_space(8.0);
                    theme::card(ui, &t, "This week", |ui| {
                        ui.label(t.body(format!(
                            "{} workouts · {} sets · {} reps · {} held",
                            st.this_week, st.sets, st.reps, crate::logic::fmt_clock(st.hold)
                        )));
                        let avg = db::average_rpe(&self.conn, &(today - chrono::Duration::days(7)).to_string());
                        ui.label(t.dim(match avg {
                            Some(v) => format!("Average RPE over the last 7 days: {v:.1} / 10"),
                            None => "No RPE ratings in the last 7 days. Rate a set in a workout.".into(),
                        }));
                    });
                },
            );
        });
    }
}

/// 53 columns × 7 rows of rounded squares, painted from per-day session counts.
fn heatmap(
    ui: &mut Ui,
    t: &theme::Theme,
    counts: &std::collections::HashMap<String, i64>,
    start: chrono::NaiveDate,
    weeks: usize,
) {
    let gap = 3.0;
    let width = ui.available_width();
    let cell = ((width - gap * (weeks as f32 - 1.0)) / weeks as f32).clamp(6.0, 16.0);
    let height = cell.mul_add(6.0, gap * 6.0);
    let (rect, _) = ui.allocate_exact_size(Vec2::new(width, height), Sense::hover());
    let painter = ui.painter();
    painter.rect_filled(rect, t.radius * 0.6, theme::alpha(Color32::BLACK, 40));
    for week in 0..weeks {
        for day in 0..7 {
            let date = start + chrono::Duration::days((week * 7 + day) as i64);
            let n = counts.get(&date.to_string()).copied().unwrap_or(0);
            let color = match n {
                0 => theme::alpha(Color32::WHITE, 14),
                1 => theme::alpha(t.accent, 70),
                2 => theme::alpha(t.accent, 120),
                3 => theme::alpha(t.accent, 175),
                _ => t.accent,
            };
            let origin = egui::pos2(
                rect.left() + week as f32 * (cell + gap),
                rect.top() + day as f32 * (cell + gap) + gap * 0.5,
            );
            painter.rect_filled(
                egui::Rect::from_min_size(origin, Vec2::splat(cell)),
                2.0,
                color,
            );
        }
    }
}
