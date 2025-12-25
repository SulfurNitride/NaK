//! Simple pages: Getting Started, Marketplace, Settings, First Run Setup

use crate::app::{MyApp, Page};
use crate::config::{AppConfig, StorageManager};
use crate::logging::log_action;
use crate::wine::runtime;
use eframe::egui;

/// First-run setup page - shown on first launch to configure SLR preference
pub fn render_first_run_setup(app: &mut MyApp, ui: &mut egui::Ui) {
    // Wrap in scroll area for fullscreen/small window support
    egui::ScrollArea::vertical().show(ui, |ui| {
        ui.vertical_centered(|ui| {
            ui.add_space(20.0);

            ui.heading(egui::RichText::new("Welcome to NaK!").size(28.0).strong());
            ui.add_space(5.0);
            ui.label(
                egui::RichText::new("Linux Modding Helper")
                    .size(16.0)
                    .color(egui::Color32::GRAY),
            );

            ui.add_space(20.0);
            ui.separator();
            ui.add_space(15.0);

            // SLR Configuration Section
            ui.heading(egui::RichText::new("Runtime Configuration").size(20.0));
            ui.add_space(10.0);

            // Calculate max width based on available space
            let max_width = ui.available_width().min(600.0);

            // Explanation
            egui::Frame::none()
                .fill(egui::Color32::from_rgb(35, 35, 45))
                .rounding(egui::Rounding::same(8.0))
                .inner_margin(15.0)
                .show(ui, |ui| {
                    ui.set_max_width(max_width);

                    ui.label(egui::RichText::new("What is Steam Linux Runtime (SLR)?").strong().size(14.0));
                    ui.add_space(8.0);

                    ui.label("SLR is a containerized environment that provides consistent libraries for running Windows applications via Proton.");
                    ui.add_space(10.0);

                    ui.colored_label(
                        egui::Color32::from_rgb(100, 200, 100),
                        "Pros:",
                    );
                    ui.label("  - Functions more like Steam does when running games");
                    ui.label("  - More consistent behavior across different Linux distributions");
                    ui.add_space(8.0);

                    ui.colored_label(
                        egui::Color32::from_rgb(255, 180, 100),
                        "Cons:",
                    );
                    ui.label("  - Might cause unexpected issues");
                    ui.add_space(8.0);

                    ui.colored_label(
                        egui::Color32::from_rgb(150, 150, 150),
                        "Requirements:",
                    );
                    ui.label("  - ~750MB disk space for runtime files");
                });

            ui.add_space(15.0);

            // Important note
            egui::Frame::none()
                .fill(egui::Color32::from_rgb(50, 50, 30))
                .rounding(egui::Rounding::same(8.0))
                .inner_margin(12.0)
                .show(ui, |ui| {
                    ui.set_max_width(max_width);
                    ui.label(
                        egui::RichText::new("Note: You can change this setting anytime in Settings > Advanced or per-prefix in the Prefix Manager. If you choose 'No' now and want to enable SLR later, you'll just need to wait for the download to complete.")
                            .color(egui::Color32::from_rgb(255, 220, 100)),
                    );
                });

            ui.add_space(20.0);

            // Choice buttons
            ui.label(egui::RichText::new("Would you like to use Steam Linux Runtime?").size(16.0));
            ui.add_space(15.0);

            let slr_installed = runtime::is_runtime_installed();
            let is_downloading = *app.is_downloading.lock().unwrap();

            // Center buttons using a centered horizontal layout
            ui.horizontal(|ui| {
                let button_width = 200.0;
                let total_buttons_width = button_width * 2.0 + 20.0; // 2 buttons + spacing
                let available = ui.available_width();
                let padding = ((available - total_buttons_width) / 2.0).max(0.0);

                ui.add_space(padding);

                // Yes button
                let yes_text = if slr_installed {
                    "Yes, use SLR (Already installed)"
                } else if is_downloading {
                    "Yes, use SLR (Downloading...)"
                } else {
                    "Yes, use SLR (Recommended)"
                };

                if ui.add_sized(
                    [button_width, 40.0],
                    egui::Button::new(egui::RichText::new(yes_text).size(13.0))
                ).clicked() {
                    log_action("First-run setup: User chose to use SLR");
                    app.config.use_steam_runtime = true;
                    app.config.first_run_completed = true;
                    app.config.save();

                    // Start SLR download if not installed
                    if !slr_installed && !is_downloading {
                        app.start_slr_download();
                    }

                    app.current_page = Page::GettingStarted;
                }

                ui.add_space(20.0);

                // No button
                if ui.add_sized(
                    [button_width, 40.0],
                    egui::Button::new(egui::RichText::new("No, use Direct Proton").size(13.0))
                ).clicked() {
                    log_action("First-run setup: User chose Direct Proton (no SLR)");
                    app.config.use_steam_runtime = false;
                    app.config.first_run_completed = true;
                    app.config.save();
                    app.current_page = Page::GettingStarted;
                }
            });

            ui.add_space(15.0);

            // Show download progress if downloading
            if is_downloading {
                let status = app.download_status.lock().unwrap().clone();
                let progress = *app.download_progress.lock().unwrap();

                ui.add_space(5.0);
                ui.set_max_width(max_width);
                ui.label(&status);
                ui.add(egui::ProgressBar::new(progress).animate(true));
            }

            ui.add_space(20.0);

            // Skip for advanced users
            ui.label(
                egui::RichText::new("Not sure? 'Yes' works for most users. You can always change this later.")
                    .size(12.0)
                    .color(egui::Color32::GRAY),
            );

            ui.add_space(20.0);
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
        ui.label(
            egui::RichText::new("Get started by following these three simple steps:")
                .color(egui::Color32::LIGHT_GRAY),
        );

        ui.add_space(15.0);

        // ============================================================
        // Step 1: Pick a Proton Version
        // ============================================================
        ui.label(
            egui::RichText::new("1. Pick a Proton Version")
                .size(16.0)
                .strong(),
        );
        ui.label(
            egui::RichText::new("   NaK needs Proton to run Windows modding tools")
                .size(12.0)
                .color(egui::Color32::LIGHT_GRAY),
        );
        ui.add_space(5.0);
        ui.label("   - Recommended: Download Proton-GE (best compatibility)");
        ui.label("   - Alternative: Use system Proton if you prefer");
        ui.add_space(5.0);
        if ui.button("Open Proton Picker").clicked() {
            log_action("Navigate to Proton Picker from Getting Started");
            app.current_page = Page::ProtonTools;
        }

        ui.add_space(20.0);
        ui.separator();
        ui.add_space(10.0);

        // ============================================================
        // Step 2: Choose Your Modding Approach
        // ============================================================
        ui.label(
            egui::RichText::new("2. Choose Your Modding Approach")
                .size(16.0)
                .strong(),
        );
        ui.label(
            egui::RichText::new("   Pick the option that fits your modding style")
                .size(12.0)
                .color(egui::Color32::LIGHT_GRAY),
        );
        ui.add_space(10.0);

        // Option A: Mod Managers
        ui.horizontal(|ui| {
            if ui.button("Mod Managers").clicked() {
                log_action("Navigate to Mod Managers from Getting Started");
                app.current_page = Page::ModManagers;
            }
            ui.label(
                egui::RichText::new("Install MO2 or Vortex for full mod management")
                    .color(egui::Color32::LIGHT_GRAY),
            );
        });
        ui.label("      Best for: Heavy modding with load order management, mod profiles, etc.");

        ui.add_space(8.0);

        // Option B: Game Modding
        ui.horizontal(|ui| {
            if ui.button("Game Modding").clicked() {
                log_action("Navigate to Game Modding from Getting Started");
                app.current_page = Page::GameFixer;
            }
            ui.label(
                egui::RichText::new("Apply fixes directly to game prefixes")
                    .color(egui::Color32::LIGHT_GRAY),
            );
        });
        ui.label("      Best for: Simple modding without a dedicated mod manager");

        ui.add_space(20.0);
        ui.separator();
        ui.add_space(10.0);

        // ============================================================
        // Step 3: Check FAQ & Known Issues
        // ============================================================
        ui.label(
            egui::RichText::new("3. Check FAQ & Known Issues")
                .size(16.0)
                .strong(),
        );
        ui.label(
            egui::RichText::new("   Solutions to common problems and setup tips")
                .size(12.0)
                .color(egui::Color32::LIGHT_GRAY),
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
            ui.label("Need help?");
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
                            ui.label(egui::RichText::new("[Plugin]").size(16.0));
                            ui.strong(format!("Plugin {}", i));
                            ui.small("Description of plugin...");
                            ui.add_space(5.0);
                            if ui.button("Install").clicked() {}
                        });
                    });
                ui.add_space(10.0);
            }
        });
    });
}

pub fn render_settings(app: &mut MyApp, ui: &mut egui::Ui) {
    ui.heading("Settings");
    ui.separator();

    egui::ScrollArea::vertical().show(ui, |ui| {
        // ============================================================
        // Storage & Cache Section
        // ============================================================
        egui::CollapsingHeader::new("Storage & Cache")
            .default_open(true)
            .show(ui, |ui| {
                ui.add_space(5.0);

                // Cache storage info - only refresh every 5 seconds
                let should_refresh = app.storage_info_last_update.elapsed().as_secs() > 5
                    || app.cached_storage_info.is_none();

                if should_refresh {
                    app.cached_storage_info = Some(StorageManager::get_storage_info(&app.config.get_data_path()));
                    app.storage_info_last_update = std::time::Instant::now();
                }

                let storage_info = app.cached_storage_info.clone().unwrap_or_default();

                // Refresh button
                ui.horizontal(|ui| {
                    ui.label(egui::RichText::new("Storage Info").strong());
                    if ui.small_button("Refresh").clicked() {
                        app.cached_storage_info = Some(StorageManager::get_storage_info(&app.config.get_data_path()));
                        app.storage_info_last_update = std::time::Instant::now();
                    }
                });

                // --- Location Info ---
                ui.horizontal(|ui| {
                    ui.label("Data Path:");
                    ui.monospace(&storage_info.data_path);
                });
                ui.label(
                    egui::RichText::new("Config stored in: ~/.config/nak/")
                        .size(11.0)
                        .color(egui::Color32::GRAY),
                );

                // --- Usage Breakdown ---
                if storage_info.exists {
                    ui.add_space(5.0);
                    ui.horizontal(|ui| {
                        ui.label("Total Used:");
                        ui.strong(format!("{:.2} GB", storage_info.used_space_gb));
                        ui.label(" | Free:");
                        ui.strong(format!("{:.2} GB", storage_info.free_space_gb));
                    });

                    ui.add_space(5.0);
                    ui.indent("storage_breakdown", |ui| {
                        ui.horizontal(|ui| {
                            ui.label("• Prefixes:");
                            ui.strong(format!("{:.2} GB", storage_info.prefixes_size_gb));
                        });
                        ui.horizontal(|ui| {
                            ui.label("• Proton Versions:");
                            ui.strong(format!("{:.2} GB", storage_info.proton_size_gb));
                        });
                        ui.horizontal(|ui| {
                            ui.label("• Cache:");
                            ui.strong(format!("{:.2} GB", storage_info.cache_size_gb));
                        });

                        if storage_info.other_size_gb > 0.01 {
                            ui.horizontal(|ui| {
                                ui.label("• Other:");
                                ui.strong(format!("{:.2} GB", storage_info.other_size_gb))
                                  .on_hover_text("Includes logs, tmp files, and binaries");
                            });
                        }
                    });
                }

                ui.add_space(15.0);
                ui.separator();
                ui.add_space(10.0);

                // --- Cache Controls ---
                ui.label(egui::RichText::new("Cache Configuration").strong());

                let mut cache_enabled = app.cache_config.cache_enabled;
                if ui.checkbox(&mut cache_enabled, "Enable Caching").changed() {
                    app.cache_config.cache_enabled = cache_enabled;
                    app.cache_config.save();
                    log_action(&format!("Cache enabled: {}", cache_enabled));
                }

                ui.add_enabled_ui(cache_enabled, |ui| {
                    ui.indent("cache_options", |ui| {
                        let mut cache_deps = app.cache_config.cache_dependencies;
                        if ui.checkbox(&mut cache_deps, "Cache Dependencies (~1.7GB)").changed() {
                            app.cache_config.cache_dependencies = cache_deps;
                            app.cache_config.save();
                        }

                        let mut cache_mo2 = app.cache_config.cache_mo2;
                        if ui.checkbox(&mut cache_mo2, "Cache MO2 Downloads").changed() {
                            app.cache_config.cache_mo2 = cache_mo2;
                            app.cache_config.save();
                        }

                        let mut cache_vortex = app.cache_config.cache_vortex;
                        if ui.checkbox(&mut cache_vortex, "Cache Vortex Downloads").changed() {
                            app.cache_config.cache_vortex = cache_vortex;
                            app.cache_config.save();
                        }
                    });
                });

                ui.add_space(5.0);
                if ui.button("Clear Cache").clicked() {
                    log_action("Clear cache clicked");
                    if let Err(e) = app.cache_config.clear_cache(&app.config) {
                        eprintln!("Failed to clear cache: {}", e);
                    }
                }

                ui.add_space(15.0);
                ui.separator();
                ui.add_space(10.0);

                // --- Migration Controls ---
                ui.label(egui::RichText::new("Move Installation").strong());
                ui.label("Move the entire NaK folder to a different drive (e.g., SSD).");

                ui.horizontal(|ui| {
                    ui.add(
                        egui::TextEdit::singleline(&mut app.migration_path_input)
                            .hint_text("/path/to/new/location")
                            .desired_width(300.0),
                    );

                    if ui.button("Browse").clicked() {
                        log_action("Browse for migration path clicked");
                        if let Some(path) = rfd::FileDialog::new().pick_folder() {
                            app.migration_path_input = path.to_string_lossy().to_string();
                        }
                    }
                });

                ui.horizontal(|ui| {
                    let can_move = !app.migration_path_input.trim().is_empty();
                    if ui.add_enabled(can_move, egui::Button::new("Move NaK Here")).clicked() {
                        log_action(&format!("Move NaK to: {}", app.migration_path_input));
                        let path = std::path::PathBuf::from(app.migration_path_input.trim());
                        match StorageManager::move_data(&mut app.config, &path) {
                            Ok(msg) => {
                                crate::logging::log_info(&msg);
                                app.migration_path_input.clear();
                                // Force refresh storage info
                                app.cached_storage_info = None;
                                // Refresh prefix manager and detected prefixes (paths changed)
                                app.prefix_manager = crate::wine::PrefixManager::new();
                                app.detected_prefixes = app.prefix_manager.scan_prefixes();
                            }
                            Err(e) => {
                                crate::logging::log_error(&format!("Migration failed: {}", e));
                            }
                        }
                    }
                });
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

                // --- Steam Linux Runtime Toggle ---
                ui.label(egui::RichText::new("Steam Linux Runtime (Pressure Vessel)").strong());
                ui.label(
                    egui::RichText::new("Container runtime that provides consistent library environment")
                        .size(11.0)
                        .color(egui::Color32::GRAY),
                );
                ui.add_space(5.0);

                let mut use_slr = app.config.use_steam_runtime;
                if ui.checkbox(&mut use_slr, "Use Steam Linux Runtime").changed() {
                    app.config.use_steam_runtime = use_slr;
                    app.config.save();
                    log_action(&format!("Steam Linux Runtime: {}", if use_slr { "enabled" } else { "disabled" }));
                }

                ui.indent("slr_info", |ui| {
                    if use_slr {
                        ui.colored_label(
                            egui::Color32::from_rgb(100, 200, 100),
                            "Enabled - Launch scripts use containerized runtime",
                        );
                        ui.label(
                            egui::RichText::new("Recommended for most systems")
                                .size(11.0)
                                .color(egui::Color32::GRAY),
                        );
                    } else {
                        ui.colored_label(
                            egui::Color32::from_rgb(255, 200, 100),
                            "Disabled - Launch scripts use direct Proton execution",
                        );
                        ui.label(
                            egui::RichText::new("Use if you experience SLR-related errors")
                                .size(11.0)
                                .color(egui::Color32::GRAY),
                        );
                    }
                });

                ui.add_space(10.0);

                // --- Regenerate Scripts Button ---
                ui.label(egui::RichText::new("Regenerate Launch Scripts").strong());
                ui.label(
                    egui::RichText::new("Update all existing installation scripts with current settings")
                        .size(11.0)
                        .color(egui::Color32::GRAY),
                );
                ui.add_space(5.0);

                if ui.button("Regenerate All Scripts").clicked() {
                    log_action("Regenerate all scripts clicked");
                    match crate::scripts::regenerate_all_prefix_scripts() {
                        Ok(count) => {
                            crate::logging::log_info(&format!("Regenerated scripts for {} prefix(es)", count));
                        }
                        Err(e) => {
                            crate::logging::log_error(&format!("Failed to regenerate scripts: {}", e));
                        }
                    }
                }
                ui.label(
                    egui::RichText::new("Use after changing Steam Linux Runtime setting")
                        .size(11.0)
                        .color(egui::Color32::GRAY),
                );

                ui.add_space(15.0);
                ui.separator();
                ui.add_space(10.0);

                // --- Pre-Release Updates Toggle ---
                ui.label(egui::RichText::new("Pre-Release Updates").strong());
                ui.label(
                    egui::RichText::new("Get notified about pre-release versions (beta/testing builds)")
                        .size(11.0)
                        .color(egui::Color32::GRAY),
                );
                ui.add_space(5.0);

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
                        let config = AppConfig::load();
                        let logs_path = config.get_data_path().join("logs");
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
