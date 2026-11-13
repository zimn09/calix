//! Ranks: one ladder per exercise plus the progression lines.
use crate::app::App;
use crate::db;
use crate::logic;
use crate::theme;
use eframe::egui::{self, RichText, ScrollArea, Ui};
use std::collections::HashSet;

impl App {
    pub fn page_ranks(&mut self, ui: &mut Ui) {
        let t = self.theme.clone();
        self.page_title(ui, "Ranks", "A ladder for every exercise and every progression line");
        ui.add_space(6.0);

        let st = db::stats(&self.conn);
        let done: HashSet<String> = self
            .progress
            .iter()
            .filter(|(_, s)| s.as_str() == "completed")
            .map(|(k, _)| k.clone())
            .collect();
        let mut tracks: Vec<_> = logic::build_tracks(self.d)
            .into_iter()
            .map(|track| logic::evaluate(&track, &st.bests_by_exercise, &done, self.d.ranks.max_rank))
            .collect();
        tracks.sort_by(|a, b| {
            b.rank.cmp(&a.rank).then(b.best.partial_cmp(&a.best).unwrap_or(std::cmp::Ordering::Equal))
        });

        let order = ["pushing", "pulling", "core", "legs", "static"];
        ScrollArea::vertical().auto_shrink([false, false]).show(ui, |ui| {
            for group in order {
                let rows: Vec<_> = tracks.iter().filter(|r| r.track.group == group).collect();
                if rows.is_empty() {
                    continue;
                }
                ui.label(t.section(self.d.ranks.groups.get(group).map(|s| s.as_str()).unwrap_or(group)));
                ui.add_space(4.0);
                for res in rows {
                    let color = theme::hex(self.d.rank_color(res.rank));
                    egui::Frame::none()
                        .fill(t.surface)
                        .stroke(egui::Stroke::new(1.0, t.line))
                        .rounding(t.radius + 2.0)
                        .inner_margin(egui::Margin::symmetric(12, 9))
                        .show(ui, |ui| {
                            ui.set_width(ui.available_width());
                            ui.horizontal(|ui| {
                                ui.label(RichText::new(&res.track.name).size(13.5 * t.scale).strong().color(t.text));
                                theme::chip(ui, &t, self.d.rank_name(res.rank), color);
                                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                    ui.label(t.dim(res.goal.clone()));
                                });
                            });
                            ui.add_space(3.0);
                            theme::bar(ui, &t, res.progress, color, 6.0);
                        });
                    ui.add_space(4.0);
                }
                ui.add_space(10.0);
            }
        });
    }
}
