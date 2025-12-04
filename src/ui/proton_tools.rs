//! Proton Picker page UI

use eframe::egui;
use std::thread;

use crate::app::MyApp;
use crate::wine::{GithubRelease, download_ge_proton, delete_ge_proton, download_cachyos_proton, delete_cachyos_proton, set_active_proton};
use super::UiExt;

pub fn render_proton_tools(app: &mut MyApp, ui: &mut egui::Ui) {
    ui.heading("Proton Picker");
    ui.separator();

    ui.horizontal(|ui| {
        ui.label("Active Proton:");
        let mut selected = app.config.selected_proton.clone();
        let _combo_response = egui::ComboBox::from_id_salt("proton_combo")
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

    ui.add_space(20.0);
    ui.subheading("Download GE-Proton");

    ui.horizontal(|ui| {
        if *app.is_fetching_ge.lock().unwrap() {
            ui.spinner();
            ui.label("Fetching from GitHub...");
        }
    });

    ui.add_space(10.0);
    ui.horizontal(|ui| {
        ui.label("Search:");
        ui.text_edit_singleline(&mut app.ge_search_query);
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

    let filtered_releases: Vec<GithubRelease> = {
        let releases = app.available_ge_versions.lock().unwrap();
        releases.iter()
            .filter(|r| app.ge_search_query.is_empty() || r.tag_name.to_lowercase().contains(&app.ge_search_query.to_lowercase()))
            .take(5)
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
    }

    // Create a set of installed version names for fast lookup
    let installed_names: Vec<String> = app.proton_versions.iter().map(|p| p.name.clone()).collect();

    for release in filtered_releases {
        ui.horizontal(|ui| {
            ui.strong(&release.tag_name);
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                if installed_names.contains(&release.tag_name) {
                    ui.horizontal(|ui| {
                        ui.add_enabled(false, egui::Button::new("Installed"));
                        if ui.button("Uninstall").clicked() {
                            if let Err(e) = delete_ge_proton(&release.tag_name) {
                                eprintln!("Failed to delete: {}", e);
                            }
                            app.should_refresh_proton = true;
                        }
                    });
                } else {
                    if ui.add_enabled(!is_downloading_any, egui::Button::new("Download")).clicked() {
                        download_ge_proton_ui(app, &release);
                    }
                }
            });
        });
        ui.separator();
    }

    // =========================================================================
    // CachyOS Proton Section
    // =========================================================================
    ui.add_space(20.0);
    ui.subheading("Download CachyOS Proton");

    ui.horizontal(|ui| {
        if *app.is_fetching_cachyos.lock().unwrap() {
            ui.spinner();
            ui.label("Fetching from GitHub...");
        }
    });

    ui.add_space(10.0);
    ui.horizontal(|ui| {
        ui.label("Search:");
        ui.text_edit_singleline(&mut app.cachyos_search_query);
    });

    ui.add_space(10.0);

    // Filter CachyOS releases - only show ones with v2 assets
    let filtered_cachyos: Vec<GithubRelease> = {
        let releases = app.available_cachyos_versions.lock().unwrap();
        releases.iter()
            .filter(|r| {
                // Must have a v2 tar.xz asset
                r.assets.iter().any(|a| a.name.contains("_v2.tar.xz"))
            })
            .filter(|r| app.cachyos_search_query.is_empty() || r.tag_name.to_lowercase().contains(&app.cachyos_search_query.to_lowercase()))
            .take(5)
            .cloned()
            .collect()
    };

    if filtered_cachyos.is_empty() {
        let releases_empty = app.available_cachyos_versions.lock().unwrap().is_empty();
        if !releases_empty {
            ui.label("No matching versions found.");
        } else if !*app.is_fetching_cachyos.lock().unwrap() {
            ui.label("No versions available (Check internet connection).");
        }
    }

    for release in filtered_cachyos {
        ui.horizontal(|ui| {
            ui.strong(&release.tag_name);
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                // Check if installed - CachyOS extracts to a folder based on the tarball name
                let is_installed = installed_names.iter().any(|n| n.contains("proton-cachyos") && release.tag_name.contains(&n.replace("proton-cachyos-", "").split('-').next().unwrap_or("")));

                if is_installed {
                    ui.horizontal(|ui| {
                        ui.add_enabled(false, egui::Button::new("Installed"));
                        // Find the installed name to delete
                        if let Some(installed_name) = installed_names.iter().find(|n| n.contains("proton-cachyos")) {
                            if ui.button("Uninstall").clicked() {
                                if let Err(e) = delete_cachyos_proton(installed_name) {
                                    eprintln!("Failed to delete: {}", e);
                                }
                                app.should_refresh_proton = true;
                            }
                        }
                    });
                } else {
                    if ui.add_enabled(!is_downloading_any, egui::Button::new("Download")).clicked() {
                        download_cachyos_proton_ui(app, &release);
                    }
                }
            });
        });
        ui.separator();
    }
}

fn download_cachyos_proton_ui(app: &MyApp, release: &GithubRelease) {
    let is_downloading = app.is_downloading.clone();
    let status_msg = app.download_status.clone();
    let progress_val = app.download_progress.clone();

    // Find the v2.tar.xz asset
    let asset = release.assets.iter().find(|a| a.name.contains("_v2.tar.xz"));
    if asset.is_none() {
        *status_msg.lock().unwrap() = "Error: No v2.tar.xz asset found".to_string();
        return;
    }
    let asset = asset.unwrap().clone();
    let file_name = asset.name.clone();
    let download_url = asset.browser_download_url.clone();

    let mut dl_guard = is_downloading.lock().unwrap();
    if *dl_guard { return; }
    *dl_guard = true;
    drop(dl_guard);

    // Reset progress
    *progress_val.lock().unwrap() = 0.0;
    *status_msg.lock().unwrap() = format!("Starting download: {}...", file_name);

    thread::spawn(move || {
        let cb_progress_inner = progress_val.clone();
        let cb_status_inner = status_msg.clone();

        let callback = move |current: u64, total: u64| {
            if total > 0 {
                let p = current as f32 / total as f32;
                *cb_progress_inner.lock().unwrap() = p;
                *cb_status_inner.lock().unwrap() = format!("Downloading: {:.1}%", p * 100.0);
            }
        };

        match download_cachyos_proton(download_url, file_name, callback) {
            Ok(_) => {
                 // SIGNAL REFRESH via special string suffix
                 *status_msg.lock().unwrap() = "Download complete! REFRESH".to_string();
                 *progress_val.lock().unwrap() = 1.0;
            }
            Err(e) => {
                 *status_msg.lock().unwrap() = format!("Error: {}", e);
            }
        }
        *is_downloading.lock().unwrap() = false;
    });
}

fn download_ge_proton_ui(app: &MyApp, release: &GithubRelease) {
    let is_downloading = app.is_downloading.clone();
    let status_msg = app.download_status.clone();
    let progress_val = app.download_progress.clone();

    // Find the .tar.gz asset
    let asset = release.assets.iter().find(|a| a.name.ends_with(".tar.gz"));
    if asset.is_none() {
        *status_msg.lock().unwrap() = "Error: No .tar.gz asset found".to_string();
        return;
    }
    let asset = asset.unwrap().clone();
    let file_name = asset.name.clone();
    let download_url = asset.browser_download_url.clone();

    let mut dl_guard = is_downloading.lock().unwrap();
    if *dl_guard { return; }
    *dl_guard = true;
    drop(dl_guard);

    // Reset progress
    *progress_val.lock().unwrap() = 0.0;
    *status_msg.lock().unwrap() = format!("Starting download: {}...", file_name);

    thread::spawn(move || {
        let cb_progress_inner = progress_val.clone();
        let cb_status_inner = status_msg.clone();

        let callback = move |current: u64, total: u64| {
            if total > 0 {
                let p = current as f32 / total as f32;
                *cb_progress_inner.lock().unwrap() = p;
                *cb_status_inner.lock().unwrap() = format!("Downloading: {:.1}%", p * 100.0);
            }
        };

        match download_ge_proton(download_url, file_name, callback) {
            Ok(_) => {
                 // SIGNAL REFRESH via special string suffix
                 *status_msg.lock().unwrap() = "Download complete! REFRESH".to_string();
                 *progress_val.lock().unwrap() = 1.0;
            }
            Err(e) => {
                 *status_msg.lock().unwrap() = format!("Error: {}", e);
            }
        }
        *is_downloading.lock().unwrap() = false;
    });
}
