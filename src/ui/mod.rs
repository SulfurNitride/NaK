//! UI components and rendering

mod sidebar;
mod mod_managers;
mod proton_tools;
mod pages;

pub use sidebar::render_sidebar;
pub use mod_managers::render_mod_managers;
pub use proton_tools::render_proton_tools;
pub use pages::{render_getting_started, render_marketplace, render_settings};

use eframe::egui;
use std::sync::atomic::Ordering;

use crate::app::MyApp;

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
        // Check for background download completion
        {
            let mut status = self.download_status.lock().unwrap();
            if status.contains("REFRESH") {
                // Clear the signal
                *status = status.replace(" REFRESH", "");
                self.should_refresh_proton = true;
            }
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
                },
                _ => {
                    ui.add_enabled_ui(!is_busy, |ui| {
                        match self.current_page {
                            crate::app::Page::GettingStarted => render_getting_started(self, ui),
                            crate::app::Page::Marketplace => render_marketplace(self, ui),
                            crate::app::Page::ProtonTools => render_proton_tools(self, ui),
                            crate::app::Page::Settings => render_settings(self, ui),
                            _ => {}
                        }
                    });
                }
            }
        });
    }
}
