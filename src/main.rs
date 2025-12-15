//! NaK - Linux Mod Manager Tool
//!
//! A tool to help manage modding tools (MO2, Vortex) on Linux via Proton/Wine.

use eframe::egui;

mod app;
mod config;
mod games;
mod installers;
mod logging;
mod nxm;
mod scripts;
mod ui;
mod utils;
mod wine;

use app::MyApp;
use logging::{init_logger, log_info};

fn main() -> eframe::Result<()> {
    // Initialize NaK logging system (writes to ~/NaK/logs/)
    init_logger();
    log_info("NaK starting up...");

    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([720.0, 720.0])
            .with_min_inner_size([720.0, 720.0])
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
