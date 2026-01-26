//! Simple pages: Getting Started, Marketplace, Settings, First Run Setup

use crate::app::{MyApp, Page};
use crate::config::{AppConfig, ManagedPrefixes};
use crate::logging::log_action;
use crate::steam::ShortcutsVdf;
use eframe::egui;
use std::collections::HashSet;

/// First-run setup page - shown on first launch
/// Now simplified since Steam handles Proton/runtime natively
pub fn render_first_run_setup(app: &mut MyApp, ui: &mut egui::Ui) {
    egui::ScrollArea::vertical().show(ui, |ui| {
        ui.vertical_centered(|ui| {
            ui.add_space(40.0);

            ui.heading(egui::RichText::new("Welcome to NaK!").size(32.0).strong());
            ui.add_space(8.0);
            ui.label(
                egui::RichText::new("Linux Modding Helper")
                    .size(18.0)
                    .color(egui::Color32::GRAY),
            );

            ui.add_space(30.0);

            let max_width = ui.available_width().min(550.0);

            // Info box
            egui::Frame::none()
                .fill(egui::Color32::from_rgb(35, 35, 45))
                .rounding(egui::Rounding::same(8.0))
                .inner_margin(20.0)
                .show(ui, |ui| {
                    ui.set_max_width(max_width);

                    ui.label(egui::RichText::new("What NaK Does").strong().size(16.0));
                    ui.add_space(12.0);

                    ui.label("NaK helps you install and run mod managers (MO2, Vortex) on Linux:");
                    ui.add_space(8.0);
                    ui.label("  - Creates Steam shortcuts for your mod managers");
                    ui.label("  - Installs required Windows dependencies (VC++, DirectX, etc.)");
                    ui.label("  - Sets up game registry entries for mod detection");
                    ui.label("  - Handles NXM links from Nexus Mods");
                });

            ui.add_space(20.0);

            // Steam integration note
            egui::Frame::none()
                .fill(egui::Color32::from_rgb(30, 50, 40))
                .rounding(egui::Rounding::same(8.0))
                .inner_margin(15.0)
                .show(ui, |ui| {
                    ui.set_max_width(max_width);
                    ui.colored_label(
                        egui::Color32::from_rgb(100, 200, 100),
                        "Steam Integration",
                    );
                    ui.add_space(5.0);
                    ui.label("NaK adds your mod managers as non-Steam games. This means:");
                    ui.label("  - Proton versions are managed through Steam");
                    ui.label("  - Launch mod managers directly from Steam");
                    ui.label("  - Steam overlay and controller support work");
                });

            ui.add_space(30.0);

            // Get Started button
            if ui.add_sized(
                [200.0, 45.0],
                egui::Button::new(egui::RichText::new("Get Started").size(16.0))
            ).clicked() {
                log_action("First-run setup completed");
                app.config.first_run_completed = true;
                app.config.save();
                app.current_page = Page::GettingStarted;
            }

            ui.add_space(20.0);

            ui.label(
                egui::RichText::new("Click above to begin setting up your mod manager")
                    .size(12.0)
                    .color(egui::Color32::GRAY),
            );

            ui.add_space(30.0);
        });
    });
}

pub fn render_getting_started(app: &mut MyApp, ui: &mut egui::Ui) {
    egui::ScrollArea::vertical().show(ui, |ui| {
        // ============================================================
        // Header
        // ============================================================
        ui.heading(egui::RichText::new("Welcome to NaK!").size(24.0).strong());
        ui.label(
            egui::RichText::new("Linux Modding Helper")
                .size(14.0)
                .color(egui::Color32::GRAY),
        );

        ui.separator();
        ui.add_space(10.0);

        ui.label("NaK makes it easy to run Windows modding tools on Linux using Proton.");

        ui.add_space(15.0);

        // ============================================================
        // Install a Mod Manager
        // ============================================================
        ui.label(
            egui::RichText::new("Install a Mod Manager")
                .size(16.0)
                .strong(),
        );
        ui.label(
            egui::RichText::new("Choose MO2 or Vortex - NaK handles all the setup automatically")
                .size(12.0)
                .color(egui::Color32::LIGHT_GRAY),
        );
        ui.add_space(10.0);

        ui.horizontal(|ui| {
            if ui.button("Go to Mod Managers").clicked() {
                log_action("Navigate to Mod Managers from Getting Started");
                app.current_page = Page::ModManagers;
            }
        });
        ui.add_space(10.0);
        ui.label("NaK will:");
        ui.label("  - Create a Steam shortcut for your mod manager");
        ui.label("  - Configure your selected Proton version automatically");
        ui.label("  - Install required Windows dependencies");

        ui.add_space(20.0);
        ui.separator();
        ui.add_space(10.0);

        // ============================================================
        // FAQ & Help
        // ============================================================
        ui.label(
            egui::RichText::new("Need Help?")
                .size(16.0)
                .strong(),
        );
        ui.add_space(5.0);
        if ui.button("View FAQ & Known Issues").clicked() {
            log_action("Open FAQ in browser");
            let _ = std::process::Command::new("xdg-open")
                .arg("https://github.com/SulfurNitride/NaK/blob/main/docs/FAQ.md")
                .spawn();
        }

        ui.add_space(15.0);

        // Support links
        ui.horizontal(|ui| {
            ui.label("Community:");
            if ui.link("GitHub Issues").clicked() {
                let _ = std::process::Command::new("xdg-open")
                    .arg("https://github.com/SulfurNitride/NaK/issues")
                    .spawn();
            }
            ui.label("|");
            if ui.link("Discord").clicked() {
                let _ = std::process::Command::new("xdg-open")
                    .arg("https://discord.gg/9JWQzSeUWt")
                    .spawn();
            }
            ui.label("|");
            if ui.link("Ko-Fi (Donate)").clicked() {
                let _ = std::process::Command::new("xdg-open")
                    .arg("https://ko-fi.com/sulfurnitride")
                    .spawn();
            }
        });
    });
}

pub fn render_settings(app: &mut MyApp, ui: &mut egui::Ui) {
    ui.heading("Settings");
    ui.separator();

    egui::ScrollArea::vertical().show(ui, |ui| {
        // ============================================================
        // Pre-Cache Downloads Section
        // ============================================================
        egui::CollapsingHeader::new("Pre-Cache Downloads")
            .default_open(true)
            .show(ui, |ui| {
                ui.add_space(5.0);

                // --- Dependency Pre-Cache ---
                ui.label(egui::RichText::new("Pre-Cache Downloads").strong());
                ui.label(
                    egui::RichText::new("Download MO2, Vortex, and dependencies for offline installation")
                        .size(11.0)
                        .color(egui::Color32::GRAY),
                );
                ui.add_space(5.0);

                let cache_status = crate::deps::precache::get_cache_status();
                let is_precaching = *app.is_precaching.lock().unwrap();

                // Show dependency cache status (quick check, no network)
                ui.horizontal(|ui| {
                    ui.label("Dependencies:");
                    if cache_status.is_complete() {
                        ui.colored_label(
                            egui::Color32::from_rgb(100, 200, 100),
                            format!("{} files cached (~{}MB)", cache_status.total_files(), cache_status.total_cached_mb),
                        );
                    } else {
                        ui.colored_label(
                            egui::Color32::from_rgb(255, 200, 100),
                            format!(
                                "{}/{} files (~{}MB remaining)",
                                cache_status.cached_count(),
                                cache_status.total_files(),
                                cache_status.total_missing_mb
                            ),
                        );
                    }
                });

                ui.add_space(5.0);

                // Pre-cache button or progress
                if is_precaching {
                    let progress = *app.precache_progress.lock().unwrap();
                    let status = app.precache_status.lock().unwrap().clone();

                    ui.add(egui::ProgressBar::new(progress).text(&status));
                    ui.add_space(5.0);

                    if ui.button("Cancel").clicked() {
                        app.cancel_install.store(true, std::sync::atomic::Ordering::Relaxed);
                    }
                } else {
                    ui.horizontal(|ui| {
                        // Button is always enabled - it will check for MO2/Vortex updates
                        if ui.button("Pre-Cache All").clicked() {
                            log_action("Pre-cache all clicked");
                            app.cancel_install.store(false, std::sync::atomic::Ordering::Relaxed);
                            app.start_precache();
                        }

                        if cache_status.cached_count() > 0
                            && ui.button("Clear Cache").clicked()
                        {
                            if let Err(e) = crate::deps::precache::clear_cache() {
                                eprintln!("Failed to clear dependency cache: {}", e);
                            }
                        }
                    });

                    // Show result message if any
                    if let Some(result) = app.precache_result.lock().unwrap().as_ref() {
                        ui.add_space(5.0);
                        match result {
                            Ok(count) => {
                                if *count > 0 {
                                    ui.colored_label(
                                        egui::Color32::from_rgb(100, 200, 100),
                                        format!("Downloaded {} files!", count),
                                    );
                                } else {
                                    ui.colored_label(
                                        egui::Color32::from_rgb(100, 200, 100),
                                        "Everything up to date!",
                                    );
                                }
                            }
                            Err(e) => {
                                ui.colored_label(egui::Color32::RED, format!("Error: {}", e));
                            }
                        }
                    }
                }

            });

        ui.add_space(10.0);
        ui.separator();
        ui.add_space(10.0);

        // ============================================================
        // Advanced Settings Section
        // ============================================================
        egui::CollapsingHeader::new("Advanced Settings")
            .default_open(false)
            .show(ui, |ui| {
                ui.add_space(5.0);

                // --- Cache Location ---
                ui.label(egui::RichText::new("Cache Location").strong());
                ui.label(
                    egui::RichText::new("Where to store downloaded files (MO2/Vortex installers, dependencies)")
                        .size(11.0)
                        .color(egui::Color32::GRAY),
                );
                ui.add_space(5.0);

                let current_cache = if app.config.cache_location.is_empty() {
                    format!("{} (default)", AppConfig::get_default_cache_dir().display())
                } else {
                    app.config.cache_location.clone()
                };
                ui.label(format!("Current: {}", current_cache));
                ui.add_space(5.0);

                ui.horizontal(|ui| {
                    if ui.button("Change Location").clicked() {
                        if let Some(path) = rfd::FileDialog::new()
                            .set_title("Select Cache Location")
                            .pick_folder()
                        {
                            app.config.cache_location = path.to_string_lossy().to_string();
                            app.config.save();
                            log_action(&format!("Cache location changed to: {}", app.config.cache_location));
                        }
                    }

                    if !app.config.cache_location.is_empty()
                        && ui.button("Reset to Default").clicked()
                    {
                        app.config.cache_location = String::new();
                        app.config.save();
                        log_action("Cache location reset to default");
                    }

                    if ui.button("Open Cache Folder").clicked() {
                        let cache_path = app.config.get_cache_dir();
                        let _ = std::fs::create_dir_all(&cache_path);
                        let _ = std::process::Command::new("xdg-open").arg(&cache_path).spawn();
                    }
                });
            });

        ui.add_space(10.0);
        ui.separator();
        ui.add_space(10.0);

        // ============================================================
        // Prefix Cleanup Section
        // ============================================================
        egui::CollapsingHeader::new("Prefix Cleanup")
            .default_open(false)
            .show(ui, |ui| {
                ui.add_space(5.0);
                ui.label(egui::RichText::new("Manage NaK-created Wine Prefixes").strong());
                ui.label(
                    egui::RichText::new("Clean up orphaned prefixes after removing mod managers from Steam")
                        .size(11.0)
                        .color(egui::Color32::GRAY),
                );
                ui.add_space(10.0);

                let managed = ManagedPrefixes::load();

                if managed.prefixes.is_empty() {
                    ui.label("No managed prefixes found.");
                    ui.label(
                        egui::RichText::new("Prefixes will appear here after installing mod managers via NaK.")
                            .size(11.0)
                            .color(egui::Color32::GRAY),
                    );
                } else {
                    // Get all AppIDs currently in shortcuts.vdf
                    let active_app_ids = get_active_shortcut_app_ids();

                    let mut to_delete: Option<u32> = None;
                    let mut to_update: Option<crate::config::ManagedPrefix> = None;

                    for prefix in &managed.prefixes {
                        let is_active = active_app_ids.contains(&prefix.app_id);
                        let prefix_exists = std::path::Path::new(&prefix.prefix_path).exists();

                        egui::Frame::none()
                            .fill(egui::Color32::from_rgb(35, 35, 45))
                            .rounding(egui::Rounding::same(6.0))
                            .inner_margin(10.0)
                            .show(ui, |ui| {
                                ui.horizontal(|ui| {
                                    // Manager icon/type
                                    let type_color = if prefix.manager_type == crate::config::ManagerType::MO2 {
                                        egui::Color32::from_rgb(100, 150, 255)
                                    } else {
                                        egui::Color32::from_rgb(255, 150, 100)
                                    };
                                    ui.colored_label(type_color, format!("[{}]", prefix.manager_type));

                                    // Instance name
                                    ui.label(egui::RichText::new(&prefix.name).strong());

                                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                        // Status badge
                                        if is_active {
                                            egui::Frame::none()
                                                .fill(egui::Color32::from_rgb(30, 60, 30))
                                                .rounding(egui::Rounding::same(4.0))
                                                .inner_margin(egui::vec2(8.0, 4.0))
                                                .show(ui, |ui| {
                                                    ui.colored_label(
                                                        egui::Color32::from_rgb(100, 200, 100),
                                                        "In Use",
                                                    );
                                                });
                                        } else {
                                            egui::Frame::none()
                                                .fill(egui::Color32::from_rgb(60, 40, 30))
                                                .rounding(egui::Rounding::same(4.0))
                                                .inner_margin(egui::vec2(8.0, 4.0))
                                                .show(ui, |ui| {
                                                    ui.colored_label(
                                                        egui::Color32::from_rgb(255, 180, 100),
                                                        "Removed From Steam",
                                                    );
                                                });
                                        }
                                    });
                                });

                                ui.add_space(5.0);

                                // Details row with AppID and Proton selector
                                ui.horizontal(|ui| {
                                    ui.label(
                                        egui::RichText::new(format!("AppID: {}", prefix.app_id))
                                            .size(11.0)
                                            .color(egui::Color32::GRAY),
                                    );

                                    if !prefix_exists {
                                        ui.label(
                                            egui::RichText::new("|")
                                                .size(11.0)
                                                .color(egui::Color32::DARK_GRAY),
                                        );
                                        ui.label(
                                            egui::RichText::new("Prefix deleted")
                                                .size(11.0)
                                                .color(egui::Color32::from_rgb(255, 100, 100)),
                                        );
                                    }

                                    // Proton selector
                                    if prefix_exists && !app.steam_protons.is_empty() {
                                        ui.label(
                                            egui::RichText::new("|")
                                                .size(11.0)
                                                .color(egui::Color32::DARK_GRAY),
                                        );

                                        let current_proton = prefix.proton_config_name.as_deref()
                                            .and_then(|name| app.steam_protons.iter().find(|p| p.config_name == name))
                                            .or_else(|| app.steam_protons.first());

                                        let current_display = current_proton
                                            .map(|p| p.name.as_str())
                                            .unwrap_or("Select Proton");

                                        let combo_id = format!("proton_select_{}", prefix.app_id);
                                        egui::ComboBox::from_id_salt(&combo_id)
                                            .selected_text(egui::RichText::new(current_display).size(11.0))
                                            .width(140.0)
                                            .show_ui(ui, |ui| {
                                                for proton in &app.steam_protons {
                                                    let is_selected = prefix.proton_config_name.as_deref() == Some(&proton.config_name);
                                                    if ui.selectable_label(is_selected, &proton.name).clicked() {
                                                        ManagedPrefixes::update_proton(prefix.app_id, &proton.config_name);
                                                    }
                                                }
                                            });
                                    }
                                });

                                // Prefix path (truncated safely for UTF-8)
                                let path_display = truncate_path(&prefix.prefix_path, 60);
                                ui.label(
                                    egui::RichText::new(path_display)
                                        .size(10.0)
                                        .color(egui::Color32::DARK_GRAY),
                                );

                                ui.add_space(5.0);

                                // Actions
                                ui.horizontal(|ui| {
                                    // Open folder button (always available if exists)
                                    if prefix_exists
                                        && ui.small_button("Open Folder").clicked()
                                    {
                                        let _ = std::process::Command::new("xdg-open")
                                            .arg(&prefix.prefix_path)
                                            .spawn();
                                    }

                                    // Update Scripts button (only if prefix exists and NaK Tools exists)
                                    let tools_dir = std::path::Path::new(&prefix.install_path).join("NaK Tools");
                                    if prefix_exists && tools_dir.exists()
                                        && ui.small_button("Update Scripts").clicked()
                                    {
                                        to_update = Some(prefix.clone());
                                    }

                                    // Delete button (only if NOT active)
                                    if !is_active && prefix_exists
                                        && ui.small_button(egui::RichText::new("Delete Prefix").color(egui::Color32::from_rgb(255, 100, 100))).clicked()
                                    {
                                        to_delete = Some(prefix.app_id);
                                    } else if !is_active && !prefix_exists
                                        && ui.small_button("Remove Entry").clicked()
                                    {
                                        // Just remove from tracking if prefix already deleted
                                        ManagedPrefixes::unregister(prefix.app_id);
                                    }
                                });
                            });

                        ui.add_space(8.0);
                    }

                    // Handle deletion outside the loop to avoid borrow issues
                    if let Some(app_id) = to_delete {
                        match ManagedPrefixes::delete_prefix(app_id) {
                            Ok(_) => {
                                log_action(&format!("Deleted prefix with AppID: {}", app_id));
                            }
                            Err(e) => {
                                log_action(&format!("Failed to delete prefix: {}", e));
                            }
                        }
                    }

                    // Handle script regeneration outside the loop
                    if let Some(prefix) = to_update {
                        // Find the Proton to use - prefer the stored one, fallback to first available
                        let proton = prefix.proton_config_name.as_deref()
                            .and_then(|name| app.steam_protons.iter().find(|p| p.config_name == name))
                            .or_else(|| app.steam_protons.first());

                        if let Some(proton) = proton {
                            let install_path = std::path::Path::new(&prefix.install_path);
                            let prefix_path = std::path::Path::new(&prefix.prefix_path);

                            match crate::installers::regenerate_nak_tools_scripts(
                                prefix.manager_type,
                                install_path,
                                prefix_path,
                                prefix.app_id,
                                &proton.path,
                            ) {
                                Ok(_) => {
                                    log_action(&format!("Updated scripts for {} (AppID: {}) using {}", prefix.name, prefix.app_id, proton.name));
                                    // Always update stored Proton to current one
                                    ManagedPrefixes::update_proton(prefix.app_id, &proton.config_name);
                                }
                                Err(e) => {
                                    log_action(&format!("Failed to update scripts: {}", e));
                                }
                            }
                        } else {
                            log_action("No Proton available - cannot update scripts");
                        }
                    }
                }
            });

        ui.add_space(10.0);
        ui.separator();
        ui.add_space(10.0);

        // ============================================================
        // About Section
        // ============================================================
        egui::CollapsingHeader::new("About")
            .default_open(false)
            .show(ui, |ui| {
                ui.label("NaK - Linux Modding Helper (Rust Edition)");
                ui.label(format!("Version: {}", env!("CARGO_PKG_VERSION")));
                ui.add_space(5.0);
                ui.hyperlink_to("GitHub Repository", "https://github.com/SulfurNitride/NaK");
                ui.add_space(10.0);

                ui.horizontal(|ui| {
                    if ui.button("Open NaK Folder").clicked() {
                        let config = AppConfig::load();
                        let nak_path = config.get_data_path();
                        let _ = std::process::Command::new("xdg-open").arg(&nak_path).spawn();
                    }

                    if ui.button("Open Logs Folder").clicked() {
                        // Logs are now in current working directory
                        let logs_path = std::env::current_dir().unwrap_or_else(|_| std::path::PathBuf::from("."));
                        let _ = std::process::Command::new("xdg-open").arg(&logs_path).spawn();
                    }
                });
            });
    });
}

pub fn render_updater(app: &mut MyApp, ui: &mut egui::Ui) {
    ui.heading("Version");
    ui.separator();

    egui::ScrollArea::vertical().show(ui, |ui| {
        // Current version info
        ui.add_space(10.0);
        ui.label(egui::RichText::new("NaK - Linux Modding Helper").size(18.0));
        ui.label(format!("Current Version: {}", env!("CARGO_PKG_VERSION")));
        ui.add_space(10.0);

        ui.separator();
        ui.add_space(10.0);

        // Update status
        let is_checking = *app.is_checking_update.lock().unwrap();
        let is_installing = *app.is_installing_update.lock().unwrap();
        let update_installed = *app.update_installed.lock().unwrap();
        let update_info = app.update_info.lock().unwrap().clone();
        let update_error = app.update_error.lock().unwrap().clone();

        // Show restart prompt if update was installed
        if update_installed {
            egui::Frame::none()
                .fill(egui::Color32::from_rgb(40, 80, 40))
                .rounding(egui::Rounding::same(4.0))
                .inner_margin(10.0)
                .show(ui, |ui| {
                    ui.colored_label(
                        egui::Color32::from_rgb(150, 255, 150),
                        "Update installed successfully!",
                    );
                    ui.label("Please restart NaK to use the new version.");
                    ui.add_space(5.0);
                    if ui.button("Restart Now").clicked() {
                        let exe = std::env::current_exe().ok();
                        if let Some(exe_path) = exe {
                            let _ = std::process::Command::new(&exe_path).spawn();
                            std::process::exit(0);
                        }
                    }
                });
            ui.add_space(10.0);
        }

        if is_checking {
            ui.horizontal(|ui| {
                ui.spinner();
                ui.label("Checking for updates...");
            });
        } else if is_installing {
            ui.horizontal(|ui| {
                ui.spinner();
                ui.label("Installing update...");
            });
        } else if let Some(ref info) = update_info {
            if info.is_update_available {
                egui::Frame::none()
                    .fill(egui::Color32::from_rgb(40, 60, 40))
                    .rounding(egui::Rounding::same(4.0))
                    .inner_margin(10.0)
                    .show(ui, |ui| {
                        ui.colored_label(
                            egui::Color32::from_rgb(100, 200, 100),
                            format!("Update available: v{}", info.latest_version),
                        );
                        ui.label(format!("Current: v{}", info.current_version));
                    });

                if !info.release_notes.is_empty() {
                    ui.add_space(10.0);
                    egui::CollapsingHeader::new("Release Notes")
                        .default_open(true)
                        .show(ui, |ui| {
                            egui::ScrollArea::vertical()
                                .max_height(200.0)
                                .show(ui, |ui| {
                                    ui.label(&info.release_notes);
                                });
                        });
                }

                ui.add_space(10.0);

                if info.download_url.is_some() {
                    if crate::updater::can_self_update() {
                        if ui.button("Install Update").clicked() {
                            log_action("Install update clicked");
                            let url = info.download_url.clone().unwrap();
                            let is_installing = app.is_installing_update.clone();
                            let update_error = app.update_error.clone();
                            let update_installed = app.update_installed.clone();

                            *is_installing.lock().unwrap() = true;
                            *update_error.lock().unwrap() = None;

                            std::thread::spawn(move || {
                                match crate::updater::install_update(&url) {
                                    Ok(_) => {
                                        *update_installed.lock().unwrap() = true;
                                    }
                                    Err(e) => {
                                        *update_error.lock().unwrap() = Some(e.to_string());
                                    }
                                }
                                *is_installing.lock().unwrap() = false;
                            });
                        }
                    } else {
                        ui.colored_label(
                            egui::Color32::from_rgb(255, 200, 100),
                            "Cannot self-update (no write permission to executable location)",
                        );
                        if ui.button("Copy Download URL").clicked() {
                            if let Some(url) = &info.download_url {
                                ui.output_mut(|o| o.copied_text = url.clone());
                            }
                        }
                    }
                } else {
                    ui.label("No Linux binary found in release");
                    if ui.link("Download from GitHub").clicked() {
                        let _ = std::process::Command::new("xdg-open")
                            .arg("https://github.com/SulfurNitride/NaK/releases/latest")
                            .spawn();
                    }
                }
            } else {
                ui.colored_label(
                    egui::Color32::from_rgb(100, 200, 100),
                    format!("You're up to date! (v{})", info.current_version),
                );
            }
        } else {
            ui.label("Click 'Check for Updates' to see if a new version is available.");
        }

        if let Some(error) = update_error {
            ui.add_space(5.0);
            ui.colored_label(egui::Color32::RED, format!("Error: {}", error));
        }

        ui.add_space(15.0);

        ui.horizontal(|ui| {
            if ui.add_enabled(!is_checking && !is_installing, egui::Button::new("Check for Updates")).clicked() {
                log_action("Check for updates clicked");
                let is_checking = app.is_checking_update.clone();
                let update_info = app.update_info.clone();
                let update_error = app.update_error.clone();

                *is_checking.lock().unwrap() = true;
                *update_error.lock().unwrap() = None;

                std::thread::spawn(move || {
                    match crate::updater::check_for_updates() {
                        Ok(info) => {
                            *update_info.lock().unwrap() = Some(info);
                        }
                        Err(e) => {
                            *update_error.lock().unwrap() = Some(e.to_string());
                        }
                    }
                    *is_checking.lock().unwrap() = false;
                });
            }

            if ui.link("GitHub Releases").clicked() {
                let _ = std::process::Command::new("xdg-open")
                    .arg("https://github.com/SulfurNitride/NaK/releases")
                    .spawn();
            }
        });
    });
}

/// Safely truncate a path string for display (UTF-8 safe)
fn truncate_path(path: &str, max_chars: usize) -> String {
    let char_count = path.chars().count();
    if char_count <= max_chars {
        path.to_string()
    } else {
        // Take the last (max_chars - 3) characters and prepend "..."
        let skip = char_count.saturating_sub(max_chars - 3);
        let truncated: String = path.chars().skip(skip).collect();
        format!("...{}", truncated)
    }
}

/// Get all AppIDs currently in Steam's shortcuts.vdf
fn get_active_shortcut_app_ids() -> HashSet<u32> {
    let mut app_ids = HashSet::new();

    // Find Steam path
    if let Some(steam_path) = crate::steam::find_steam_path() {
        // Find all user directories in userdata
        let userdata_path = std::path::Path::new(&steam_path).join("userdata");
        if let Ok(entries) = std::fs::read_dir(&userdata_path) {
            for entry in entries.flatten() {
                // Skip "0" folder - it's a special Steam folder for offline/anonymous mode
                if let Some(name) = entry.path().file_name() {
                    if name.to_string_lossy() == "0" {
                        continue;
                    }
                }

                let shortcuts_path = entry.path().join("config/shortcuts.vdf");
                if shortcuts_path.exists() {
                    // Try to load shortcuts file
                    if let Ok(shortcuts) = ShortcutsVdf::parse(&shortcuts_path) {
                        for shortcut in &shortcuts.shortcuts {
                            app_ids.insert(shortcut.appid);
                        }
                    }
                }
            }
        }
    }

    app_ids
}
