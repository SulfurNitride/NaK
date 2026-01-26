//! UI components and rendering

mod marketplace;
mod mod_managers;
mod pages;
mod sidebar;

pub use marketplace::{render_marketplace, MarketplaceState};
pub use mod_managers::render_mod_managers;
pub use pages::{render_first_run_setup, render_getting_started, render_settings, render_updater};
pub use sidebar::render_sidebar;

use eframe::egui;
use std::sync::atomic::Ordering;

use crate::app::MyApp;
use crate::logging::{log_error, log_info};

// ============================================================================
// eframe::App Implementation
// ============================================================================

impl eframe::App for MyApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // Check for background download completion (using atomic flag)
        if self.download_needs_refresh.swap(false, Ordering::Relaxed) {
            self.should_refresh_proton = true;
        }

        if self.should_refresh_proton {
            self.refresh_steam_protons();
            self.should_refresh_proton = false;
        }

        // Global Style Tweaks
        let mut style = (*ctx.style()).clone();
        style.visuals.widgets.active.rounding = egui::Rounding::same(4.0);
        style.visuals.widgets.inactive.rounding = egui::Rounding::same(4.0);
        style.visuals.widgets.open.rounding = egui::Rounding::same(4.0);
        ctx.set_style(style);

        let is_busy = *self.is_installing_manager.lock().unwrap();

        // Render confirmation dialogs
        render_confirmation_dialogs(self, ctx);

        // Hide sidebar during first-run setup
        if self.current_page != crate::app::Page::FirstRunSetup {
            egui::SidePanel::left("sidebar_panel")
                .resizable(false)
                .default_width(180.0)
                .show(ctx, |ui| {
                    render_sidebar(self, ctx, ui, !is_busy);
                });
        }

        egui::CentralPanel::default().show(ctx, |ui| {
            // If busy, show overlay/status at top
            if is_busy {
                ui.vertical_centered(|ui| {
                    ui.add_space(10.0);
                    ui.heading("Installation in Progress...");

                    let status = self.install_status.lock().unwrap().clone();
                    ui.label(&status);

                    let p = *self.install_progress.lock().unwrap();
                    ui.add(egui::ProgressBar::new(p).animate(true));

                    if ui.button("Cancel").clicked() {
                        self.cancel_install.store(true, Ordering::Relaxed);
                        *self.install_status.lock().unwrap() = "Cancelling...".to_string();
                    }
                    ui.add_space(10.0);
                    ui.separator();
                });
            }

            match self.current_page {
                crate::app::Page::FirstRunSetup => {
                    render_first_run_setup(self, ui);
                }
                crate::app::Page::ModManagers => {
                    render_mod_managers(self, ui);
                }
                _ => {
                    ui.add_enabled_ui(!is_busy, |ui| match self.current_page {
                        crate::app::Page::GettingStarted => render_getting_started(self, ui),
                        crate::app::Page::Marketplace => render_marketplace(self, ui),
                        crate::app::Page::Settings => render_settings(self, ui),
                        crate::app::Page::Updater => render_updater(self, ui),
                        _ => {}
                    });
                }
            }
        });
    }
}

/// Render confirmation dialogs for destructive actions
fn render_confirmation_dialogs(app: &mut MyApp, ctx: &egui::Context) {
    // Steam-native migration notice (shown once for users with legacy data)
    if app.show_steam_migration_popup {
        egui::Window::new("NaK Has Changed")
            .collapsible(false)
            .resizable(false)
            .default_width(500.0)
            .anchor(egui::Align2::CENTER_CENTER, [0.0, 0.0])
            .show(ctx, |ui| {
                ui.vertical_centered(|ui| {
                    ui.add_space(10.0);
                    ui.label(egui::RichText::new("NaK Now Uses Steam Integration").size(20.0).strong());
                    ui.add_space(15.0);
                });

                ui.label("NaK has moved to Steam-native integration. MO2 is now added as a non-Steam game and runs through Steam's Proton.");
                ui.add_space(10.0);

                egui::Frame::none()
                    .fill(egui::Color32::from_rgb(50, 40, 30))
                    .rounding(egui::Rounding::same(6.0))
                    .inner_margin(12.0)
                    .show(ui, |ui| {
                        ui.label(egui::RichText::new("What This Means:").strong());
                        ui.add_space(5.0);
                        ui.label("- Old NaK prefixes and Protons are no longer used");
                        ui.label("- New installations create Steam shortcuts");
                        ui.label("- Proton versions are managed through Steam");
                    });

                ui.add_space(15.0);

                let legacy_path = app.config.get_data_path();
                egui::Frame::none()
                    .fill(egui::Color32::from_rgb(60, 50, 40))
                    .rounding(egui::Rounding::same(6.0))
                    .inner_margin(12.0)
                    .show(ui, |ui| {
                        ui.label(egui::RichText::new("Recommended: Delete Old NaK Data").strong().color(egui::Color32::from_rgb(255, 200, 100)));
                        ui.add_space(5.0);
                        ui.label(format!("Your old NaK folder at {} contains data from the previous version.", legacy_path.display()));
                        ui.label("You can safely delete it to start fresh with the new system.");
                        ui.add_space(5.0);
                        ui.label(egui::RichText::new("Or keep it if you want to use an older NaK version.")
                            .size(11.0)
                            .color(egui::Color32::GRAY));
                    });

                ui.add_space(15.0);

                ui.horizontal(|ui| {
                    let nak_folder = app.config.get_data_path();

                    if ui.button("Open NaK Folder").clicked() {
                        let _ = std::process::Command::new("xdg-open")
                            .arg(&nak_folder)
                            .spawn();
                    }

                    ui.add_space(10.0);

                    if ui.button(egui::RichText::new("Delete Old Data").color(egui::Color32::from_rgb(255, 150, 150))).clicked() {
                        // Delete the old NaK data folder entirely
                        if let Err(e) = std::fs::remove_dir_all(&nak_folder) {
                            log_error(&format!("Failed to delete {}: {}", nak_folder.display(), e));
                        } else {
                            log_info(&format!("Deleted old NaK folder: {}", nak_folder.display()));
                        }
                        app.show_steam_migration_popup = false;
                        app.config.steam_migration_shown = true;
                        app.config.save();
                    }

                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        if ui.button("Got It, Keep Data").clicked() {
                            app.show_steam_migration_popup = false;
                            app.config.steam_migration_shown = true;
                            app.config.save();
                        }
                    });
                });

                ui.add_space(10.0);
            });
    }
}
