//! Coach page: a chat with the local rule engine, headed by a drawn coach avatar.
use crate::app::App;
use crate::assistant;
use crate::theme;
use eframe::egui::{
    self, Align, Color32, Frame, Layout, Margin, RichText, ScrollArea, Sense, Stroke, TextEdit, Ui, Vec2,
};

const CHIPS: [&str; 6] = [
    "hey",
    "did 3x12 push ups",
    "and 10 more",
    "no, 15 reps",
    "sum of reps this week",
    "what should I train today?",
];

const OK: Color32 = Color32::from_rgb(0x4a, 0xd9, 0xa9);

/// A small coach drawn from primitives: disc, ring, head, shoulders. No image files.
fn coach_avatar(ui: &mut Ui, size: f32, accent: Color32) -> egui::Response {
    let (rect, response) = ui.allocate_exact_size(Vec2::splat(size), Sense::hover());
    let p = ui.painter();
    let c = rect.center();
    p.circle_filled(c, size * 0.5, theme::alpha(accent, 42));
    p.circle_stroke(c, size * 0.45, Stroke::new(1.0, theme::alpha(accent, 120)));
    p.circle_filled(egui::pos2(c.x, c.y - size * 0.135), size * 0.145, accent);
    let body = egui::Rect::from_center_size(
        egui::pos2(c.x, c.y + size * 0.30),
        egui::vec2(size * 0.61, size * 0.47),
    );
    p.rect_filled(body, size * 0.235, accent);
    p.rect_filled(
        egui::Rect::from_center_size(
            egui::pos2(c.x, c.y + size * 0.24),
            egui::vec2(size * 0.13, size * 0.075),
        ),
        size * 0.035,
        theme::alpha(Color32::BLACK, 80),
    );
    response
}

fn bubble(ui: &mut Ui, t: &theme::Theme, you: bool, text: &str) {
    let (fill, stroke, color) = if you {
        (
            theme::alpha(t.accent, 34),
            theme::alpha(t.accent, 105),
            Color32::from_rgb(0xea, 0xf3, 0xff),
        )
    } else {
        (
            theme::blend(Color32::from_rgb(0x15, 0x1d, 0x2b), t.bg, 0.55),
            t.line,
            Color32::from_rgb(0xd9, 0xe3, 0xf2),
        )
    };
    Frame::none()
        .fill(fill)
        .stroke(Stroke::new(1.0, stroke))
        .rounding(14.0)
        .inner_margin(Margin::symmetric(13, 10))
        .show(ui, |ui| {
            ui.set_max_width(460.0);
            ui.label(RichText::new(text).size(12.5 * t.scale).color(color));
        });
}

fn accent_button(ui: &mut Ui, t: &theme::Theme, label: &str) -> egui::Response {
    let fill = theme::blend(t.accent, Color32::BLACK, 0.72);
    ui.add(
        egui::Button::new(RichText::new(label).strong().color(Color32::WHITE))
            .fill(fill)
            .rounding(t.radius)
            .min_size(Vec2::new(92.0, 30.0)),
    )
}

impl App {
    pub fn page_coach(&mut self, ui: &mut Ui) {
        let t = self.theme.clone();
        let accent = t.accent;
        let scale = t.scale;
        // The conversation is the whole page: no heading, no hero card, no footer.
        let panel_h = ui.available_height();

        let has_pending = !self.coach.pending.is_empty();
        let mut send: Option<String> = None;
        let mut do_apply = false;
        let mut discard = false;

        theme::card(ui, &t, "", |ui| {
            // A bordered viewport keeps the chat readable. It takes the height the card
            // has left, so the conversation fills the screen.
            let viewport = (panel_h - 118.0).max(240.0);
            Frame::none()
                .fill(theme::blend(Color32::BLACK, t.bg, 0.55))
                .stroke(Stroke::new(1.0, t.line))
                .rounding(t.radius + 2.0)
                .inner_margin(Margin::same(12))
                .show(ui, |ui| {
                    ui.set_width(ui.available_width());
                    ui.allocate_ui_with_layout(
                        egui::vec2(ui.available_width(), viewport),
                        Layout::top_down(Align::Min),
                        |ui| {
                            ScrollArea::vertical()
                                .auto_shrink([false, false])
                                .stick_to_bottom(true)
                                .min_scrolled_height(viewport - 24.0)
                                .max_height(viewport - 24.0)
                                .show(ui, |ui| {
                                    ui.set_width(ui.available_width());
                                    for (you, text) in self.coach.messages.clone() {
                                        if you {
                                            ui.with_layout(Layout::right_to_left(Align::Min), |ui| {
                                                bubble(ui, &t, true, &text);
                                            });
                                        } else {
                                            ui.horizontal_top(|ui| {
                                                coach_avatar(ui, 28.0, accent);
                                                bubble(ui, &t, false, &text);
                                            });
                                        }
                                        ui.add_space(8.0);
                                    }
                                });
                        },
                    );
                });

            if has_pending {
                ui.add_space(6.0);
                Frame::none()
                    .fill(theme::alpha(accent, 22))
                    .stroke(Stroke::new(1.0, theme::alpha(accent, 110)))
                    .rounding(t.radius + 2.0)
                    .inner_margin(Margin::same(13))
                    .show(ui, |ui| {
                        ui.set_width(ui.available_width());
                        ui.label(
                            RichText::new("SAVE THIS TO YOUR LOG?")
                                .size(10.0 * scale)
                                .strong()
                                .color(theme::blend(accent, Color32::WHITE, 0.55)),
                        );
                        for line in self.coach.pending_text.lines() {
                            ui.label(RichText::new(line).size(12.5 * scale).color(Color32::from_rgb(0xdc, 0xe7, 0xf7)));
                        }
                        ui.add_space(4.0);
                        ui.horizontal(|ui| {
                            if accent_button(ui, &t, "Save").clicked() {
                                do_apply = true;
                            }
                            if ui
                                .add(
                                    egui::Button::new(RichText::new("Discard").color(t.muted))
                                        .rounding(t.radius)
                                        .min_size(Vec2::new(92.0, 30.0)),
                                )
                                .clicked()
                            {
                                discard = true;
                            }
                        });
                    });
            }

            ui.add_space(8.0);
            ui.horizontal_wrapped(|ui| {
                ui.spacing_mut().item_spacing.x = 6.0;
                ui.spacing_mut().item_spacing.y = 6.0;
                for chip in CHIPS {
                    if theme::chip_button(ui, &t, chip)
                        .on_hover_cursor(egui::CursorIcon::PointingHand)
                        .clicked()
                    {
                        send = Some(chip.to_string());
                    }
                }
            });

            ui.add_space(8.0);
            ui.horizontal(|ui| {
                let width = (ui.available_width() - 100.0).max(120.0);
                let response = ui.add_sized(
                    [width, 30.0],
                    TextEdit::singleline(&mut self.coach.input)
                        .hint_text("Tell the coach what you did, or ask a question…"),
                );
                let entered = response.lost_focus() && ui.input(|i| i.key_pressed(egui::Key::Enter));
                if accent_button(ui, &t, "Send").clicked() || entered {
                    if !self.coach.input.trim().is_empty() {
                        send = Some(self.coach.input.clone());
                        self.coach.input.clear();
                    }
                    response.request_focus();
                }
            });
        });

        if let Some(text) = send {
            self.coach_ask(text);
        }
        if do_apply {
            self.coach_apply();
        } else if discard {
            self.coach.pending.clear();
            self.coach.pending_text.clear();
            self.coach.detail = "Nothing was saved.".into();
        }
    }

    pub fn coach_ask(&mut self, text: String) {
        if text.trim().is_empty() {
            return;
        }
        let answer = assistant::ask_with(&self.conn, &text, self.coach.last.as_ref());
        self.coach.messages.push((true, text));
        self.coach.messages.push((false, answer.text.clone()));
        let mut detail = format!(
            "{} · {}% sure",
            answer.intent,
            (answer.confidence * 100.0).round() as i32
        );
        if !answer.entities.is_empty() {
            detail.push_str(&format!(" · understood {}", answer.entities.join(", ")));
        }
        self.coach.detail = detail;
        if answer.undo {
            self.coach.last = None;
        }
        self.coach.pending_text = answer
            .actions
            .iter()
            .map(|a| format!("• {}: {}", a.label(), a.describe()))
            .collect::<Vec<_>>()
            .join("\n");
        self.coach.pending = answer.actions;
        self.reload();
    }

    pub fn coach_apply(&mut self) {
        let notes = assistant::apply(&self.conn, &self.coach.pending.clone());
        if let Some(action) = self.coach.pending.first().cloned() {
            self.coach.last = Some(action);
        }
        for note in notes {
            self.coach.messages.push((false, note));
        }
        self.coach.pending.clear();
        self.coach.pending_text.clear();
        self.coach.detail = "Saved to your log.".into();
        self.sync_xp();
    }
}
