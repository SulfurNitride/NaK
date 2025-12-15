//! UI components and rendering

mod game_fixer;
mod mod_managers;
mod pages;
mod proton_tools;
mod sidebar;

pub use game_fixer::render_game_fixer;
pub use mod_managers::render_mod_managers;
pub use pages::{render_getting_started, render_marketplace, render_settings};
pub use proton_tools::render_proton_tools;
pub use sidebar::render_sidebar;

use eframe::egui;
use std::sync::atomic::Ordering;

use crate::app::MyApp;
use crate::logging::{log_action, log_error, log_info};
use crate::wine::{delete_cachyos_proton, delete_ge_proton};

// ============================================================================
// UI Extension Trait
// ============================================================================

pub trait UiExt {
    fn subheading(&mut self, text: &str);
}

impl UiExt for egui::Ui {
    fn subheading(&mut self, text: &str) {
        self.add_space(10.0);
        self.label(egui::RichText::new(text).size(16.0).strong());
        self.add_space(5.0);
    }
}

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
            self.refresh_proton_versions();
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

        egui::SidePanel::left("sidebar_panel")
            .resizable(false)
            .default_width(180.0)
            .show(ctx, |ui| {
                render_sidebar(self, ctx, ui, !is_busy);
            });

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
                crate::app::Page::ModManagers => {
                    render_mod_managers(self, ui);
                }
                crate::app::Page::GameFixer => {
                    render_game_fixer(self, ui);
                }
                _ => {
                    ui.add_enabled_ui(!is_busy, |ui| match self.current_page {
                        crate::app::Page::GettingStarted => render_getting_started(self, ui),
                        crate::app::Page::Marketplace => render_marketplace(self, ui),
                        crate::app::Page::ProtonTools => render_proton_tools(self, ui),
                        crate::app::Page::Settings => render_settings(self, ui),
                        _ => {}
                    });
                }
            }
        });
    }
}

/// Render confirmation dialogs for destructive actions
fn render_confirmation_dialogs(app: &mut MyApp, ctx: &egui::Context) {
    // Prefix deletion confirmation
    if let Some(prefix_name) = app.pending_prefix_delete.clone() {
        egui::Window::new("Confirm Delete")
            .collapsible(false)
            .resizable(false)
            .anchor(egui::Align2::CENTER_CENTER, [0.0, 0.0])
            .show(ctx, |ui| {
                ui.vertical_centered(|ui| {
                    ui.add_space(10.0);
                    ui.label(egui::RichText::new("⚠ Delete Prefix?").size(18.0).strong());
                    ui.add_space(10.0);
                    ui.label(format!("Are you sure you want to delete '{}'?", prefix_name));
                    ui.label(egui::RichText::new("This will permanently remove all data in this prefix.")
                        .color(egui::Color32::from_rgb(255, 150, 150)));
                    ui.add_space(15.0);

                    ui.horizontal(|ui| {
                        if ui.button("Cancel").clicked() {
                            app.pending_prefix_delete = None;
                        }
                        ui.add_space(20.0);
                        if ui.button(egui::RichText::new("Delete").color(egui::Color32::RED)).clicked() {
                            log_action(&format!("Confirmed delete prefix: {}", prefix_name));
                            if let Err(e) = app.prefix_manager.delete_prefix(&prefix_name) {
                                log_error(&format!("Failed to delete prefix '{}': {}", prefix_name, e));
                            } else {
                                log_info(&format!("Prefix '{}' deleted successfully", prefix_name));
                                app.detected_prefixes = app.prefix_manager.scan_prefixes();
                            }
                            app.pending_prefix_delete = None;
                        }
                    });
                    ui.add_space(10.0);
                });
            });
    }

    // Proton deletion confirmation
    if let Some((proton_name, proton_type)) = app.pending_proton_delete.clone() {
        egui::Window::new("Confirm Uninstall")
            .collapsible(false)
            .resizable(false)
            .anchor(egui::Align2::CENTER_CENTER, [0.0, 0.0])
            .show(ctx, |ui| {
                ui.vertical_centered(|ui| {
                    ui.add_space(10.0);
                    ui.label(egui::RichText::new("⚠ Uninstall Proton?").size(18.0).strong());
                    ui.add_space(10.0);
                    ui.label(format!("Are you sure you want to uninstall '{}'?", proton_name));
                    ui.add_space(15.0);

                    ui.horizontal(|ui| {
                        if ui.button("Cancel").clicked() {
                            app.pending_proton_delete = None;
                        }
                        ui.add_space(20.0);
                        if ui.button(egui::RichText::new("Uninstall").color(egui::Color32::RED)).clicked() {
                            log_action(&format!("Confirmed uninstall proton: {} ({})", proton_name, proton_type));
                            let result = if proton_type == "ge" {
                                delete_ge_proton(&proton_name)
                            } else {
                                delete_cachyos_proton(&proton_name)
                            };
                            if let Err(e) = result {
                                log_error(&format!("Failed to uninstall '{}': {}", proton_name, e));
                            } else {
                                log_info(&format!("Proton '{}' uninstalled successfully", proton_name));
                                app.should_refresh_proton = true;
                            }
                            app.pending_proton_delete = None;
                        }
                    });
                    ui.add_space(10.0);
                });
            });
    }
}
