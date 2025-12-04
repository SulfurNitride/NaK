//! Simple pages: Getting Started, Marketplace, Settings

use eframe::egui;
use crate::app::MyApp;
use super::UiExt;

pub fn render_getting_started(_app: &MyApp, ui: &mut egui::Ui) {
    ui.heading("Welcome to NaK (Rust Edition)");
    ui.separator();
    ui.label("This tool helps you manage modding tools on Linux without the hassle.");

    ui.add_space(20.0);
    ui.subheading("Quick Start Steps:");
    ui.label("1. Go to 'Proton Tools' and install the latest GE-Proton.");
    ui.label("2. Go to 'Mod Managers' to set up MO2 or Vortex.");
    ui.label("3. Use the 'Marketplace' to find plugins (Coming Soon).");
}

pub fn render_marketplace(_app: &MyApp, ui: &mut egui::Ui) {
    ui.heading("Marketplace");
    ui.separator();

    // Placeholder Grid for Marketplace items
    egui::ScrollArea::vertical().show(ui, |ui| {
        ui.horizontal_wrapped(|ui| {
            for i in 1..=6 {
                egui::Frame::group(ui.style())
                    .rounding(egui::Rounding::same(4.0))
                    .inner_margin(10.0)
                    .show(ui, |ui| {
                        ui.set_width(150.0);
                        ui.set_height(120.0);
                        ui.vertical_centered(|ui| {
                            ui.label(egui::RichText::new("📦").size(24.0));
                            ui.strong(format!("Plugin {}", i));
                            ui.small("Description of plugin...");
                            ui.add_space(5.0);
                            if ui.button("Install").clicked() { }
                        });
                    });
                 ui.add_space(10.0);
            }
        });
    });
}

pub fn render_settings(_app: &mut MyApp, ui: &mut egui::Ui) {
     ui.heading("Settings");
     ui.separator();
     ui.label("Application configuration.");
}
