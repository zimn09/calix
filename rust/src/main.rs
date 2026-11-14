//! CALIX – offline calisthenics trainer, Rust desktop edition.
//!
//! A port of the Python/PySide6 PC app: same skill tree, exercise library,
//! ranks and achievements, the same SQLite schema, rebuilt with egui.
mod app;
mod assistant;
mod data;
mod db;
mod logic;
mod pages;
mod theme;

fn main() -> eframe::Result<()> {
    let options = eframe::NativeOptions {
        viewport: eframe::egui::ViewportBuilder::default()
            .with_inner_size([1440.0, 900.0])
            .with_min_inner_size([1000.0, 640.0])
            .with_title("CALIX"),
        ..Default::default()
    };
    eframe::run_native(
        "CALIX",
        options,
        Box::new(|cc| Ok(Box::new(app::App::new(cc)))),
    )
}
