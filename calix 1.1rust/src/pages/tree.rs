//! The interactive skill tree: pan/zoom canvas, nodes, edges and the detail panel.
use crate::app::App;
use crate::logic::{self, Status, NODE_H, NODE_W, ROW_H};
use crate::theme;
use eframe::egui::{
    self, Align2, Color32, FontId, Rect, RichText, Sense, Stroke, Ui, Vec2,
};

const ORANGE: Color32 = Color32::from_rgb(0xff, 0xa9, 0x4d);

fn status_style(status: Status, cat: Color32) -> (Color32, Color32, Color32, Color32) {
    // (top, bottom, border, text)
    match status {
        Status::Locked => (
            Color32::from_rgb(0x10, 0x17, 0x24),
            Color32::from_rgb(0x0c, 0x11, 0x19),
            Color32::from_rgb(0x1c, 0x25, 0x34),
            Color32::from_rgb(0x6d, 0x7b, 0x91),
        ),
        Status::Available => (
            theme::blend(cat, Color32::from_rgb(0x0f, 0x15, 0x21), 0.24),
            Color32::from_rgb(0x0c, 0x11, 0x1a),
            cat,
            Color32::from_rgb(0xf3, 0xf7, 0xfc),
        ),
        Status::Training => (
            theme::blend(ORANGE, Color32::from_rgb(0x0f, 0x15, 0x21), 0.30),
            Color32::from_rgb(0x0c, 0x11, 0x1a),
            ORANGE,
            Color32::from_rgb(0xff, 0xf4, 0xe6),
        ),
        Status::Completed => (
            theme::blend(cat, Color32::from_rgb(0x0f, 0x15, 0x21), 0.52),
            theme::blend(cat, Color32::from_rgb(0x0b, 0x10, 0x17), 0.24),
            cat,
            Color32::WHITE,
        ),
    }
}

fn wrap_name(name: &str) -> Vec<String> {
    if name.chars().count() <= 19 {
        return vec![name.to_string()];
    }
    let mut lines: Vec<String> = Vec::new();
    let mut current = String::new();
    for word in name.split_whitespace() {
        if !current.is_empty() && current.chars().count() + word.chars().count() + 1 > 18 {
            lines.push(std::mem::take(&mut current));
        }
        if !current.is_empty() {
            current.push(' ');
        }
        current.push_str(word);
        if lines.len() == 2 {
            break;
        }
    }
    if !current.is_empty() {
        lines.push(current);
    }
    lines.truncate(2);
    lines
}

impl App {
    pub fn page_tree(&mut self, ui: &mut Ui) {
        let t = self.theme.clone();
        ui.horizontal(|ui| {
            ui.label(t.title("Skill Tree"));
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                ui.label(t.dim("drag to pan · scroll to zoom · click a node"));
            });
        });
        ui.add_space(8.0);

        let full = ui.available_size();
        let detail_w = 360.0_f32.min(full.x * 0.38);
        let canvas_w = (full.x - detail_w - 12.0).max(240.0);
        let height = full.y.max(200.0);

        ui.horizontal_top(|ui| {
            self.tree_canvas(ui, Vec2::new(canvas_w, height));
            ui.add_space(10.0);
            ui.allocate_ui_with_layout(Vec2::new(detail_w, height), egui::Layout::top_down(egui::Align::Min), |ui| {
                egui::ScrollArea::vertical()
                    .id_source("skill-detail")
                    .auto_shrink([false, false])
                    .show(ui, |ui| self.tree_detail(ui));
            });
        });
    }

    fn tree_canvas(&mut self, ui: &mut Ui, size: Vec2) {
        let t = self.theme.clone();
        let (resp, painter) = ui.allocate_painter(size, Sense::click_and_drag());
        let rect = resp.rect;
        let painter = painter.with_clip_rect(rect);
        painter.rect_filled(rect, t.radius + 8.0, t.bg2);

        if resp.dragged() {
            self.tree.pan += resp.drag_delta();
        }
        if resp.hovered() {
            let scroll = ui.input(|i| i.raw_scroll_delta.y);
            if scroll.abs() > 0.5 {
                let pointer = ui.input(|i| i.pointer.hover_pos()).unwrap_or(rect.center());
                let old = self.tree.zoom;
                let new = (old * (scroll * 0.0016).exp()).clamp(0.14, 2.6);
                let k = new / old;
                self.tree.pan = (pointer - rect.min) - ((pointer - rect.min) - self.tree.pan) * k;
                self.tree.zoom = new;
            }
        }

        if !self.tree.init && rect.width() > 50.0 {
            let total: f32 = self
                .layout
                .lanes
                .last()
                .map(|l| l.left + l.width + 30.0)
                .unwrap_or(1600.0);
            let _ = total;
            self.tree.zoom = (rect.width() / 1750.0).clamp(0.34, 0.72);
            self.tree.pan = Vec2::new(18.0, 150.0);
            self.tree.init = true;
        }
        let zoom = self.tree.zoom;
        let origin = rect.min + self.tree.pan;
        let to_screen = |x: f32, y: f32| egui::pos2(origin.x + x * zoom, origin.y + y * zoom);

        // ---- dot grid
        if self.settings.grid {
            let step = 36.0 * zoom;
            if step > 7.0 {
                let mut y = origin.y - ((origin.y - rect.top()) / step).ceil() * step;
                while y < rect.bottom() {
                    let mut x = origin.x - ((origin.x - rect.left()) / step).ceil() * step;
                    while x < rect.right() {
                        painter.circle_filled(egui::pos2(x, y), 1.0, theme::alpha(Color32::WHITE, 12));
                        x += step;
                    }
                    y += step;
                }
            }
        }

        // ---- category lanes
        let band_top = -185.0;
        let band_bottom = self.layout.max_row as f32 * ROW_H + 250.0;
        for lane in &self.layout.lanes {
            let cat = theme::hex(self.d.category_color(&lane.category));
            // lanes are columns: they run from the header to the bottom of the canvas
            let left_x = to_screen(lane.left - 14.0, 0.0).x;
            let right_x = to_screen(lane.left + lane.width + 14.0, 0.0).x;
            let top_y = to_screen(0.0, band_top).y;
            let band = Rect::from_min_max(
                egui::pos2(left_x.max(rect.left() - 4.0), top_y),
                egui::pos2(right_x.min(rect.right() + 4.0), rect.bottom()),
            );
            if band.width() <= 0.0 {
                continue;
            }
            painter.rect_filled(band, 18.0, theme::alpha(cat, 4));
            painter.rect_stroke(band, 18.0, Stroke::new(1.0, theme::alpha(cat, 20)), egui::StrokeKind::Inside);
            painter.circle_filled(to_screen(lane.left + 16.0, band_top + 34.0), 4.5 * zoom, theme::alpha(cat, 230));
            painter.text(
                to_screen(lane.left + 34.0, band_top + 34.0),
                Align2::LEFT_CENTER,
                self.d.category_label(&lane.category).to_uppercase(),
                FontId::proportional(15.0 * zoom.max(0.5)),
                theme::alpha(cat, 210),
            );
        }

        // ---- edges
        for skill in &self.d.skills.items {
            let Some(&(cx, cy)) = self.layout.pos.get(&skill.id) else { continue };
            for pre in &skill.prereqs {
                let Some(&(px, py)) = self.layout.pos.get(pre) else { continue };
                let from = to_screen(px, py + NODE_H / 2.0);
                let to = to_screen(cx, cy - NODE_H / 2.0);
                let parent_status = logic::status(self.d, &self.progress, pre);
                let child_status = logic::status(self.d, &self.progress, &skill.id);
                let color = if parent_status == Status::Completed && child_status == Status::Completed {
                    Color32::from_rgb(0x38, 0xd9, 0xa9)
                } else if parent_status == Status::Completed {
                    theme::hex(self.d.category_color(&skill.category))
                } else {
                    Color32::from_rgb(0x20, 0x2a, 0x3a)
                };
                let mid = (from.y + to.y) / 2.0;
                let points = [
                    from,
                    egui::pos2(from.x, mid),
                    egui::pos2(to.x, mid),
                    to,
                ];
                let stroke = Stroke::new((2.0 * zoom).clamp(1.0, 3.4), theme::alpha(color, 200));
                painter.add(egui::epaint::CubicBezierShape::from_points_stroke(
                    points,
                    false,
                    Color32::TRANSPARENT,
                    stroke,
                ));
            }
        }

        // ---- nodes
        let pointer = ui.input(|i| i.pointer.hover_pos());
        let mut hit: Option<String> = None;
        for skill in &self.d.skills.items {
            let Some(&(x, y)) = self.layout.pos.get(&skill.id) else { continue };
            let center = to_screen(x, y);
            let size = Vec2::new(NODE_W * zoom, NODE_H * zoom);
            let node_rect = Rect::from_center_size(center, size);
            if !rect.intersects(node_rect) {
                continue;
            }
            let status = logic::status(self.d, &self.progress, &skill.id);
            let cat = theme::hex(self.d.category_color(&skill.category));
            let (top, bottom, border, text) = status_style(status, cat);
            if let Some(p) = pointer {
                if node_rect.contains(p) {
                    hit = Some(skill.id.clone());
                }
            }
            if self.tree.hover.as_deref() == Some(skill.id.as_str())
                || self.tree.selected.as_deref() == Some(skill.id.as_str())
            {
                painter.rect_stroke(
                    node_rect.expand(2.0),
                    t.radius,
                    Stroke::new(1.6, theme::alpha(Color32::WHITE, 150)),
                    egui::StrokeKind::Outside,
                );
            }
            painter.rect_filled(node_rect, t.radius, theme::blend(top, bottom, 0.55));
            // glass sheen across the top half
            let sheen = Rect::from_min_max(
                egui::pos2(node_rect.left() + 1.0, node_rect.top() + 1.0),
                egui::pos2(node_rect.right() - 1.0, node_rect.center().y),
            );
            painter.rect_filled(sheen, t.radius - 2.0, theme::alpha(Color32::WHITE, 10));
            painter.rect_stroke(node_rect, t.radius, Stroke::new(if status == Status::Locked { 1.0 } else { 1.8 }, border), egui::StrokeKind::Inside);
            // category rail
            let rail = Rect::from_min_size(
                egui::pos2(node_rect.left() + 6.0 * zoom, node_rect.top() + 11.0 * zoom),
                Vec2::new(4.0 * zoom, node_rect.height() - 22.0 * zoom),
            );
            painter.rect_filled(rail, 2.0 * zoom, if status == Status::Locked { Color32::from_rgb(0x26, 0x32, 0x4a) } else { cat });

            let font = FontId::proportional(13.5 * zoom);
            let lines = wrap_name(&skill.name);
            let line_h = 15.0 * zoom;
            let start_y = center.y - line_h * (lines.len() as f32 - 1.0) / 2.0 - 4.0 * zoom;
            for (i, line) in lines.iter().enumerate() {
                painter.text(
                    egui::pos2(node_rect.left() + 20.0 * zoom, start_y + i as f32 * line_h),
                    Align2::LEFT_CENTER,
                    line,
                    font.clone(),
                    text,
                );
            }

            // tier pips
            for i in 0..4 {
                let enabled = i <= skill.tier;
                let c = if enabled {
                    if status == Status::Locked { Color32::from_rgb(0x3d, 0x4a, 0x5e) } else { theme::alpha(cat, 235) }
                } else {
                    Color32::from_rgb(0x21, 0x2b, 0x3a)
                };
                painter.circle_filled(
                    egui::pos2(node_rect.left() + 21.0 * zoom + i as f32 * 10.0 * zoom, node_rect.bottom() - 13.0 * zoom),
                    3.1 * zoom,
                    c,
                );
            }

            // status badge
            let badge = egui::pos2(node_rect.right() - 19.0 * zoom, node_rect.top() + 19.0 * zoom);
            let dot = 8.0 * zoom;
            match status {
                Status::Completed => {
                    painter.circle_filled(badge, dot, Color32::from_rgb(0x38, 0xd9, 0xa9));
                    painter.text(badge, Align2::CENTER_CENTER, "✓", FontId::proportional(10.0 * zoom), Color32::from_rgb(0x06, 0x23, 0x1a));
                }
                Status::Training => {
                    painter.circle_filled(badge, dot, ORANGE);
                    painter.text(badge, Align2::CENTER_CENTER, "▶", FontId::proportional(8.0 * zoom), Color32::from_rgb(0x20, 0x14, 0x0a));
                }
                Status::Available => {
                    painter.circle_stroke(badge, dot * 0.6, Stroke::new(1.6 * zoom, theme::alpha(cat, 200)));
                }
                Status::Locked => {
                    painter.circle_stroke(badge, dot * 0.55, Stroke::new(1.4 * zoom, Color32::from_rgb(0x5d, 0x6a, 0x80)));
                }
            }

            // rank badge
            if self.settings.effects {
                if let Some(rank) = self.ranks.get(&skill.id).copied().filter(|r| *r > 0) {
                    let pos = egui::pos2(node_rect.right() - 17.0 * zoom, node_rect.bottom() - 15.0 * zoom);
                    let c = theme::hex(self.d.rank_color(rank));
                    painter.circle_filled(pos, 8.5 * zoom, theme::blend(c, t.bg2, 0.72));
                    painter.circle_stroke(pos, 8.5 * zoom, Stroke::new(1.0, c));
                    painter.text(pos, Align2::CENTER_CENTER, format!("{rank}"), FontId::proportional(9.0 * zoom), Color32::WHITE);
                }
            }
        }

        self.tree.hover = hit.clone();
        if resp.clicked() {
            if let Some(id) = hit {
                self.tree.selected = Some(id);
                self.tree.record.clear();
            }
        }
    }

    fn tree_detail(&mut self, ui: &mut Ui) {
        let t = self.theme.clone();
        let Some(sid) = self.tree.selected.clone() else {
            theme::card(ui, &t, "Skill details", |ui| {
                ui.label(t.body("Select a skill in the tree to see its progression, its exercises and your records."));
                ui.add_space(6.0);
                ui.label(t.dim("Completed skills unlock everything that depends on them."));
            });
            return;
        };
        let Some(skill) = self.d.skill(&sid) else { return };
        let skill = skill.clone();
        let status = logic::status(self.d, &self.progress, &sid);
        let cat = theme::hex(self.d.category_color(&skill.category));

        theme::card(ui, &t, "", |ui| {
            ui.label(RichText::new(&skill.name).size(21.0 * t.scale).strong().color(Color32::WHITE));
            ui.horizontal(|ui| {
                theme::chip(ui, &t, self.d.category_label(&skill.category), cat);
                theme::chip(ui, &t, self.d.tier(skill.tier), theme::hex("#9aa4b2"));
                let status_color = match status {
                    Status::Locked => theme::hex("#667085"),
                    Status::Available => theme::hex("#4dd0e1"),
                    Status::Training => ORANGE,
                    Status::Completed => theme::hex("#69db7c"),
                };
                theme::chip(ui, &t, status.label(), status_color);
            });
            ui.add_space(4.0);
            ui.label(t.body(&skill.description));
        });
        ui.add_space(8.0);

        if status == Status::Locked {
            let missing = logic::missing_prereqs(self.d, &self.progress, &sid);
            theme::card(ui, &t, "Prerequisites", |ui| {
                ui.label(t.body(format!("Complete first: {}", missing.join(", "))));
            });
            ui.add_space(8.0);
        }

        if !skill.steps.is_empty() {
            theme::card(ui, &t, "Progression", |ui| {
                for (i, step) in skill.steps.iter().enumerate() {
                    ui.label(t.body(format!("{}. {}", i + 1, step)));
                }
            });
            ui.add_space(8.0);
        }

        if !skill.exercises.is_empty() {
            theme::card(ui, &t, "Recommended training", |ui| {
                for rx in &skill.exercises {
                    ui.label(t.body(format!("• {}", rx)));
                }
            });
            ui.add_space(8.0);
        }

        if !skill.regressions.is_empty() {
            theme::card(ui, &t, "Regressions", |ui| {
                ui.label(t.body(skill.regressions.join(" · ")));
            });
            ui.add_space(8.0);
        }

        theme::card(ui, &t, "Benchmark", |ui| {
            let best = self.bests.get(&sid).map(|b| b.0).unwrap_or(0.0);
            if skill.target > 0.0 {
                ui.label(t.body(format!("Target: {} {}", logic::fmt_num(skill.target), skill.unit)));
                theme::bar(ui, &t, (best / skill.target) as f32, cat, 8.0);
            }
            ui.label(t.dim(format!(
                "Best recorded: {} {}{}",
                logic::fmt_num(best),
                skill.unit,
                self.bests.get(&sid).map(|b| format!("  ({})", b.1)).unwrap_or_default()
            )));
        });
        ui.add_space(8.0);

        if !skill.note.is_empty() {
            theme::card(ui, &t, "Note", |ui| {
                ui.label(t.dim(&skill.note));
            });
            ui.add_space(8.0);
        }

        theme::card(ui, &t, "Log a record", |ui| {
            ui.horizontal(|ui| {
                ui.add(egui::TextEdit::singleline(&mut self.tree.record).desired_width(90.0).hint_text(skill.unit.clone()));
                if ui.button("Save").clicked() {
                    if let Ok(value) = self.tree.record.trim().replace(',', ".").parse::<f64>() {
                        crate::db::add_record(&self.conn, &sid, value);
                        let reached_target = skill.target > 0.0 && value >= skill.target;
                        self.tree.record.clear();
                        self.reload();
                        self.sync_xp();
                        if reached_target && status != Status::Completed {
                            crate::db::set_status(&self.conn, &sid, Some("completed"));
                            self.reload();
                            self.sync_xp();
                            self.notify(format!("{} completed!", skill.name));
                        } else {
                            self.notify(format!("Record saved: {} {}", logic::fmt_num(value), skill.unit));
                        }
                    }
                }
            });
            ui.add_space(4.0);
            ui.horizontal(|ui| {
                if ui.button("Start training").clicked() {
                    crate::db::set_status(&self.conn, &sid, Some("training"));
                    self.reload();
                }
                if status == Status::Completed {
                    if ui.button("Reopen").clicked() {
                        crate::db::set_status(&self.conn, &sid, None);
                        self.reload();
                    }
                } else if ui.button("Mark completed").clicked() {
                    crate::db::set_status(&self.conn, &sid, Some("completed"));
                    self.reload();
                    self.sync_xp();
                    self.notify(format!("{} marked completed", skill.name));
                }
            });
        });
    }
}
