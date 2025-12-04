//! Simple pages: Getting Started, Marketplace, Settings

use eframe::egui;
use crate::app::{MyApp, Page};
use crate::config::StorageManager;
use crate::logging::log_action;

pub fn render_getting_started(app: &mut MyApp, ui: &mut egui::Ui) {
    egui::ScrollArea::vertical().show(ui, |ui| {
        // ============================================================
        // Header
        // ============================================================
        ui.heading(egui::RichText::new("Welcome to NaK!").size(24.0).strong());
        ui.label(egui::RichText::new("Linux Modding Helper").size(14.0).color(egui::Color32::GRAY));

        ui.separator();
        ui.add_space(10.0);

        ui.label("NaK makes it easy to run Windows modding tools on Linux using Proton.");
        ui.label(egui::RichText::new("Get started by following these three simple steps:").color(egui::Color32::LIGHT_GRAY));

        ui.add_space(15.0);

        // ============================================================
        // Step 1: Pick a Proton Version
        // ============================================================
        ui.label(egui::RichText::new("1. Pick a Proton Version").size(16.0).strong());
        ui.label(egui::RichText::new("   NaK needs Proton to run Windows modding tools").size(12.0).color(egui::Color32::LIGHT_GRAY));
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
        // Step 2: Always Use Portable Mode for MO2
        // ============================================================
        ui.label(egui::RichText::new("2. Always Use Portable Mode for MO2").size(16.0).strong());
        ui.label(egui::RichText::new("   This is CRITICAL for proper operation on Linux").size(12.0).strong().color(egui::Color32::from_rgb(255, 200, 100)));
        ui.add_space(5.0);
        ui.label(egui::RichText::new("   When MO2 asks during installation:").strong());
        ui.label(egui::RichText::new("   [YES] SELECT: Portable").strong().color(egui::Color32::LIGHT_GREEN));
        ui.label(egui::RichText::new("   [NO]  NEVER SELECT: Global").strong().color(egui::Color32::from_rgb(255, 100, 100)));
        ui.add_space(5.0);
        ui.label("   - Portable mode keeps all files in one place");
        ui.label("   - Makes backups and management much easier");
        ui.label("   - Avoids Wine registry issues");

        ui.add_space(20.0);
        ui.separator();
        ui.add_space(10.0);

        // ============================================================
        // Step 3: Check FAQ & Known Issues
        // ============================================================
        ui.label(egui::RichText::new("3. Check FAQ & Known Issues").size(16.0).strong());
        ui.label(egui::RichText::new("   Solutions to common problems and setup tips").size(12.0).color(egui::Color32::LIGHT_GRAY));
        ui.add_space(5.0);
        ui.label("   - Comprehensive FAQ with troubleshooting guides");
        ui.label("   - Known issues and their solutions");
        ui.label("   - Tips & best practices for Linux modding");
        ui.add_space(5.0);
        if ui.button("View FAQ & Known Issues").clicked() {
            log_action("Open FAQ in browser");
            let _ = std::process::Command::new("xdg-open")
                .arg("https://github.com/SulfurNitride/NaK/blob/main/docs/FAQ.md")
                .spawn();
        }

        ui.add_space(20.0);

        // ============================================================
        // Quick Tips
        // ============================================================
        ui.separator();
        ui.add_space(10.0);

        ui.label(egui::RichText::new("Quick Tips:").size(14.0).strong());
        ui.label("- You can switch between pages using the tabs on the left");
        ui.label("- Use 'Proton Picker' to manage GE-Proton versions");
        ui.label("- Check Settings to configure caching and storage location");

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

pub fn render_settings(app: &mut MyApp, ui: &mut egui::Ui) {
    ui.heading("Settings");
    ui.separator();

    egui::ScrollArea::vertical().show(ui, |ui| {
        // ============================================================
        // Cache Settings Section
        // ============================================================
        egui::CollapsingHeader::new("Cache Settings")
            .default_open(true)
            .show(ui, |ui| {
                ui.add_space(5.0);

                // Cache info display
                let cache_info = app.cache_config.get_cache_info();
                if cache_info.exists {
                    ui.horizontal(|ui| {
                        ui.label("Cache Size:");
                        ui.strong(format!("{:.2} MB ({} files)", cache_info.size_mb, cache_info.file_count));
                    });
                } else {
                    ui.label("Cache: Not created yet");
                }

                ui.horizontal(|ui| {
                    ui.label("Location:");
                    ui.monospace(&cache_info.location);
                });

                ui.add_space(10.0);

                // Cache toggles
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

                ui.add_space(10.0);

                // Clear cache button
                if ui.button("🗑 Clear Cache").clicked() {
                    log_action("Clear cache clicked");
                    if let Err(e) = app.cache_config.clear_cache() {
                        eprintln!("Failed to clear cache: {}", e);
                    }
                }
            });

        ui.add_space(10.0);
        ui.separator();
        ui.add_space(10.0);

        // ============================================================
        // Storage Location Section (NaK Migrator)
        // ============================================================
        egui::CollapsingHeader::new("Storage Location")
            .default_open(true)
            .show(ui, |ui| {
                ui.add_space(5.0);

                let storage_mgr = StorageManager::new();
                let storage_info = storage_mgr.get_storage_info();

                // Current location display
                ui.horizontal(|ui| {
                    ui.label("NaK Path:");
                    ui.monospace(&storage_info.nak_path);
                });

                if storage_info.is_symlink {
                    ui.horizontal(|ui| {
                        ui.label("Real Location:");
                        ui.monospace(&storage_info.real_path);
                    });
                    ui.colored_label(egui::Color32::LIGHT_BLUE, "↳ Using symlink to custom location");
                }

                if storage_info.exists {
                    ui.horizontal(|ui| {
                        ui.label("Used:");
                        ui.strong(format!("{:.2} GB", storage_info.used_space_gb));
                        ui.label(" | Free:");
                        ui.strong(format!("{:.2} GB", storage_info.free_space_gb));
                    });
                }

                ui.add_space(10.0);

                // Detect installations
                let installations = storage_mgr.detect_installations();
                if installations.total_count > 0 {
                    ui.label(format!("Detected: {} prefixes ({} MO2, {} Vortex)",
                        installations.total_count,
                        installations.mo2_count,
                        installations.vortex_count
                    ));
                    if installations.has_proton_ge {
                        ui.small("• Has Proton-GE installations");
                    }
                    if installations.has_cache {
                        ui.small("• Has cached files");
                    }
                }

                ui.add_space(10.0);

                // Migration controls - text input + button (works on all WMs including DWM)
                ui.label("Move NaK to a different location:");
                ui.horizontal(|ui| {
                    ui.add(egui::TextEdit::singleline(&mut app.migration_path_input)
                        .hint_text("/path/to/new/location")
                        .desired_width(300.0));

                    if ui.button("📂 Browse").clicked() {
                        log_action("Browse for migration path clicked");
                        // Try file dialog (won't work on minimal WMs like DWM)
                        if let Some(path) = rfd::FileDialog::new().pick_folder() {
                            app.migration_path_input = path.to_string_lossy().to_string();
                        }
                    }
                });

                ui.horizontal(|ui| {
                    let can_move = !app.migration_path_input.trim().is_empty();
                    if ui.add_enabled(can_move, egui::Button::new("📦 Move NaK Here")).clicked() {
                        log_action(&format!("Move NaK to: {}", app.migration_path_input));
                        let path = std::path::PathBuf::from(app.migration_path_input.trim());
                        match storage_mgr.setup_symlink(&path, true) {
                            Ok(msg) => {
                                crate::logging::log_info(&msg);
                                app.migration_path_input.clear();
                            }
                            Err(e) => {
                                crate::logging::log_error(&format!("Migration failed: {}", e));
                            }
                        }
                    }

                    if storage_info.is_symlink {
                        if ui.button("↩ Restore to Default Location").clicked() {
                            log_action("Restore NaK location clicked");
                            match storage_mgr.remove_symlink() {
                                Ok(msg) => {
                                    crate::logging::log_info(&msg);
                                }
                                Err(e) => {
                                    crate::logging::log_error(&format!("Restore failed: {}", e));
                                }
                            }
                        }
                    }
                });

                ui.add_space(5.0);
                ui.small("Enter a path or click Browse. Moving to SSD can improve performance.");
                ui.small("Your prefixes and cached files will be preserved.");
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
                ui.label("Version: 0.1.0");
                ui.add_space(5.0);
                ui.hyperlink_to("GitHub Repository", "https://github.com/SulfurNitride/NaK");
                ui.add_space(5.0);

                if ui.button("📂 Open NaK Folder").clicked() {
                    let home = std::env::var("HOME").unwrap_or_default();
                    let nak_path = format!("{}/NaK", home);
                    let _ = std::process::Command::new("xdg-open")
                        .arg(&nak_path)
                        .spawn();
                }

                if ui.button("📂 Open Logs Folder").clicked() {
                    let home = std::env::var("HOME").unwrap_or_default();
                    let logs_path = format!("{}/NaK/logs", home);
                    let _ = std::process::Command::new("xdg-open")
                        .arg(&logs_path)
                        .spawn();
                }
            });
    });
}
