//! Coach page: a chat with the local rule engine, headed by a drawn coach avatar.
use crate::app::App;
use crate::assistant;
use crate::theme;
use eframe::egui::{self, Align, Color32, Frame, Layout, RichText, ScrollArea, Sense, Stroke, TextEdit, Ui, Vec2};

const CHIPS: [&str; 6] = [
    "hey",
    "did 3x12 push ups",
    "and 10 more",
    "no, 15 reps",
    "sum of reps this week",
    "what should I train today?",
];

/// A small coach drawn from primitives: disc, head, shoulders. No image files.
fn coach_avatar(ui: &mut Ui, size: f32, accent: Color32) -> egui::Response {
    let (rect, response) = ui.allocate_exact_size(Vec2::splat(size), Sense::hover());
    let p = ui.painter();
    let c = rect.center();
    p.circle_filled(c, size * 0.5, theme::alpha(accent, 28));
    p.circle_stroke(c, size * 0.5 - 0.5, Stroke::new(1.0, theme::alpha(accent, 110)));
    p.circle_filled(egui::pos2(c.x, c.y - size * 0.14), size * 0.17, accent);
    let body = egui::Rect::from_center_size(
        egui::pos2(c.x, c.y + size * 0.30),
        egui::vec2(size * 0.62, size * 0.44),
    );
    p.rect_filled(body, size * 0.22, accent);
    p.rect_filled(
        egui::Rect::from_center_size(egui::pos2(c.x, c.y + size * 0.24), egui::vec2(size * 0.20, size * 0.07)),
        2.0,
        theme::alpha(Color32::BLACK, 70),
    );
    response
}

fn bubble(ui: &mut Ui, t: &theme::Theme, you: bool, text: &str) {
    let fill = if you {
        theme::alpha(Color32::from_rgb(0x4d, 0xab, 0xf7), 34)
    } else {
        Color32::from_rgb(0x14, 0x1c, 0x28)
    };
    let stroke = if you {
        theme::alpha(Color32::from_rgb(0x4d, 0xab, 0xf7), 90)
    } else {
        Color32::from_rgb(0x1f, 0x2a, 0x3a)
    };
    Frame::none()
        .fill(fill)
        .stroke(Stroke::new(1.0, stroke))
        .rounding(10.0)
        .inner_margin(egui::Margin::symmetric(10, 8))
        .show(ui, |ui| {
            ui.set_max_width(470.0);
            ui.label(
                RichText::new(text)
                    .size(12.0 * t.scale)
                    .color(if you { Color32::from_rgb(0xe6, 0xed, 0xf7) } else { t.text }),
            );
        });
}

impl App {
    pub fn page_coach(&mut self, ui: &mut Ui) {
        let t = self.theme.clone();
        let accent = theme::hex("#4dabf7");
        self.page_title(
            ui,
            "Coach",
            "Understands exercise names, numbers and dates on this machine — no model, no network.",
        );
        ui.add_space(6.0);

        // ---- the coach himself
        theme::card(ui, &t, "", |ui| {
            ui.horizontal(|ui| {
                coach_avatar(ui, 52.0, accent);
                ui.add_space(6.0);
                ui.vertical(|ui| {
                    ui.add_space(2.0);
                    ui.label(RichText::new("Coach").size(15.0 * t.scale).strong().color(Color32::WHITE));
                    ui.label(
                        RichText::new("• local engine · no model · works offline")
                            .size(9.5 * t.scale)
                            .color(theme::hex("#38d9a9")),
                    );
                    ui.label(t.dim("Log what you did, ask about your numbers, or ask what to train next."));
                });
            });
        });
        ui.add_space(8.0);

        let has_pending = !self.coach.pending.is_empty();
        let mut send: Option<String> = None;
        let mut do_apply = false;
        let mut discard = false;

        theme::card(ui, &t, "Conversation", |ui| {
            // A fixed viewport keeps the chat readable and the layout stable when a
            // confirmation card appears.
            let height = 360.0;
            ui.allocate_ui_with_layout(
                egui::vec2(ui.available_width(), height),
                Layout::top_down(Align::Min),
                |ui| {
                    ScrollArea::vertical()
                        .stick_to_bottom(true)
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
                                ui.add_space(6.0);
                            }
                        });
                },
            );

            if has_pending {
                ui.add_space(2.0);
                theme::card(ui, &t, "Save this to your log?", |ui| {
                    for line in self.coach.pending_text.lines() {
                        ui.label(t.body(line));
                    }
                    ui.add_space(4.0);
                    ui.horizontal(|ui| {
                        if ui.button("Save").clicked() {
                            do_apply = true;
                        }
                        if ui.button("Discard").clicked() {
                            discard = true;
                        }
                    });
                });
            }
            ui.add_space(4.0);
            ui.horizontal_wrapped(|ui| {
                ui.spacing_mut().item_spacing.x = 6.0;
                for chip in CHIPS {
                    if theme::pill_button(ui, &t, chip, false).clicked() {
                        send = Some(chip.to_string());
                    }
                }
            });
            ui.add_space(4.0);
            ui.horizontal(|ui| {
                let width = (ui.available_width() - 80.0).max(120.0);
                let response = ui.add_sized(
                    [width, 28.0],
                    TextEdit::singleline(&mut self.coach.input).hint_text("Tell the coach what you did…"),
                );
                let entered = response.lost_focus() && ui.input(|i| i.key_pressed(egui::Key::Enter));
                if ui.button("Send").clicked() || entered {
                    if !self.coach.input.trim().is_empty() {
                        send = Some(self.coach.input.clone());
                        self.coach.input.clear();
                    }
                    response.request_focus();
                }
            });
        });

        ui.add_space(4.0);
        ui.label(t.dim(&self.coach.detail));

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
