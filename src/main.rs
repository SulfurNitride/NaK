//! NaK - Linux Mod Manager Tool
//!
//! A tool to help manage modding tools (MO2, Vortex) on Linux via Proton/Wine.

use eframe::egui;

mod utils;
mod config;
mod wine;
mod installers;
mod scripts;
mod nxm;
mod app;
mod ui;
mod logging;

use app::MyApp;
use logging::{init_logger, log_info};

fn main() -> eframe::Result<()> {
    // Initialize NaK logging system (writes to ~/NaK/logs/)
    init_logger();
    log_info("NaK starting up...");

    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([900.0, 600.0])
            .with_min_inner_size([600.0, 400.0])
            .with_title("NaK"),
        ..Default::default()
    };

    eframe::run_native(
        "NaK",
        options,
        Box::new(|cc| {
            egui_extras::install_image_loaders(&cc.egui_ctx);
            Ok(Box::new(MyApp::default()))
        }),
    )
}
