//! Application shell: navigation, shared state and the page dispatch.
use crate::data::{data, Data};
use crate::db;
use crate::logic;
use crate::theme::{self, Theme};
use eframe::egui::{self, Align, Color32, Context, Layout, RichText, ScrollArea, Stroke, Ui, Vec2};
use rusqlite::Connection;
use std::collections::HashMap;
use std::time::Instant;

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Page {
    Tree,
    Workouts,
    Library,
    Running,
    History,
    Dashboard,
    Ranks,
    Achievements,
    Coach,
    Settings,
}

impl Page {
    pub const ALL: [(Page, &'static str); 10] = [
        (Page::Tree, "Skill Tree"),
        (Page::Workouts, "Workouts"),
        (Page::Library, "Library"),
        (Page::Running, "Running"),
        (Page::History, "History"),
        (Page::Dashboard, "Dashboard"),
        (Page::Ranks, "Ranks"),
        (Page::Achievements, "Achievements"),
        (Page::Coach, "Coach"),
        (Page::Settings, "Settings"),
    ];
}

pub struct TreeState {
    pub selected: Option<String>,
    pub hover: Option<String>,
    pub zoom: f32,
    pub pan: Vec2,
    pub init: bool,
    pub record: String,
}

impl Default for TreeState {
    fn default() -> Self {
        Self { selected: None, hover: None, zoom: 0.62, pan: Vec2::new(0.0, 40.0), init: false, record: String::new() }
    }
}

pub struct LibraryState {
    pub query: String,
    pub category: Option<String>,
    pub selected: Option<String>,
}

impl Default for LibraryState {
    fn default() -> Self {
        Self { query: String::new(), category: None, selected: None }
    }
}

#[derive(Clone)]
pub struct WorkoutEditor {
    pub id: Option<i64>,
    pub name: String,
    pub description: String,
    pub style: String,
    pub entries: Vec<db::Entry>,
}

pub struct WorkoutsState {
    pub chosen: Option<i64>,
    pub editor: Option<WorkoutEditor>,
    pub pick_category: String,
    pub session_sets: Vec<db::SetRow>,
    pub session_id: Option<i64>,
    pub started: Option<Instant>,
    pub elapsed: i64,
    pub rest_until: Option<Instant>,
    pub rest_total: i64,
}

impl Default for WorkoutsState {
    fn default() -> Self {
        Self {
            chosen: None,
            editor: None,
            pick_category: "push".into(),
            session_sets: Vec::new(),
            session_id: None,
            started: None,
            elapsed: 0,
            rest_until: None,
            rest_total: 0,
        }
    }
}

pub struct RunningState {
    pub km: f64,
    pub minutes: i64,
    pub seconds: i64,
}

impl Default for RunningState {
    fn default() -> Self {
        Self { km: 5.0, minutes: 25, seconds: 0 }
    }
}

pub struct SettingsState {
    pub accent: String,
    pub background: String,
    pub corners: String,
    pub font_size: f32,
    pub grid: bool,
    pub effects: bool,
}

impl Default for SettingsState {
    fn default() -> Self {
        Self {
            accent: "#4dabf7".into(),
            background: "charcoal".into(),
            corners: "rounded".into(),
            font_size: 10.0,
            grid: true,
            effects: true,
        }
    }
}

pub struct App {
    pub conn: Connection,
    pub d: &'static Data,
    pub theme: Theme,
    pub page: Page,
    pub progress: HashMap<String, String>,
    pub bests: HashMap<String, (f64, String)>,
    pub toast: Option<(String, Instant)>,
    pub tree: TreeState,
    pub library: LibraryState,
    pub workouts: WorkoutsState,
    pub running: RunningState,
    pub settings: SettingsState,
    pub layout: logic::TreeLayout,
    pub ranks: HashMap<String, usize>,
    pub confirm_delete: Option<i64>,
    pub coach: crate::assistant::Chat,
}

impl App {
    pub fn new(cc: &eframe::CreationContext<'_>) -> Self {
        let d = data();
        let conn = db::open().expect("open progress.db");
        let settings = SettingsState {
            accent: db::get_setting(&conn, "accent", "#4dabf7"),
            background: db::get_setting(&conn, "bg", "charcoal"),
            corners: db::get_setting(&conn, "corners", "rounded"),
            font_size: db::get_setting(&conn, "font_size", "10").parse().unwrap_or(10.0),
            grid: db::get_setting(&conn, "tree_grid", "1") == "1",
            effects: db::get_setting(&conn, "effects", "1") == "1",
        };
        let theme = Theme::new(&settings.accent, &settings.background, &settings.corners, settings.font_size);
        theme.apply(&cc.egui_ctx);
        let progress = db::progress_map(&conn);
        let bests = db::bests(&conn);
        let layout = logic::layout(d);
        db::sync_xp(&conn, d);
        Self {
            conn,
            d,
            theme,
            page: Page::Tree,
            progress,
            bests,
            toast: None,
            tree: TreeState::default(),
            library: LibraryState::default(),
            workouts: WorkoutsState::default(),
            running: RunningState::default(),
            settings,
            layout,
            ranks: HashMap::new(),
            confirm_delete: None,
            coach: crate::assistant::Chat::default(),
        }
    }

    pub fn reload(&mut self) {
        self.progress = db::progress_map(&self.conn);
        self.bests = db::bests(&self.conn);
        let st = db::stats(&self.conn);
        let done: std::collections::HashSet<String> = self
            .progress
            .iter()
            .filter(|(_, s)| s.as_str() == "completed")
            .map(|(k, _)| k.clone())
            .collect();
        let mut ranks = HashMap::new();
        for track in logic::build_tracks(self.d) {
            let res = logic::evaluate(&track, &st.bests_by_exercise, &done, self.d.ranks.max_rank);
            if !track.exercise_id.is_empty() {
                ranks.insert(track.exercise_id.clone(), res.rank);
            }
        }
        self.ranks = ranks;
    }

    pub fn notify(&mut self, text: impl Into<String>) {
        self.toast = Some((text.into(), Instant::now()));
    }

    pub fn sync_xp(&mut self) {
        let unlocked = db::sync_xp(&self.conn, self.d);
        self.reload();
        if let Some((name, xp)) = unlocked.last() {
            self.notify(format!("Achievement unlocked: {name} (+{xp} XP)"));
        }
    }

    pub fn apply_theme(&mut self, ctx: &Context) {
        self.theme = Theme::new(&self.settings.accent, &self.settings.background, &self.settings.corners, self.settings.font_size);
        self.theme.apply(ctx);
        db::set_setting(&self.conn, "accent", &self.settings.accent);
        db::set_setting(&self.conn, "bg", &self.settings.background);
        db::set_setting(&self.conn, "corners", &self.settings.corners);
        db::set_setting(&self.conn, "font_size", &format!("{}", self.settings.font_size));
        db::set_setting(&self.conn, "tree_grid", if self.settings.grid { "1" } else { "0" });
        db::set_setting(&self.conn, "effects", if self.settings.effects { "1" } else { "0" });
    }

    // ----------------------------------------------------------- chrome
    fn top_bar(&mut self, ctx: &Context) {
        let t = self.theme.clone();
        egui::TopBottomPanel::top("topbar")
            .frame(
                egui::Frame::none()
                    .fill(theme::blend(Color32::from_rgb(0x10, 0x15, 0x1f), t.bg, 0.85))
                    .stroke(Stroke::new(1.0, t.line))
                    .inner_margin(egui::Margin::symmetric(16, 8)),
            )
            .show(ctx, |ui| {
                ui.horizontal(|ui| {
                    ui.add_space(2.0);
                    ui.label(RichText::new("CALIX").size(21.0 * t.scale).strong().color(Color32::WHITE));
                    ui.label(RichText::new("CALISTHENICS PROGRESSION").size(9.0 * t.scale).color(t.muted));
                });
                // The tabs wrap over two rows on a narrow window, so they get the full width
                // here instead of the space left next to the brand.
                ui.horizontal_wrapped(|ui| {
                    ui.spacing_mut().item_spacing.x = 6.0;
                    ui.spacing_mut().item_spacing.y = 4.0;
                    for (page, label) in Page::ALL {
                        let selected = self.page == page;
                        if theme::pill_button(ui, &t, label, selected).clicked() {
                            self.page = page;
                        }
                    }
                });
            });
    }

    fn status_bar(&mut self, ctx: &Context) {
        let t = self.theme.clone();
        let level = logic::level_info(self.d, db::total_xp(&self.conn));
        let done = self.progress.values().filter(|s| s.as_str() == "completed").count();
        egui::TopBottomPanel::bottom("statusbar")
            .frame(
                egui::Frame::none()
                    .fill(theme::blend(Color32::from_rgb(0x09, 0x0c, 0x12), t.bg, 0.5))
                    .stroke(Stroke::new(1.0, t.line))
                    .inner_margin(egui::Margin::symmetric(16, 5)),
            )
            .show(ctx, |ui| {
                ui.horizontal(|ui| {
                    ui.label(
                        RichText::new(format!("Level {} · {}", level.level, level.title))
                            .size(12.0 * t.scale)
                            .strong()
                            .color(theme::hex(&level.color)),
                    );
                    ui.label(t.dim(format!("{} / {} XP", level.into, level.need.max(1))));
                    ui.add_space(14.0);
                    ui.label(t.dim(format!("{} of {} skills completed", done, self.d.skills.items.len())));
                    ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                        ui.label(t.dim(db::db_path().display().to_string()));
                    });
                });
            });
    }

    fn toast_bar(&mut self, ctx: &Context) {
        let Some((text, at)) = self.toast.clone() else { return };
        if at.elapsed().as_secs_f32() > 5.0 {
            self.toast = None;
            return;
        }
        let t = self.theme.clone();
        egui::TopBottomPanel::bottom("toast")
            .frame(
                egui::Frame::none()
                    .fill(theme::blend(t.accent, t.bg, 0.16))
                    .stroke(Stroke::new(1.0, theme::alpha(t.accent, 120)))
                    .inner_margin(egui::Margin::symmetric(16, 8)),
            )
            .show(ctx, |ui| {
                ui.horizontal(|ui| {
                    ui.label(RichText::new(text).size(12.5 * t.scale).color(Color32::WHITE));
                    ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                        if ui.button("dismiss").clicked() {
                            self.toast = None;
                        }
                    });
                });
            });
        ctx.request_repaint_after(std::time::Duration::from_millis(250));
    }

    pub fn detail_card(&self, ui: &mut Ui, title: &str, body: &str) {
        let t = &self.theme;
        theme::card(ui, t, title, |ui| {
            ui.label(t.body(body));
        });
    }

    pub fn scroll_page(ui: &mut Ui, add: impl FnOnce(&mut Ui)) {
        ScrollArea::vertical().auto_shrink([false, false]).show(ui, add);
    }

    pub fn page_title(&self, ui: &mut Ui, title: &str, subtitle: &str) {
        ui.label(self.theme.title(title));
        if !subtitle.is_empty() {
            ui.label(self.theme.dim(subtitle));
        }
        ui.add_space(4.0);
    }
}

impl eframe::App for App {
    fn update(&mut self, ctx: &Context, _frame: &mut eframe::Frame) {
        self.top_bar(ctx);
        self.status_bar(ctx);
        self.toast_bar(ctx);
        if self.workouts.started.is_some() {
            if let Some(start) = self.workouts.started {
                self.workouts.elapsed = start.elapsed().as_secs() as i64;
            }
            ctx.request_repaint_after(std::time::Duration::from_millis(500));
        }
        egui::CentralPanel::default()
            .frame(egui::Frame::none().fill(self.theme.bg).inner_margin(egui::Margin::same(16)))
            .show(ctx, |ui| {
                self.theme.backdrop(ui);
                match self.page {
                    Page::Tree => self.page_tree(ui),
                    Page::Workouts => self.page_workouts(ui),
                    Page::Library => self.page_library(ui),
                    Page::Running => self.page_running(ui),
                    Page::History => self.page_history(ui),
                    Page::Dashboard => self.page_dashboard(ui),
                    Page::Ranks => self.page_ranks(ui),
                    Page::Achievements => self.page_achievements(ui),
                    Page::Coach => self.page_coach(ui),
                    Page::Settings => self.page_settings(ui),
                }
            });
    }

    fn save(&mut self, _storage: &mut dyn eframe::Storage) {}
}
