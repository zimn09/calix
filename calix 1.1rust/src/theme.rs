//! Colour helpers, the egui style built from the user settings and a few
//! repeated widgets (cards, stat tiles, chips, section titles).
use eframe::egui::{
    self, Color32, Context, CornerRadius, FontFamily, FontId, Frame, Margin, Response, RichText,
    Sense, Stroke, TextStyle, Ui, Vec2,
};

pub fn hex(s: &str) -> Color32 {
    let s = s.trim_start_matches('#');
    if s.len() < 6 {
        return Color32::GRAY;
    }
    let r = u8::from_str_radix(&s[0..2], 16).unwrap_or(128);
    let g = u8::from_str_radix(&s[2..4], 16).unwrap_or(128);
    let b = u8::from_str_radix(&s[4..6], 16).unwrap_or(128);
    Color32::from_rgb(r, g, b)
}

pub fn alpha(c: Color32, a: u8) -> Color32 {
    Color32::from_rgba_unmultiplied(c.r(), c.g(), c.b(), a)
}

/// Mix `a` into `b` by `t` (0..1): 1.0 is pure `a`.
pub fn blend(a: Color32, b: Color32, t: f32) -> Color32 {
    let t = t.clamp(0.0, 1.0);
    let f = |x: u8, y: u8| (x as f32 * t + y as f32 * (1.0 - t)).round() as u8;
    Color32::from_rgb(f(a.r(), b.r()), f(a.g(), b.g()), f(a.b(), b.b()))
}

pub const ACCENTS: [(&str, &str); 6] = [
    ("Blue", "#4dabf7"),
    ("Purple", "#9775fa"),
    ("Red", "#ff6b6b"),
    ("Green", "#51cf66"),
    ("Orange", "#ff922b"),
    ("Teal", "#22b8cf"),
];

pub const BACKGROUNDS: [(&str, &str); 4] =
    [("Charcoal", "charcoal"), ("Pure black", "black"), ("Dark gray", "graphite"), ("Gradient", "gradient")];

#[derive(Clone)]
pub struct Theme {
    pub accent: Color32,
    pub bg: Color32,
    pub bg2: Color32,
    pub surface: Color32,
    pub surface2: Color32,
    pub line: Color32,
    pub line2: Color32,
    pub text: Color32,
    pub muted: Color32,
    pub radius: f32,
    pub scale: f32,
    pub preset: String,
}

impl Default for Theme {
    fn default() -> Self {
        Self::new("#4dabf7", "charcoal", "rounded", 10.0)
    }
}

impl Theme {
    pub fn new(accent: &str, preset: &str, corners: &str, font_size: f32) -> Self {
        let accent = hex(accent);
        let (bg, bg2) = match preset {
            "black" => (hex("#000000"), hex("#050608")),
            "graphite" => (hex("#15171b"), hex("#111317")),
            "gradient" => (hex("#080a0f"), blend(accent, hex("#080a0f"), 0.26)),
            _ => (hex("#06080d"), hex("#0b1017")),
        };
        let lift = if preset == "graphite" { 0.10 } else { 0.0 };
        let surface = blend(Color32::from_rgb(0x10, 0x17, 0x25), bg, 1.0 - lift);
        let surface2 = blend(Color32::from_rgb(0x0c, 0x11, 0x1a), bg, 1.0 - lift);
        let line = blend(Color32::from_rgb(0x1d, 0x27, 0x35), bg, 1.0 - lift);
        let line2 = blend(Color32::from_rgb(0x2b, 0x3a, 0x52), bg, 1.0 - lift);
        let radius = match corners {
            "sharp" => 4.0,
            "round" => 20.0,
            _ => 12.0,
        } * (font_size / 10.0).clamp(0.85, 1.25);
        Self {
            accent,
            bg,
            bg2,
            surface,
            surface2,
            line,
            line2,
            text: hex("#e9eef7"),
            muted: hex("#8593a8"),
            radius,
            scale: font_size / 10.0,
            preset: preset.to_string(),
        }
    }

    pub fn apply(&self, ctx: &Context) {
        let mut style = (*ctx.style()).clone();
        style.visuals = egui::Visuals::dark();
        style.visuals.panel_fill = self.bg;
        style.visuals.window_fill = self.surface;
        style.visuals.extreme_bg_color = self.surface2;
        style.visuals.faint_bg_color = self.surface;
        style.visuals.override_text_color = Some(self.text);
        style.visuals.selection.bg_fill = alpha(self.accent, 70);
        style.visuals.selection.stroke = Stroke::new(1.0, self.accent);
        style.visuals.widgets.noninteractive.bg_stroke = Stroke::new(1.0, self.line);
        style.visuals.widgets.inactive.bg_fill = self.surface;
        style.visuals.widgets.inactive.weak_bg_fill = self.surface;
        style.visuals.widgets.inactive.bg_stroke = Stroke::new(1.0, self.line2);
        style.visuals.widgets.hovered.bg_fill = blend(self.accent, self.surface, 0.16);
        style.visuals.widgets.hovered.weak_bg_fill = blend(self.accent, self.surface, 0.16);
        style.visuals.widgets.hovered.bg_stroke = Stroke::new(1.0, self.line2);
        style.visuals.widgets.active.bg_fill = blend(self.accent, self.surface, 0.26);
        style.visuals.widgets.active.weak_bg_fill = blend(self.accent, self.surface, 0.26);
        style.visuals.widgets.active.bg_stroke = Stroke::new(1.0, self.accent);
        style.visuals.widgets.inactive.corner_radius = CornerRadius::same(self.radius as u8);
        style.visuals.widgets.hovered.corner_radius = CornerRadius::same(self.radius as u8);
        style.visuals.widgets.active.corner_radius = CornerRadius::same(self.radius as u8);
        style.visuals.window_corner_radius = CornerRadius::same((self.radius + 4.0) as u8);
        style.visuals.menu_corner_radius = CornerRadius::same(self.radius as u8);
        style.spacing.item_spacing = Vec2::new(8.0, 8.0);
        style.spacing.button_padding = Vec2::new(12.0, 7.0);
        style.spacing.scroll.bar_width = 8.0;
        let scale = self.scale;
        style.text_styles.insert(TextStyle::Body, FontId::new(14.0 * scale, FontFamily::Proportional));
        style.text_styles.insert(TextStyle::Button, FontId::new(13.0 * scale, FontFamily::Proportional));
        style.text_styles.insert(TextStyle::Small, FontId::new(11.0 * scale, FontFamily::Proportional));
        style.text_styles.insert(TextStyle::Heading, FontId::new(22.0 * scale, FontFamily::Proportional));
        ctx.set_style(style);
    }

    /// Backdrop painted behind every page.
    pub fn backdrop(&self, ui: &Ui) {
        let rect = ui.max_rect();
        let painter = ui.painter();
        if self.preset == "gradient" {
            let mut mesh = egui::Mesh::default();
            mesh.colored_vertex(rect.left_top(), self.bg);
            mesh.colored_vertex(rect.right_top(), self.bg);
            mesh.colored_vertex(rect.right_bottom(), self.bg2);
            mesh.colored_vertex(rect.left_bottom(), self.bg2);
            mesh.add_triangle(0, 1, 2);
            mesh.add_triangle(0, 2, 3);
            painter.add(egui::Shape::mesh(mesh));
        } else {
            painter.rect_filled(rect, 0.0, self.bg);
        }
        // soft light falling from the top of the window
        let glow = egui::epaint::RectShape::filled(
            egui::Rect::from_center_size(
                egui::pos2(rect.center().x, rect.top() + 10.0),
                Vec2::new(rect.width() * 1.4, rect.height() * 0.9),
            ),
            (rect.height() * 0.45) as u8,
            alpha(Color32::WHITE, 6),
        );
        painter.add(egui::Shape::Rect(glow));
    }

    pub fn title(&self, text: &str) -> RichText {
        RichText::new(text).size(24.0 * self.scale).strong().color(Color32::WHITE)
    }

    pub fn heading(&self, text: &str) -> RichText {
        RichText::new(text).size(17.0 * self.scale).strong().color(Color32::WHITE)
    }

    pub fn section(&self, text: &str) -> RichText {
        RichText::new(text.to_uppercase()).size(10.0 * self.scale).strong().color(self.muted)
    }

    pub fn body(&self, text: impl Into<String>) -> RichText {
        RichText::new(text).size(13.5 * self.scale).color(self.text)
    }

    pub fn dim(&self, text: impl Into<String>) -> RichText {
        RichText::new(text).size(12.0 * self.scale).color(self.muted)
    }

    pub fn big(&self, text: impl Into<String>) -> RichText {
        RichText::new(text).size(26.0 * self.scale).strong().color(Color32::WHITE)
    }

    pub fn card_frame(&self) -> Frame {
        Frame::none()
            .fill(self.surface)
            .stroke(Stroke::new(1.0, self.line))
            .rounding(self.radius + 4.0)
            .inner_margin(Margin::same(14))
    }

    pub fn plain_frame(&self) -> Frame {
        Frame::none().fill(Color32::TRANSPARENT).inner_margin(Margin::same(0))
    }
}

/// A titled card. Returns the frame response so callers can size it.
pub fn card<R>(ui: &mut Ui, theme: &Theme, title: &str, add: impl FnOnce(&mut Ui) -> R) -> R {
    theme
        .card_frame()
        .show(ui, |ui| {
            ui.set_width(ui.available_width());
            if !title.is_empty() {
                ui.label(theme.section(title));
                ui.add_space(2.0);
            }
            add(ui)
        })
        .inner
}

pub fn stat_tile(ui: &mut Ui, theme: &Theme, title: &str, value: &str, sub: &str) {
    theme
        .card_frame()
        .show(ui, |ui| {
            ui.set_min_width(150.0);
            ui.label(theme.section(title));
            ui.label(theme.big(value));
            if !sub.is_empty() {
                ui.label(theme.dim(sub));
            }
        });
}

pub fn chip(ui: &mut Ui, theme: &Theme, text: &str, color: Color32) {
    Frame::none()
        .fill(alpha(color, 34))
        .stroke(Stroke::new(1.0, alpha(color, 150)))
        .rounding(theme.radius * 0.6)
        .inner_margin(Margin::symmetric(8, 3))
        .show(ui, |ui| {
            ui.label(RichText::new(text).size(11.0 * theme.scale).strong().color(color));
        });
}

pub fn bar(ui: &mut Ui, _theme: &Theme, fraction: f32, color: Color32, height: f32) -> Response {
    let width = ui.available_width();
    let (rect, resp) = ui.allocate_exact_size(Vec2::new(width, height), Sense::hover());
    let p = ui.painter();
    p.rect_filled(rect, height * 0.5, alpha(Color32::WHITE, 14));
    let filled = egui::Rect::from_min_size(rect.min, Vec2::new(width * fraction.clamp(0.0, 1.0), height));
    p.rect_filled(filled, height * 0.5, color);
    resp
}

/// A text input row with a label, used across the forms.
pub fn labelled<'a>(ui: &mut Ui, theme: &Theme, label: &str, add: impl FnOnce(&mut Ui) -> &'a mut Ui) {
    ui.horizontal(|ui| {
        ui.label(theme.dim(label));
        add(ui);
    });
}

pub fn pill_button(ui: &mut Ui, theme: &Theme, text: &str, selected: bool) -> Response {
    let text = RichText::new(text).size(13.0 * theme.scale).color(if selected { Color32::WHITE } else { theme.muted });
    let fill = if selected { blend(theme.accent, theme.bg, 0.18) } else { Color32::TRANSPARENT };
    ui.add(egui::Button::new(text).fill(fill).rounding(theme.radius).min_size(Vec2::new(0.0, 30.0)))
}
