//! Running: distance + time in, pace out; every run is stored as a completed
//! session with a distance so it counts toward history and streaks.
use crate::app::App;
use crate::db;
use crate::logic::{fmt_clock, fmt_pace, pace_of};
use crate::theme;
use eframe::egui::{self, ScrollArea, Ui};

impl App {
    pub fn page_running(&mut self, ui: &mut Ui) {
        let t = self.theme.clone();
        self.page_title(ui, "Running", "Log distance and time – CALIX works out the pace");
        ui.add_space(6.0);

        let totals = db::run_totals(&self.conn);
        ui.horizontal(|ui| {
            theme::stat_tile(ui, &t, "Runs logged", &format!("{}", totals.count), "");
            theme::stat_tile(
                ui,
                &t,
                "Total distance",
                &format!("{:.2} km", totals.distance_m as f64 / 1000.0),
                &format!("{} km", totals.distance_m / 1000),
            );
            theme::stat_tile(ui, &t, "Total time", &fmt_clock(totals.seconds), "");
            theme::stat_tile(ui, &t, "Average pace", &format!("{} /km", fmt_pace(totals.average)), "");
            theme::stat_tile(ui, &t, "Best pace", &format!("{} /km", fmt_pace(totals.best)), "fastest run");
        });
        ui.add_space(10.0);

        let distance_m = (self.running.km * 1000.0).round() as i64;
        let duration = self.running.minutes * 60 + self.running.seconds;
        theme::card(ui, &t, "Log a run", |ui| {
            ui.horizontal(|ui| {
                ui.label(t.dim("Distance"));
                ui.add(egui::DragValue::new(&mut self.running.km).speed(0.1).range(0.1..=200.0).suffix(" km").fixed_decimals(2));
                ui.add_space(10.0);
                ui.label(t.dim("Time"));
                ui.add(egui::DragValue::new(&mut self.running.minutes).speed(1.0).range(0..=600).suffix(" min"));
                ui.add(egui::DragValue::new(&mut self.running.seconds).speed(1.0).range(0..=59).suffix(" s"));
            });
            ui.add_space(6.0);
            ui.horizontal(|ui| {
                let pace = pace_of(distance_m, duration);
                ui.label(t.big(format!("Pace {} /km", fmt_pace(pace))));
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    if ui
                        .add_enabled(distance_m > 0 && duration > 0, egui::Button::new("Save run"))
                        .clicked()
                    {
                        match db::log_run(&self.conn, distance_m, duration) {
                            Ok(_) => {
                                self.notify(format!(
                                    "Run saved – {:.2} km in {} at {} /km",
                                    distance_m as f64 / 1000.0,
                                    fmt_clock(duration),
                                    fmt_pace(pace)
                                ));
                                self.running.minutes = 0;
                                self.running.seconds = 0;
                                self.sync_xp();
                            }
                            Err(err) => self.notify(format!("Could not save the run: {err}")),
                        }
                    }
                });
            });
        });
        ui.add_space(10.0);

        let runs = db::runs(&self.conn);
        theme::card(ui, &t, "Runs", |ui| {
            if runs.is_empty() {
                ui.label(t.dim("No runs yet. Log your first run above and it will appear here."));
                return;
            }
            let mut delete: Option<i64> = None;
            ScrollArea::vertical().max_height(360.0).id_source("runs").show(ui, |ui| {
                for run in &runs {
                    let pace = fmt_pace(pace_of(run.distance_m, run.elapsed_sec));
                    egui::Frame::none()
                        .fill(t.surface2)
                        .stroke(egui::Stroke::new(1.0, t.line))
                        .rounding(t.radius)
                        .inner_margin(egui::Margin::symmetric(10, 8))
                        .show(ui, |ui| {
                            ui.set_width(ui.available_width());
                            ui.horizontal(|ui| {
                                ui.label(t.body(run.session_date.clone()));
                                ui.label(t.dim(format!("{:.2} km", run.distance_m as f64 / 1000.0)));
                                ui.label(t.dim(fmt_clock(run.elapsed_sec)));
                                ui.label(
                                    egui::RichText::new(format!("{pace} /km")).color(theme::hex("#69db7c")).strong(),
                                );
                                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                    if ui.add(egui::Button::new("Delete").small()).clicked() {
                                        delete = Some(run.id);
                                    }
                                });
                            });
                        });
                    ui.add_space(4.0);
                }
            });
            if let Some(id) = delete {
                db::delete_session(&self.conn, id);
                self.notify("Run deleted");
                self.sync_xp();
            }
        });
    }
}
