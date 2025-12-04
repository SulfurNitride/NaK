//! Mod Managers page UI

use eframe::egui;
use std::thread;
use std::sync::atomic::Ordering;

use crate::app::{MyApp, ModManagerInstance};
use crate::installers::{install_mo2, install_vortex};
use crate::nxm::NxmHandler;
use crate::logging::log_action;

pub fn render_mod_managers(app: &mut MyApp, ui: &mut egui::Ui) {
    ui.heading("Mod Managers & Prefixes");
    ui.separator();
    ui.add_space(10.0);

    egui::ScrollArea::vertical().show(ui, |ui| {

        // --- Section 1: Prefix Manager ---
        egui::CollapsingHeader::new("Prefix Manager")
            .show(ui, |ui| {
            ui.label("Manage your Wine prefixes directly.");
            ui.add_space(5.0);
            ui.horizontal(|ui| {
                if ui.button("🔍 Scan for New Prefixes").clicked() {
                    app.detected_prefixes = app.prefix_manager.scan_prefixes();
                }
            });

            ui.add_space(5.0);

            // Prefix Grid
            let mut prefix_to_delete = None;

            egui::Grid::new("prefix_grid").striped(true).min_col_width(100.0).show(ui, |ui| {
                ui.strong("Name");
                ui.strong("Path");
                ui.strong("Actions");
                ui.end_row();

                if app.detected_prefixes.is_empty() {
                     ui.label("No NaK prefixes found");
                     ui.label("-");
                     ui.label("-");
                     ui.end_row();
                }

                for prefix in &app.detected_prefixes {
                    ui.horizontal(|ui| {
                        ui.label(&prefix.name);
                        if prefix.is_orphaned {
                            ui.colored_label(egui::Color32::RED, "⚠ Orphaned");
                        }
                    });

                    ui.label(prefix.path.to_string_lossy());
                    ui.horizontal(|ui| {
                        if ui.button("🗑").on_hover_text("Delete Prefix").clicked() {
                            prefix_to_delete = Some(prefix.name.clone());
                        }

                        let winetricks_ready = app.winetricks_path.lock().unwrap().is_some();
                        if ui.add_enabled(winetricks_ready, egui::Button::new("🍷 Winetricks")).clicked() {
                            let path = prefix.path.clone();
                            let wt_path = app.winetricks_path.lock().unwrap().clone().unwrap();

                            // Find active proton
                            let mut wine_bin = None;
                            let mut wineserver_bin = None;
                            let mut wine_path_env = None;

                            if let Some(selected_name) = &app.config.selected_proton {
                                if let Some(proton) = app.proton_versions.iter().find(|p| &p.name == selected_name) {
                                    let bin_dir = proton.path.join("files").join("bin");
                                    let wine_exec = bin_dir.join("wine");
                                    let server_exec = bin_dir.join("wineserver");

                                    if wine_exec.exists() {
                                        wine_bin = Some(wine_exec);
                                        wineserver_bin = Some(server_exec);
                                        if let Ok(current_path) = std::env::var("PATH") {
                                            wine_path_env = Some(format!("{}:{}", bin_dir.to_string_lossy(), current_path));
                                        }
                                    }
                                }
                            }

                            thread::spawn(move || {
                                println!("Launching winetricks for prefix: {:?}", path);
                                let mut cmd = std::process::Command::new(wt_path);
                                cmd.arg("--gui")
                                   .env("WINEPREFIX", path);

                                if let Some(w) = wine_bin {
                                    println!("Using Wine: {:?}", w);
                                    cmd.env("WINE", w);
                                }
                                if let Some(ws) = wineserver_bin {
                                    cmd.env("WINESERVER", ws);
                                }
                                if let Some(p) = wine_path_env {
                                    cmd.env("PATH", p);
                                }

                                let result = cmd.spawn();

                                match result {
                                    Ok(_) => println!("Winetricks launched successfully"),
                                    Err(e) => eprintln!("Failed to launch winetricks: {}", e),
                                }
                            });
                        }
                        if ui.button("📂 Open").clicked() {
                            let _ = std::process::Command::new("xdg-open")
                                .arg(&prefix.path)
                                .spawn();
                        }

                        // NXM Handler Toggle
                        let prefix_base = prefix.path.parent().unwrap();
                        let manager_link = prefix_base.join("manager_link");
                        let is_linked = manager_link.exists() || std::fs::symlink_metadata(&manager_link).is_ok();

                        let path_str = prefix.path.to_string_lossy().to_string();
                        let is_active = app.config.active_nxm_prefix.as_ref() == Some(&path_str);

                        if is_active {
                            ui.colored_label(egui::Color32::GREEN, "✅ Active NXM");
                        } else {
                            if ui.add_enabled(is_linked, egui::Button::new("🔗 Activate NXM")).on_disabled_hover_text("Not a NaK-managed MO2/Vortex prefix").clicked() {
                                if let Ok(target) = std::fs::read_link(&manager_link) {
                                    if let Err(e) = NxmHandler::set_active_instance(&target) {
                                        eprintln!("Failed to set active instance: {}", e);
                                    } else {
                                        app.config.active_nxm_prefix = Some(path_str);
                                        app.config.save();
                                    }
                                }
                            }
                        }
                    });
                    ui.end_row();
                }
            });

            if let Some(name) = prefix_to_delete {
                if let Err(e) = app.prefix_manager.delete_prefix(&name) {
                    eprintln!("Failed to delete prefix: {}", e);
                } else {
                    app.detected_prefixes = app.prefix_manager.scan_prefixes();
                }
            }
        });
        ui.add_space(10.0);
        ui.separator();
        ui.add_space(10.0);

        // --- Section 2: MO2 Manager ---
        render_mo2_section(app, ui);

        ui.add_space(10.0);
        ui.separator();
        ui.add_space(10.0);

        // --- Section 3: Vortex Manager ---
        render_vortex_section(app, ui);

    }); // End ScrollArea

    ui.add_space(20.0);
    ui.separator();

    // --- Terminal / Logs ---
    egui::CollapsingHeader::new("📜 Terminal / Logs")
        .default_open(true)
        .show(ui, |ui| {
        let logs = app.logs.lock().unwrap();
        let start_idx = logs.len().saturating_sub(100);
        egui::ScrollArea::vertical().max_height(300.0).stick_to_bottom(true).show(ui, |ui| {
            for line in &logs[start_idx..] {
                ui.monospace(line);
            }
        });
    });
}

fn render_mo2_section(app: &mut MyApp, ui: &mut egui::Ui) {
    egui::CollapsingHeader::new("Mod Organizer 2 Manager")
        .show(ui, |ui| {
            ui.label("Manage your Mod Organizer 2 installations.");
            ui.add_space(5.0);

            let is_busy = *app.is_installing_manager.lock().unwrap();

            ui.add_enabled_ui(!is_busy, |ui| {
                ui.horizontal(|ui| {
                    ui.label("Instance Name:");
                    ui.text_edit_singleline(&mut app.install_name_input);
                });

                ui.horizontal(|ui| {
                    ui.label("Install Path:");
                    ui.text_edit_singleline(&mut app.install_path_input);

                    if ui.button("📂").clicked() {
                        if let Some(path) = rfd::FileDialog::new().pick_folder() {
                            app.install_path_input = path.to_string_lossy().to_string();
                        }
                    }
                });
            });

            ui.horizontal(|ui| {
                let winetricks_ready = app.winetricks_path.lock().unwrap().is_some();
                let proton_selected = app.config.selected_proton.is_some();
                let is_busy = *app.is_installing_manager.lock().unwrap();
                let name_valid = !app.install_name_input.trim().is_empty();
                let path_valid = !app.install_path_input.trim().is_empty();
                let can_install = winetricks_ready && proton_selected && !is_busy && name_valid && path_valid;

                if ui.add_enabled(can_install, egui::Button::new("⬇ Install New MO2"))
                    .on_disabled_hover_text(if !name_valid { "Enter an instance name" } else if !path_valid { "Select an install path" } else if !proton_selected { "Select a Proton version" } else { "Waiting for dependencies..." })
                    .clicked() {
                    log_action(&format!("Install MO2 clicked - Name: {}, Path: {}", app.install_name_input, app.install_path_input));
                    // Setup Variables
                    let status_arc = app.install_status.clone();
                    let busy_arc = app.is_installing_manager.clone();
                    let logs_arc = app.logs.clone();
                    let progress_arc = app.install_progress.clone();
                    let cancel_arc = app.cancel_install.clone();
                    let wt_path = app.winetricks_path.lock().unwrap().clone().unwrap();

                    let selected_name = app.config.selected_proton.as_ref().unwrap().clone();
                    let proton = app.proton_versions.iter().find(|p| p.name == selected_name).cloned();
                    let instance_name = app.install_name_input.clone();
                    let install_path = std::path::PathBuf::from(&app.install_path_input);

                    if let Some(proton_info) = proton {
                        *busy_arc.lock().unwrap() = true;
                        *status_arc.lock().unwrap() = "Starting MO2 Installation...".to_string();
                        *progress_arc.lock().unwrap() = 0.0;
                        cancel_arc.store(false, Ordering::Relaxed);

                        thread::spawn(move || {
                            let cb_status = status_arc.clone();
                            let cb_logs = logs_arc.clone();
                            let cb_prog = progress_arc.clone();

                            let status_callback = move |msg: String| {
                                *cb_status.lock().unwrap() = msg;
                            };

                            let log_callback = move |msg: String| {
                                cb_logs.lock().unwrap().push(msg);
                            };

                            let prog_callback = move |p: f32| {
                                *cb_prog.lock().unwrap() = p;
                            };

                            if let Err(e) = install_mo2(&instance_name, install_path, &proton_info, wt_path, status_callback, log_callback, prog_callback, cancel_arc) {
                                *status_arc.lock().unwrap() = format!("Error: {}", e);
                            }
                            *busy_arc.lock().unwrap() = false;
                        });
                    } else {
                        *status_arc.lock().unwrap() = "Selected Proton version not found!".to_string();
                    }
                }

                if ui.add_enabled(!is_busy, egui::Button::new("📂 Setup Existing MO2")).clicked() { }
            });
            ui.add_space(10.0);

            // Filter for MO2 instances
            for instance in &app.installed_instances {
                if instance.manager_type == "MO2" {
                     render_instance_card(ui, instance);
                }
            }
        });
}

fn render_vortex_section(app: &mut MyApp, ui: &mut egui::Ui) {
    egui::CollapsingHeader::new("Vortex Manager")
        .show(ui, |ui| {
            ui.label("Manage your Vortex installations.");
             ui.add_space(5.0);

            let is_busy = *app.is_installing_manager.lock().unwrap();

            ui.add_enabled_ui(!is_busy, |ui| {
                ui.horizontal(|ui| {
                    ui.label("Instance Name:");
                    ui.text_edit_singleline(&mut app.vortex_install_name);
                });

                ui.horizontal(|ui| {
                    ui.label("Install Path:");
                    ui.text_edit_singleline(&mut app.vortex_install_path);

                    if ui.button("📂").clicked() {
                        if let Some(path) = rfd::FileDialog::new().pick_folder() {
                            app.vortex_install_path = path.to_string_lossy().to_string();
                        }
                    }
                });
            });

            ui.horizontal(|ui| {
                let winetricks_ready = app.winetricks_path.lock().unwrap().is_some();
                let proton_selected = app.config.selected_proton.is_some();
                let is_busy = *app.is_installing_manager.lock().unwrap();
                let name_valid = !app.vortex_install_name.trim().is_empty();
                let path_valid = !app.vortex_install_path.trim().is_empty();
                let can_install = winetricks_ready && proton_selected && !is_busy && name_valid && path_valid;

                if ui.add_enabled(can_install, egui::Button::new("⬇ Install New Vortex"))
                    .on_disabled_hover_text(if !name_valid { "Enter an instance name" } else if !path_valid { "Select an install path" } else if !proton_selected { "Select a Proton version" } else { "Waiting for dependencies..." })
                    .clicked() {
                    log_action(&format!("Install Vortex clicked - Name: {}, Path: {}", app.vortex_install_name, app.vortex_install_path));
                    // Setup Variables
                    let status_arc = app.install_status.clone();
                    let busy_arc = app.is_installing_manager.clone();
                    let logs_arc = app.logs.clone();
                    let progress_arc = app.install_progress.clone();
                    let cancel_arc = app.cancel_install.clone();
                    let wt_path = app.winetricks_path.lock().unwrap().clone().unwrap();

                    let selected_name = app.config.selected_proton.as_ref().unwrap().clone();
                    let proton = app.proton_versions.iter().find(|p| p.name == selected_name).cloned();
                    let instance_name = app.vortex_install_name.clone();
                    let install_path = std::path::PathBuf::from(&app.vortex_install_path);

                    if let Some(proton_info) = proton {
                        *busy_arc.lock().unwrap() = true;
                        *status_arc.lock().unwrap() = "Starting Vortex Installation...".to_string();
                        *progress_arc.lock().unwrap() = 0.0;
                        cancel_arc.store(false, Ordering::Relaxed);

                        thread::spawn(move || {
                            let cb_status = status_arc.clone();
                            let cb_logs = logs_arc.clone();
                            let cb_prog = progress_arc.clone();

                            // Ensure busy flag is reset even on panic
                            struct BusyGuard(std::sync::Arc<std::sync::Mutex<bool>>);
                            impl Drop for BusyGuard {
                                fn drop(&mut self) {
                                    *self.0.lock().unwrap() = false;
                                }
                            }
                            let _guard = BusyGuard(busy_arc.clone());

                            let status_callback = move |msg: String| {
                                *cb_status.lock().unwrap() = msg;
                            };

                            let log_callback = move |msg: String| {
                                cb_logs.lock().unwrap().push(msg);
                            };

                            let prog_callback = move |p: f32| {
                                *cb_prog.lock().unwrap() = p;
                            };

                            if let Err(e) = install_vortex(&instance_name, install_path, &proton_info, wt_path, status_callback, log_callback, prog_callback, cancel_arc) {
                                *status_arc.lock().unwrap() = format!("Error: {}", e);
                            }
                        });
                    } else {
                        *status_arc.lock().unwrap() = "Selected Proton version not found!".to_string();
                    }
                }

                if ui.button("📂 Setup Existing Vortex").clicked() { }
            });
            ui.add_space(10.0);

            // Filter for Vortex instances
            for instance in &app.installed_instances {
                if instance.manager_type == "Vortex" {
                     render_instance_card(ui, instance);
                }
            }
        });
}

fn render_instance_card(ui: &mut egui::Ui, instance: &ModManagerInstance) {
    egui::Frame::group(ui.style())
        .rounding(egui::Rounding::same(6.0))
        .fill(egui::Color32::from_gray(32))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_gray(60)))
        .inner_margin(10.0)
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                // Icon label
                let icon_text = if instance.manager_type == "MO2" { "MO2" } else { "VTX" };
                ui.add(egui::Label::new(egui::RichText::new(icon_text)
                    .size(20.0)
                    .strong()
                    .color(egui::Color32::from_rgb(100, 149, 237))));
                ui.add_space(10.0);

                // Info
                ui.vertical(|ui| {
                    ui.heading(&instance.name);
                    ui.label(format!("Game: {}", instance.game));
                    ui.label(egui::RichText::new(&instance.status).color(egui::Color32::GREEN));
                });

                // Actions
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    if ui.button("🚀 Launch").clicked() {
                        println!("Launching {}", instance.name);
                    }
                    if ui.button("⚙ Config").clicked() { }
                    if ui.button("🗑").clicked() { }
                });
            });
        });
    ui.add_space(8.0);
}
