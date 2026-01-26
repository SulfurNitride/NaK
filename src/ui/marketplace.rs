//! Marketplace UI - Browse and install plugins

use eframe::egui;
use std::sync::atomic::Ordering;
use std::thread;

use crate::app::MyApp;
use crate::installers::{install_plugin, TaskContext};
use crate::logging::log_action;
use crate::marketplace::{
    fetch_registry, fetch_plugin_manifest, check_version_compatible,
    get_plugin_display_info, get_plugin_exe_name,
    Registry, PluginManifest,
};

/// Marketplace state stored in MyApp
#[derive(Default)]
pub struct MarketplaceState {
    /// Cached registry (fetched from GitHub)
    pub registry: Option<Registry>,
    /// Plugin manifests that have been fetched
    pub manifests: std::collections::HashMap<String, PluginManifest>,
    /// Loading state
    pub is_loading: bool,
    /// Error message
    pub error: Option<String>,
    /// Plugin being installed (id, name)
    pub installing_plugin: Option<(String, String)>,
    /// Install wizard state
    pub install_name: String,
    pub install_path: String,
    pub show_install_wizard: bool,
    /// Selected Proton for plugin installation
    pub selected_proton: Option<String>,
}

pub fn render_marketplace(app: &mut MyApp, ui: &mut egui::Ui) {
    ui.heading("Marketplace");
    ui.label("Browse and install additional plugins for NaK");
    ui.add_space(10.0);

    // Initialize marketplace state if needed
    if app.marketplace_state.is_none() {
        app.marketplace_state = Some(MarketplaceState::default());
    }

    // Check if install wizard is open
    let show_wizard = app.marketplace_state.as_ref().map(|s| s.show_install_wizard).unwrap_or(false);
    if show_wizard {
        render_install_wizard(app, ui);
        return;
    }

    // Get current state for reading
    let is_loading = app.marketplace_state.as_ref().map(|s| s.is_loading).unwrap_or(false);
    let error = app.marketplace_state.as_ref().and_then(|s| s.error.clone());
    let has_registry = app.marketplace_state.as_ref().map(|s| s.registry.is_some()).unwrap_or(false);

    // Refresh button
    let mut should_fetch = false;
    ui.horizontal(|ui| {
        if ui.add_enabled(!is_loading, egui::Button::new("Refresh")).clicked() {
            should_fetch = true;
        }
        if is_loading {
            ui.spinner();
            ui.label("Loading...");
        }
    });

    if should_fetch {
        fetch_registry_blocking(app);
    }

    ui.add_space(10.0);
    ui.separator();
    ui.add_space(10.0);

    // Show error if any
    if let Some(err) = error {
        ui.colored_label(egui::Color32::RED, format!("Error: {}", err));
        ui.add_space(10.0);
    }

    // Show registry or prompt to fetch
    if !has_registry && !is_loading {
        ui.vertical_centered(|ui| {
            ui.add_space(50.0);
            ui.label("Click 'Refresh' to load available plugins");
        });
    } else if has_registry {
        // Clone the registry for iteration
        let registry = app.marketplace_state.as_ref().unwrap().registry.clone().unwrap();
        render_plugin_list(app, ui, registry);
    }
}

fn render_plugin_list(app: &mut MyApp, ui: &mut egui::Ui, registry: Registry) {
    ui.label(format!("{} plugin(s) available:", registry.plugins.len()));
    ui.add_space(10.0);

    // Collect actions to perform after iteration
    let mut manifest_to_fetch: Option<(String, String)> = None;

    egui::ScrollArea::vertical().show(ui, |ui| {
        for entry in &registry.plugins {
            egui::Frame::none()
                .fill(egui::Color32::from_rgb(40, 40, 45))
                .rounding(egui::Rounding::same(8.0))
                .inner_margin(16.0)
                .outer_margin(egui::Margin::symmetric(0.0, 4.0))
                .show(ui, |ui| {
                    ui.horizontal(|ui| {
                        ui.vertical(|ui| {
                            ui.label(egui::RichText::new(&entry.name).size(18.0).strong());
                            ui.label(&entry.description);
                            ui.add_space(5.0);

                            // Show manifest details if loaded
                            let state = app.marketplace_state.as_ref().unwrap();
                            if let Some(manifest) = state.manifests.get(&entry.id) {
                                ui.horizontal(|ui| {
                                    ui.label(egui::RichText::new(format!("by {}", manifest.plugin.author)).size(12.0).color(egui::Color32::GRAY));
                                    ui.label(egui::RichText::new("|").color(egui::Color32::DARK_GRAY));
                                    ui.label(egui::RichText::new(format!("Requires NaK {}", manifest.plugin.min_nak_version)).size(12.0).color(egui::Color32::GRAY));
                                });

                                // Version compatibility check
                                if !check_version_compatible(&manifest.plugin.min_nak_version) {
                                    ui.colored_label(
                                        egui::Color32::from_rgb(255, 150, 100),
                                        format!("Requires NaK {} (you have {})", manifest.plugin.min_nak_version, env!("CARGO_PKG_VERSION"))
                                    );
                                }
                            }
                        });

                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                            let state = app.marketplace_state.as_ref().unwrap();
                            let has_manifest = state.manifests.contains_key(&entry.id);

                            if has_manifest {
                                let manifest = state.manifests.get(&entry.id).unwrap();
                                let compatible = check_version_compatible(&manifest.plugin.min_nak_version);

                                // Extract values before potentially mutating
                                let (name, _desc, _author) = get_plugin_display_info(manifest);
                                let exe_name = get_plugin_exe_name(manifest).to_string();
                                let entry_id = entry.id.clone();

                                if ui.add_enabled(compatible, egui::Button::new("Install")).clicked() {
                                    // Set up install wizard
                                    let state = app.marketplace_state.as_mut().unwrap();
                                    state.installing_plugin = Some((entry_id, name.clone()));
                                    state.install_name = name;
                                    state.install_path = format!(
                                        "{}/{}",
                                        std::env::var("HOME").unwrap_or_default(),
                                        exe_name.replace(".exe", "")
                                    );
                                    state.show_install_wizard = true;
                                }
                            } else if ui.button("Load Details").clicked() {
                                manifest_to_fetch = Some((entry.folder.clone(), entry.id.clone()));
                            }
                        });
                    });
                });
        }
    });

    // Perform deferred actions
    if let Some((folder, plugin_id)) = manifest_to_fetch {
        fetch_manifest_blocking(app, &folder, &plugin_id);
    }
}

fn fetch_registry_blocking(app: &mut MyApp) {
    let state = app.marketplace_state.as_mut().unwrap();
    state.is_loading = true;
    state.error = None;

    match fetch_registry() {
        Ok(registry) => {
            let state = app.marketplace_state.as_mut().unwrap();
            state.registry = Some(registry);
            state.is_loading = false;
        }
        Err(e) => {
            let state = app.marketplace_state.as_mut().unwrap();
            state.error = Some(e.to_string());
            state.is_loading = false;
        }
    }
}

fn fetch_manifest_blocking(app: &mut MyApp, folder: &str, plugin_id: &str) {
    match fetch_plugin_manifest(folder) {
        Ok(manifest) => {
            let state = app.marketplace_state.as_mut().unwrap();
            state.manifests.insert(plugin_id.to_string(), manifest);
        }
        Err(e) => {
            let state = app.marketplace_state.as_mut().unwrap();
            state.error = Some(format!("Failed to load plugin details: {}", e));
        }
    }
}

fn render_install_wizard(app: &mut MyApp, ui: &mut egui::Ui) {
    let is_installing = *app.is_installing_manager.lock().unwrap();
    let install_status = app.install_status.lock().unwrap().clone();

    // If installation is in progress, don't render anything here
    // The global progress bar at the top handles the display
    if is_installing {
        return;
    }

    // Check for installation completion
    if !install_status.is_empty() {
        if install_status.contains("Installed!") || install_status.contains("Complete!") {
            // Success - show completion message
            ui.vertical_centered(|ui| {
                ui.add_space(20.0);
                ui.label(egui::RichText::new("Installation Complete!").heading().color(egui::Color32::GREEN));
                ui.add_space(10.0);
                ui.label(&install_status);
                ui.add_space(20.0);
                ui.label("Restart Steam to see the new shortcut.");
                ui.add_space(20.0);
                if ui.button("Done").clicked() {
                    let state = app.marketplace_state.as_mut().unwrap();
                    state.show_install_wizard = false;
                    state.installing_plugin = None;
                    *app.install_status.lock().unwrap() = String::new();
                }
            });
            return;
        } else if install_status.starts_with("Error:") || install_status.contains("failed") {
            // Error - show error and allow retry
            ui.vertical_centered(|ui| {
                ui.add_space(20.0);
                ui.label(egui::RichText::new("Installation Failed").heading().color(egui::Color32::RED));
                ui.add_space(10.0);
                ui.colored_label(egui::Color32::RED, &install_status);
                ui.add_space(20.0);
                ui.horizontal(|ui| {
                    if ui.button("Back").clicked() {
                        *app.install_status.lock().unwrap() = String::new();
                    }
                    if ui.button("Close").clicked() {
                        let state = app.marketplace_state.as_mut().unwrap();
                        state.show_install_wizard = false;
                        state.installing_plugin = None;
                        *app.install_status.lock().unwrap() = String::new();
                    }
                });
            });
            return;
        }
    }

    let state = app.marketplace_state.as_ref().unwrap();
    let plugin_name = state.installing_plugin.as_ref().map(|(_, n)| n.clone()).unwrap_or_default();
    let plugin_id = state.installing_plugin.as_ref().map(|(id, _)| id.clone()).unwrap_or_default();

    ui.heading(format!("Install {}", plugin_name));
    ui.add_space(10.0);

    // Get manifest for this plugin
    let manifest = state.manifests.get(&plugin_id).cloned();

    if let Some(manifest) = manifest {
        // Show plugin info
        let (name, description, author) = get_plugin_display_info(&manifest);
        ui.label(format!("Name: {}", name));
        ui.label(format!("Description: {}", description));
        ui.label(format!("Author: {}", author));
        ui.label(format!("Executable: {}", get_plugin_exe_name(&manifest)));
        ui.add_space(10.0);
        ui.separator();
        ui.add_space(10.0);

        // Install name input
        ui.horizontal(|ui| {
            ui.label("Install Name:");
            let state = app.marketplace_state.as_mut().unwrap();
            ui.text_edit_singleline(&mut state.install_name);
        });

        // Install path input
        ui.horizontal(|ui| {
            ui.label("Install Path:");
            let state = app.marketplace_state.as_mut().unwrap();
            ui.text_edit_singleline(&mut state.install_path);
            if ui.button("Browse...").clicked() {
                if let Some(path) = rfd::FileDialog::new().pick_folder() {
                    state.install_path = path.display().to_string();
                }
            }
        });

        ui.add_space(10.0);

        // Proton selection
        ui.horizontal(|ui| {
            ui.label("Proton Version:");
            let state = app.marketplace_state.as_mut().unwrap();
            let current_selection = state.selected_proton.clone()
                .unwrap_or_else(|| app.steam_protons.first().map(|p| p.config_name.clone()).unwrap_or_default());

            egui::ComboBox::from_id_salt("plugin_proton_select")
                .selected_text(&current_selection)
                .show_ui(ui, |ui| {
                    for proton in &app.steam_protons {
                        if ui.selectable_value(
                            &mut state.selected_proton,
                            Some(proton.config_name.clone()),
                            &proton.name
                        ).clicked() {
                            // Selection handled by selectable_value
                        }
                    }
                });
        });

        ui.add_space(20.0);

        // Validation
        let state = app.marketplace_state.as_ref().unwrap();
        let install_name = state.install_name.clone();
        let install_path = state.install_path.clone();
        let selected_proton = state.selected_proton.clone();

        let name_valid = !install_name.trim().is_empty();
        let path_valid = !install_path.trim().is_empty();
        let proton_valid = selected_proton.is_some() || !app.steam_protons.is_empty();
        let can_install = name_valid && path_valid && proton_valid;

        // Buttons
        ui.horizontal(|ui| {
            if ui.button("Cancel").clicked() {
                let state = app.marketplace_state.as_mut().unwrap();
                state.show_install_wizard = false;
                state.installing_plugin = None;
            }

            ui.add_space(10.0);

            if ui.add_enabled(can_install, egui::Button::new("Install")).clicked() {
                start_plugin_installation(app, manifest.clone());
            }
        });

        if !can_install {
            ui.add_space(5.0);
            if !name_valid {
                ui.colored_label(egui::Color32::YELLOW, "Please enter an install name");
            }
            if !path_valid {
                ui.colored_label(egui::Color32::YELLOW, "Please select an install path");
            }
            if !proton_valid {
                ui.colored_label(egui::Color32::YELLOW, "No Proton versions found");
            }
        }
    } else {
        ui.colored_label(egui::Color32::RED, "Error: Plugin manifest not found");
        if ui.button("Back").clicked() {
            let state = app.marketplace_state.as_mut().unwrap();
            state.show_install_wizard = false;
            state.installing_plugin = None;
        }
    }
}

fn start_plugin_installation(app: &mut MyApp, manifest: PluginManifest) {
    let state = app.marketplace_state.as_ref().unwrap();
    let install_name = state.install_name.clone();
    let install_path = std::path::PathBuf::from(&state.install_path);
    let selected_proton_name = state.selected_proton.clone()
        .unwrap_or_else(|| app.steam_protons.first().map(|p| p.config_name.clone()).unwrap_or_default());

    log_action(&format!("Starting plugin installation: {} -> {:?}", install_name, install_path));

    // Find the selected Proton
    let proton = match app.steam_protons.iter().find(|p| p.config_name == selected_proton_name) {
        Some(p) => p.clone(),
        None => {
            let state = app.marketplace_state.as_mut().unwrap();
            state.error = Some("Selected Proton not found".to_string());
            return;
        }
    };

    // Setup shared state
    let status_arc = app.install_status.clone();
    let busy_arc = app.is_installing_manager.clone();
    let logs_arc = app.logs.clone();
    let progress_arc = app.install_progress.clone();
    let cancel_arc = app.cancel_install.clone();

    *busy_arc.lock().unwrap() = true;
    *status_arc.lock().unwrap() = format!("Preparing to install {}...", manifest.plugin.name);
    *progress_arc.lock().unwrap() = 0.0;
    cancel_arc.store(false, Ordering::Relaxed);

    thread::spawn(move || {
        let cb_status = status_arc.clone();
        let cb_logs = logs_arc.clone();
        let cb_prog = progress_arc.clone();

        // Ensure busy flag is cleared when thread exits
        struct BusyGuard(std::sync::Arc<std::sync::Mutex<bool>>);
        impl Drop for BusyGuard {
            fn drop(&mut self) {
                *self.0.lock().unwrap() = false;
            }
        }
        let _guard = BusyGuard(busy_arc);

        let ctx = TaskContext::new(
            {
                let s = cb_status.clone();
                move |msg| *s.lock().unwrap() = msg
            },
            {
                let l = cb_logs.clone();
                move |msg| l.lock().unwrap().push(msg)
            },
            {
                let p = cb_prog.clone();
                move |val| *p.lock().unwrap() = val
            },
            cancel_arc,
        );

        match install_plugin(
            &manifest,
            &install_name,
            install_path,
            &proton,
            ctx,
            false, // skip_disk_check
        ) {
            Ok(result) => {
                // Auto-restart Steam so the shortcut appears
                *cb_status.lock().unwrap() = "Restarting Steam...".to_string();
                match crate::steam::restart_steam() {
                    Ok(_) => {
                        *cb_status.lock().unwrap() = format!(
                            "{} Installed! AppID: {}. Steam has been restarted.",
                            manifest.plugin.name,
                            result.app_id
                        );
                    }
                    Err(e) => {
                        crate::logging::log_warning(&format!("Failed to restart Steam: {}", e));
                        *cb_status.lock().unwrap() = format!(
                            "{} Installed! AppID: {}. Please restart Steam manually.",
                            manifest.plugin.name,
                            result.app_id
                        );
                    }
                }
            }
            Err(e) => {
                *cb_status.lock().unwrap() = format!("Error: {}", e);
            }
        }
    });
}
