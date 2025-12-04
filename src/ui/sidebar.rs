//! Sidebar navigation

use eframe::egui;
use crate::app::{MyApp, Page};

pub fn render_sidebar(app: &mut MyApp, _ctx: &egui::Context, ui: &mut egui::Ui, is_enabled: bool) {
    ui.heading("NaK");
    ui.add_space(10.0);

    if !app.missing_deps.is_empty() {
        ui.colored_label(egui::Color32::RED, "⚠ Missing Deps:");
        for dep in &app.missing_deps {
            ui.colored_label(egui::Color32::RED, format!("• {}", dep));
        }
        ui.small("Please install via OS package manager.");
        ui.separator();
    }

    let navigation_buttons = [
        (Page::GettingStarted, "Getting Started"),
        (Page::ModManagers, "Mod Managers"),
        (Page::Marketplace, "Marketplace"),
        (Page::ProtonTools, "Proton Tools"),
        (Page::Settings, "Settings"),
    ];

    for (page, label) in navigation_buttons {
        let is_selected = app.current_page == page;
        let is_enabled_page = page != Page::Marketplace; // Disable Marketplace

        if ui.add_enabled(!is_selected && is_enabled_page && is_enabled, egui::Button::new(label).min_size(egui::vec2(150.0, 30.0))).clicked() {
            app.current_page = page;
        }
        ui.add_space(5.0);
    }

    ui.with_layout(egui::Layout::bottom_up(egui::Align::Min), |ui| {
        ui.label("v0.1.0-rust");
        ui.separator();
    });
}
