//! Proton Picker page UI

use eframe::egui;
use std::sync::atomic::Ordering;
use std::thread;

use super::UiExt;
use crate::app::MyApp;
use crate::wine::{
    download_cachyos_proton, download_ge_proton, runtime, set_active_proton, GithubRelease,
};

pub fn render_proton_tools(app: &mut MyApp, ui: &mut egui::Ui) {
    ui.heading("Proton Picker");
    ui.separator();

    ui.horizontal(|ui| {
        ui.label("Active Proton:");
        let mut selected = app.config.selected_proton.clone();
        egui::ComboBox::from_id_salt("proton_combo")
            .selected_text(selected.as_deref().unwrap_or("Select Version"))
            .show_ui(ui, |ui| {
                for p in &app.proton_versions {
                    ui.selectable_value(&mut selected, Some(p.name.clone()), &p.name);
                }
            });

        // Save if changed and update active symlink
        if app.config.selected_proton != selected {
            app.config.selected_proton = selected.clone();
            app.config.save();

            // Update the 'active' symlink for the selected proton
            if let Some(name) = &selected {
                if let Some(proton) = app.proton_versions.iter().find(|p| &p.name == name) {
                    let _ = set_active_proton(proton);
                }
            }
        }
    });

    // =========================================================================
    // Steam Runtime Section
    // =========================================================================
    ui.add_space(20.0);
    ui.subheading("Steam Linux Runtime");

    let is_downloading_any = *app.is_downloading.lock().unwrap();
    let runtime_path = runtime::find_steam_runtime_sniper();

    if let Some(path) = runtime_path {
        ui.horizontal(|ui| {
            ui.label("Status:");
            ui.colored_label(egui::Color32::GREEN, "Installed");
        });
        ui.label(
            egui::RichText::new(path.to_string_lossy())
                .size(12.0)
                .color(egui::Color32::from_gray(180)),
        );
    } else {
        ui.horizontal(|ui| {
            ui.label("Status:");
            if is_downloading_any {
                ui.colored_label(egui::Color32::YELLOW, "Downloading...");
            } else {
                ui.colored_label(egui::Color32::RED, "Missing");
            }
        });
        ui.label("Required for stable containerized gaming. (Auto-downloads on startup)");

        ui.add_space(5.0);
        if ui
            .add_enabled(
                !is_downloading_any,
                egui::Button::new("Manually Download (~500MB)"),
            )
            .clicked()
        {
            download_runtime_ui(app);
        }
    }

    // =========================================================================
    // Unified Proton Downloads Section
    // =========================================================================
    ui.add_space(20.0);
    ui.subheading("Download Proton");

    // Source toggle buttons
    ui.horizontal(|ui| {
        let is_ge = app.proton_download_source == "ge";
        let is_cachyos = app.proton_download_source == "cachyos";

        if ui
            .selectable_label(is_ge, "GE-Proton")
            .on_hover_text("GloriousEggroll's Proton fork with game fixes")
            .clicked()
        {
            app.proton_download_source = "ge".to_string();
        }

        if ui
            .selectable_label(is_cachyos, "CachyOS Proton")
            .on_hover_text("CachyOS optimized Proton builds")
            .clicked()
        {
            app.proton_download_source = "cachyos".to_string();
        }

        ui.add_space(20.0);

        // Show fetching status
        let is_fetching = if app.proton_download_source == "ge" {
            *app.is_fetching_ge.lock().unwrap()
        } else {
            *app.is_fetching_cachyos.lock().unwrap()
        };

        if is_fetching {
            ui.spinner();
            ui.label("Fetching...");
        } else {
            // Refresh button
            if ui.button("⟳ Refresh").on_hover_text("Refresh available versions").clicked() {
                if app.proton_download_source == "ge" {
                    refresh_ge_releases(app);
                } else {
                    refresh_cachyos_releases(app);
                }
            }
        }
    });

    ui.add_space(10.0);

    // Single search bar
    ui.horizontal(|ui| {
        ui.label("Search:");
        ui.add(
            egui::TextEdit::singleline(&mut app.proton_search_query).desired_width(300.0),
        );
    });

    // Download Status Bar
    let status = app.download_status.lock().unwrap().clone();
    let progress = *app.download_progress.lock().unwrap();
    let is_downloading_any = *app.is_downloading.lock().unwrap();

    if is_downloading_any {
        ui.add_space(5.0);
        ui.add(egui::ProgressBar::new(progress).text(&status).animate(true));
    } else if !status.is_empty() {
        ui.add_space(5.0);
        ui.colored_label(egui::Color32::LIGHT_BLUE, format!("ℹ {}", status));
    }

    ui.add_space(10.0);

    // Create a set of installed version names for fast lookup
    let installed_names: Vec<String> = app.proton_versions.iter().map(|p| p.name.clone()).collect();

    // Show releases based on selected source
    if app.proton_download_source == "ge" {
        render_ge_releases(app, ui, &installed_names, is_downloading_any);
    } else {
        render_cachyos_releases(app, ui, &installed_names, is_downloading_any);
    }
}

fn render_ge_releases(
    app: &mut MyApp,
    ui: &mut egui::Ui,
    installed_names: &[String],
    is_downloading: bool,
) {
    let filtered_releases: Vec<GithubRelease> = {
        let releases = app.available_ge_versions.lock().unwrap();
        releases
            .iter()
            .filter(|r| {
                app.proton_search_query.is_empty()
                    || r.tag_name
                        .to_lowercase()
                        .contains(&app.proton_search_query.to_lowercase())
            })
            .take(10)
            .cloned()
            .collect()
    };

    if filtered_releases.is_empty() {
        let releases_empty = app.available_ge_versions.lock().unwrap().is_empty();
        if !releases_empty {
            ui.label("No matching versions found.");
        } else if !*app.is_fetching_ge.lock().unwrap() {
            ui.label("No versions available (Check internet connection).");
        }
        return;
    }

    egui::ScrollArea::vertical()
        .id_salt("ge_releases")
        .show(ui, |ui| {
            for release in filtered_releases {
                ui.horizontal(|ui| {
                    ui.strong(&release.tag_name);
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        if installed_names.contains(&release.tag_name) {
                            if ui.button("Uninstall").clicked() {
                                app.pending_proton_delete =
                                    Some((release.tag_name.clone(), "ge".to_string()));
                            }
                            ui.add_enabled(false, egui::Button::new("Installed"));
                        } else if ui
                            .add_enabled(!is_downloading, egui::Button::new("Download"))
                            .clicked()
                        {
                            download_ge_proton_ui(app, &release);
                        }
                    });
                });
                ui.separator();
            }
        });
}

fn render_cachyos_releases(
    app: &mut MyApp,
    ui: &mut egui::Ui,
    installed_names: &[String],
    is_downloading: bool,
) {
    // Filter CachyOS releases - only show ones with v2 assets
    let filtered_releases: Vec<GithubRelease> = {
        let releases = app.available_cachyos_versions.lock().unwrap();
        releases
            .iter()
            .filter(|r| {
                // Must have a v2 tar.xz asset
                r.assets.iter().any(|a| a.name.contains("_v2.tar.xz"))
            })
            .filter(|r| {
                app.proton_search_query.is_empty()
                    || r.tag_name
                        .to_lowercase()
                        .contains(&app.proton_search_query.to_lowercase())
            })
            .take(10)
            .cloned()
            .collect()
    };

    if filtered_releases.is_empty() {
        let releases_empty = app.available_cachyos_versions.lock().unwrap().is_empty();
        if !releases_empty {
            ui.label("No matching versions found.");
        } else if !*app.is_fetching_cachyos.lock().unwrap() {
            ui.label("No versions available (Check internet connection).");
        }
        return;
    }

    egui::ScrollArea::vertical()
        .id_salt("cachyos_releases")
        .show(ui, |ui| {
            for release in filtered_releases {
                ui.horizontal(|ui| {
                    ui.strong(&release.tag_name);
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        // Check if installed - extract the date part
                        let date_part = release
                            .tag_name
                            .split('-')
                            .find(|s| s.len() == 8 && s.chars().all(|c| c.is_ascii_digit()))
                            .unwrap_or("");

                        let matching_installed = installed_names.iter().find(|n| {
                            n.contains("proton-cachyos") && n.contains(date_part) && !date_part.is_empty()
                        });

                        if let Some(installed_name) = matching_installed {
                            let name_to_delete = installed_name.clone();
                            if ui.button("Uninstall").clicked() {
                                app.pending_proton_delete =
                                    Some((name_to_delete, "cachyos".to_string()));
                            }
                            ui.add_enabled(false, egui::Button::new("Installed"));
                        } else if ui
                            .add_enabled(!is_downloading, egui::Button::new("Download"))
                            .clicked()
                        {
                            download_cachyos_proton_ui(app, &release);
                        }
                    });
                });
                ui.separator();
            }
        });
}

fn download_cachyos_proton_ui(app: &MyApp, release: &GithubRelease) {
    let is_downloading = app.is_downloading.clone();
    let status_msg = app.download_status.clone();
    let progress_val = app.download_progress.clone();
    let needs_refresh = app.download_needs_refresh.clone();

    // Find the v2.tar.xz asset
    let asset = release
        .assets
        .iter()
        .find(|a| a.name.contains("_v2.tar.xz"));
    if asset.is_none() {
        if let Ok(mut guard) = status_msg.lock() {
            *guard = "Error: No v2.tar.xz asset found".to_string();
        }
        return;
    }
    let asset = asset.unwrap().clone();
    let file_name = asset.name.clone();
    let download_url = asset.browser_download_url.clone();

    let mut dl_guard = is_downloading.lock().unwrap();
    if *dl_guard {
        return;
    }
    *dl_guard = true;
    drop(dl_guard);

    // Reset progress
    if let Ok(mut guard) = progress_val.lock() {
        *guard = 0.0;
    }
    if let Ok(mut guard) = status_msg.lock() {
        *guard = format!("Starting download: {}...", file_name);
    }

    thread::spawn(move || {
        let cb_progress_inner = progress_val.clone();
        let cb_status_progress = status_msg.clone();

        let progress_callback = move |current: u64, total: u64| {
            if total > 0 {
                let p = current as f32 / total as f32;
                if let Ok(mut guard) = cb_progress_inner.lock() {
                    *guard = p;
                }
                if let Ok(mut guard) = cb_status_progress.lock() {
                    *guard = format!("Downloading: {:.1}%", p * 100.0);
                }
            }
        };

        let cb_status_extract = status_msg.clone();
        let status_callback = move |msg: &str| {
            if let Ok(mut guard) = cb_status_extract.lock() {
                *guard = msg.to_string();
            }
        };

        match download_cachyos_proton(download_url, file_name, progress_callback, status_callback) {
            Ok(_) => {
                if let Ok(mut guard) = status_msg.lock() {
                    *guard = "Download complete!".to_string();
                }
                if let Ok(mut guard) = progress_val.lock() {
                    *guard = 1.0;
                }
                // Signal UI to refresh proton list
                needs_refresh.store(true, Ordering::Relaxed);
            }
            Err(e) => {
                if let Ok(mut guard) = status_msg.lock() {
                    *guard = format!("Error: {}", e);
                }
            }
        }
        if let Ok(mut guard) = is_downloading.lock() {
            *guard = false;
        }
    });
}

fn download_ge_proton_ui(app: &MyApp, release: &GithubRelease) {
    let is_downloading = app.is_downloading.clone();
    let status_msg = app.download_status.clone();
    let progress_val = app.download_progress.clone();
    let needs_refresh = app.download_needs_refresh.clone();

    // Find the .tar.gz asset
    let asset = release.assets.iter().find(|a| a.name.ends_with(".tar.gz"));
    if asset.is_none() {
        if let Ok(mut guard) = status_msg.lock() {
            *guard = "Error: No .tar.gz asset found".to_string();
        }
        return;
    }
    let asset = asset.unwrap().clone();
    let file_name = asset.name.clone();
    let download_url = asset.browser_download_url.clone();

    let mut dl_guard = is_downloading.lock().unwrap();
    if *dl_guard {
        return;
    }
    *dl_guard = true;
    drop(dl_guard);

    // Reset progress
    if let Ok(mut guard) = progress_val.lock() {
        *guard = 0.0;
    }
    if let Ok(mut guard) = status_msg.lock() {
        *guard = format!("Starting download: {}...", file_name);
    }

    thread::spawn(move || {
        let cb_progress_inner = progress_val.clone();
        let cb_status_progress = status_msg.clone();

        let progress_callback = move |current: u64, total: u64| {
            if total > 0 {
                let p = current as f32 / total as f32;
                if let Ok(mut guard) = cb_progress_inner.lock() {
                    *guard = p;
                }
                if let Ok(mut guard) = cb_status_progress.lock() {
                    *guard = format!("Downloading: {:.1}%", p * 100.0);
                }
            }
        };

        let cb_status_extract = status_msg.clone();
        let status_callback = move |msg: &str| {
            if let Ok(mut guard) = cb_status_extract.lock() {
                *guard = msg.to_string();
            }
        };

        match download_ge_proton(download_url, file_name, progress_callback, status_callback) {
            Ok(_) => {
                if let Ok(mut guard) = status_msg.lock() {
                    *guard = "Download complete!".to_string();
                }
                if let Ok(mut guard) = progress_val.lock() {
                    *guard = 1.0;
                }
                // Signal UI to refresh proton list
                needs_refresh.store(true, Ordering::Relaxed);
            }
            Err(e) => {
                if let Ok(mut guard) = status_msg.lock() {
                    *guard = format!("Error: {}", e);
                }
            }
        }
        if let Ok(mut guard) = is_downloading.lock() {
            *guard = false;
        }
    });
}

fn download_runtime_ui(app: &MyApp) {
    let is_downloading = app.is_downloading.clone();
    let status_msg = app.download_status.clone();
    let progress_val = app.download_progress.clone();
    let needs_refresh = app.download_needs_refresh.clone();

    let mut dl_guard = is_downloading.lock().unwrap();
    if *dl_guard {
        return;
    }
    *dl_guard = true;
    drop(dl_guard);

    if let Ok(mut guard) = progress_val.lock() {
        *guard = 0.0;
    }
    if let Ok(mut guard) = status_msg.lock() {
        *guard = "Downloading Steam Runtime...".to_string();
    }

    thread::spawn(move || {
        let cb_progress_inner = progress_val.clone();
        let cb_status_inner = status_msg.clone();

        let callback = move |current: u64, total: u64| {
            if total > 0 {
                let p = current as f32 / total as f32;
                if let Ok(mut guard) = cb_progress_inner.lock() {
                    *guard = p;
                }
                if let Ok(mut guard) = cb_status_inner.lock() {
                    *guard = format!("Downloading Runtime: {:.1}%", p * 100.0);
                }
            }
        };

        match crate::wine::runtime::download_runtime(callback) {
            Ok(_) => {
                if let Ok(mut guard) = status_msg.lock() {
                    *guard = "Runtime Installed!".to_string();
                }
                if let Ok(mut guard) = progress_val.lock() {
                    *guard = 1.0;
                }
                // Signal UI to refresh
                needs_refresh.store(true, Ordering::Relaxed);
            }
            Err(e) => {
                if let Ok(mut guard) = status_msg.lock() {
                    *guard = format!("Error: {}", e);
                }
            }
        }
        if let Ok(mut guard) = is_downloading.lock() {
            *guard = false;
        }
    });
}

/// Refresh GE-Proton releases from GitHub
fn refresh_ge_releases(app: &MyApp) {
    use crate::wine::fetch_ge_releases;

    let is_fetching = app.is_fetching_ge.clone();
    let versions = app.available_ge_versions.clone();

    // Don't start if already fetching
    if *is_fetching.lock().unwrap() {
        return;
    }

    *is_fetching.lock().unwrap() = true;

    thread::spawn(move || {
        match fetch_ge_releases() {
            Ok(releases) => {
                *versions.lock().unwrap() = releases;
            }
            Err(e) => {
                eprintln!("Failed to fetch GE releases: {}", e);
            }
        }
        *is_fetching.lock().unwrap() = false;
    });
}

/// Refresh CachyOS Proton releases from GitHub
fn refresh_cachyos_releases(app: &MyApp) {
    use crate::wine::fetch_cachyos_releases;

    let is_fetching = app.is_fetching_cachyos.clone();
    let versions = app.available_cachyos_versions.clone();

    // Don't start if already fetching
    if *is_fetching.lock().unwrap() {
        return;
    }

    *is_fetching.lock().unwrap() = true;

    thread::spawn(move || {
        match fetch_cachyos_releases() {
            Ok(releases) => {
                *versions.lock().unwrap() = releases;
            }
            Err(e) => {
                eprintln!("Failed to fetch CachyOS releases: {}", e);
            }
        }
        *is_fetching.lock().unwrap() = false;
    });
}
