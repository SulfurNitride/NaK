//! Sidebar navigation

use crate::app::{MyApp, Page};
use eframe::egui;

pub fn render_sidebar(app: &mut MyApp, _ctx: &egui::Context, ui: &mut egui::Ui, is_enabled: bool) {
    ui.heading("NaK");
    ui.add_space(10.0);

    // Steam detection warning (critical)
    if !app.steam_detected {
        egui::Frame::none()
            .fill(egui::Color32::from_rgb(80, 20, 20))
            .rounding(egui::Rounding::same(4.0))
            .inner_margin(8.0)
            .show(ui, |ui| {
                ui.colored_label(egui::Color32::RED, "STEAM NOT DETECTED");
                ui.colored_label(
                    egui::Color32::from_rgb(255, 150, 150),
                    "NaK requires Steam to be installed.",
                );
                ui.colored_label(
                    egui::Color32::from_rgb(255, 150, 150),
                    "Please install Steam first.",
                );
            });
        ui.add_space(5.0);
        ui.separator();
    } else if let Some(path) = &app.steam_path {
        ui.small(format!("Steam: {}", path));
        ui.add_space(2.0);
    }

    let missing = app.missing_deps.lock().unwrap();
    if !missing.is_empty() {
        ui.colored_label(egui::Color32::RED, "Missing Deps:");
        for dep in missing.iter() {
            ui.colored_label(egui::Color32::RED, format!("- {}", dep));
        }
        ui.small("Please install via OS package manager.");
        ui.separator();
    }
    drop(missing); // Release lock early

    // Update available notification
    let update_available = app.update_info.lock().unwrap()
        .as_ref()
        .map(|i| i.is_update_available)
        .unwrap_or(false);

    if update_available {
        egui::Frame::none()
            .fill(egui::Color32::from_rgb(40, 80, 40))
            .rounding(egui::Rounding::same(4.0))
            .inner_margin(8.0)
            .show(ui, |ui| {
                ui.colored_label(egui::Color32::from_rgb(100, 255, 100), "UPDATE AVAILABLE");
                if let Some(info) = app.update_info.lock().unwrap().as_ref() {
                    ui.colored_label(
                        egui::Color32::from_rgb(200, 255, 200),
                        format!("v{} -> v{}", info.current_version, info.latest_version),
                    );
                }
                if ui.small_button("View Update").clicked() {
                    app.current_page = Page::Updater;
                }
            });
        ui.add_space(5.0);
        ui.separator();
    }

    let navigation_buttons = [
        (Page::GettingStarted, "Getting Started"),
        (Page::ModManagers, "Mod Managers"),
        (Page::Settings, "Settings"),
        (Page::Updater, if update_available { "Version (NEW!)" } else { "Version" }),
    ];

    for (page, label) in navigation_buttons {
        let is_selected = app.current_page == page;

        // Highlight Version button if update available
        let button = if page == Page::Updater && update_available {
            egui::Button::new(egui::RichText::new(label).color(egui::Color32::from_rgb(100, 255, 100)))
                .min_size(egui::vec2(150.0, 30.0))
        } else {
            egui::Button::new(label).min_size(egui::vec2(150.0, 30.0))
        };

        if ui
            .add_enabled(!is_selected && is_enabled, button)
            .clicked()
        {
            app.current_page = page;
        }
        ui.add_space(5.0);
    }

    ui.with_layout(egui::Layout::bottom_up(egui::Align::Min), |ui| {
        ui.label(format!("v{}", env!("CARGO_PKG_VERSION")));
        ui.separator();
    });
}
