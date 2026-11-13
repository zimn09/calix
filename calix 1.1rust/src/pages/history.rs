//! Workout history and the statistics calculated from it.
use crate::app::App;
use crate::db;
use crate::logic::{fmt_clock, fmt_pace, pace_of};
use crate::theme;
use eframe::egui::{self, ScrollArea, Ui};

pub fn pretty_date(day: &str) -> String {
    chrono::NaiveDate::parse_from_str(day, "%Y-%m-%d")
        .map(|d| d.format("%a %b %-d, %Y").to_string())
        .unwrap_or_else(|_| day.to_string())
}

impl App {
    pub fn page_history(&mut self, ui: &mut Ui) {
        let t = self.theme.clone();
        self.page_title(ui, "Workout History", "Every finished session, including runs");
        ui.add_space(6.0);

        let st = db::stats(&self.conn);
        ui.horizontal(|ui| {
            theme::stat_tile(ui, &t, "Workouts", &format!("{}", st.sessions), &format!("{} min trained", st.seconds / 60));
            theme::stat_tile(ui, &t, "This week", &format!("{}", st.this_week), "since Monday");
            theme::stat_tile(ui, &t, "Streak", &format!("{}", st.streak), if st.streak == 1 { "day" } else { "days in a row" });
            theme::stat_tile(ui, &t, "Sets", &format!("{}", st.sets), "");
        });
        ui.add_space(8.0);
        ui.horizontal(|ui| {
            theme::stat_tile(ui, &t, "Reps", &format!("{}", st.reps), "");
            theme::stat_tile(ui, &t, "Hold time", &fmt_clock(st.hold), "total");
            theme::stat_tile(ui, &t, "Exercises trained", &format!("{}", st.trained.len()), "");
            theme::stat_tile(ui, &t, "Max hold", &format!("{} s", st.max_hold as i64), "single set");
        });
        ui.add_space(10.0);

        let rows = db::history(&self.conn);
        theme::card(ui, &t, "Sessions", |ui| {
            if rows.is_empty() {
                ui.label(t.dim("No sessions yet. Finish a workout or log a run and it appears here."));
                return;
            }
            let mut delete = None;
            ScrollArea::vertical().max_height(520.0).id_source("history").show(ui, |ui| {
                for row in &rows {
                    egui::Frame::none()
                        .fill(t.surface2)
                        .stroke(egui::Stroke::new(1.0, t.line))
                        .rounding(t.radius)
                        .inner_margin(egui::Margin::symmetric(10, 8))
                        .show(ui, |ui| {
                            ui.set_width(ui.available_width());
                            ui.horizontal(|ui| {
                                ui.label(egui::RichText::new(pretty_date(&row.session_date)).strong().color(t.text));
                                ui.label(t.body(row.workout_name.clone()));
                                if row.distance_m > 0 {
                                    ui.label(t.dim(format!(
                                        "{:.2} km · {} · {} /km",
                                        row.distance_m as f64 / 1000.0,
                                        fmt_clock(row.elapsed_sec),
                                        fmt_pace(pace_of(row.distance_m, row.elapsed_sec))
                                    )));
                                } else {
                                    ui.label(t.dim(format!(
                                        "{} · {}/{} sets · {} reps",
                                        fmt_clock(row.elapsed_sec),
                                        row.sets_done,
                                        row.sets_total,
                                        row.reps_total
                                    )));
                                }
                                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                    if ui.add(egui::Button::new("Delete").small()).clicked() {
                                        delete = Some(row.id);
                                    }
                                });
                            });
                        });
                    ui.add_space(4.0);
                }
            });
            if let Some(id) = delete {
                db::delete_session(&self.conn, id);
                self.notify("Session deleted");
                self.sync_xp();
            }
        });
    }
}
