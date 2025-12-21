//! Game Modding Helper page UI
//!
//! Allows users to find Steam/Heroic games and apply modding fixes to their Wine prefixes.
//! Uses the same dependencies and registry settings as the mod manager installers.

use eframe::egui;
use std::sync::atomic::AtomicBool;
use std::sync::Arc;
use std::thread;

use crate::app::MyApp;
use crate::games::{DetectedGame, GameFixer, GameSource};
use crate::installers::STANDARD_DEPS;

pub fn render_game_fixer(app: &mut MyApp, ui: &mut egui::Ui) {
    ui.heading("Game Modding Helper");
    ui.label("Apply modding fixes (dependencies & registry) to Steam and Heroic game prefixes.");
    ui.separator();

    // Check if we're currently applying fixes
    let is_applying = *app.is_applying_game_fix.lock().unwrap();

    if is_applying {
        render_applying_status(app, ui);
        return;
    }

    // Top bar with search, refresh, and proton selection
    ui.horizontal(|ui| {
        ui.label("Search:");
        ui.add(egui::TextEdit::singleline(&mut app.game_search_query).desired_width(200.0));

        ui.add_space(20.0);

        if ui.button("Refresh Games").clicked() {
            app.refresh_detected_games();
        }

        ui.add_space(10.0);
        ui.label(format!("{} games found", app.detected_games.len()));
    });

    ui.add_space(5.0);

    // Proton selection in a compact row
    ui.horizontal(|ui| {
        ui.label("Proton:");
        let mut selected = app.config.selected_proton.clone();
        egui::ComboBox::from_id_salt("game_fix_proton")
            .width(200.0)
            .selected_text(selected.as_deref().unwrap_or("Select Proton"))
            .show_ui(ui, |ui| {
                for p in &app.proton_versions {
                    ui.selectable_value(&mut selected, Some(p.name.clone()), &p.name);
                }
            });

        if app.config.selected_proton != selected {
            app.config.selected_proton = selected;
            app.config.save();
        }

        ui.add_space(20.0);
        ui.label(
            egui::RichText::new("Applies same fixes as Mod Managers")
                .size(11.0)
                .color(egui::Color32::from_gray(150)),
        );
    });

    ui.add_space(10.0);
    ui.separator();

    // Filter games by search query
    let search_query = app.game_search_query.to_lowercase();
    let filtered_games: Vec<DetectedGame> = app
        .detected_games
        .iter()
        .filter(|g| search_query.is_empty() || g.name.to_lowercase().contains(&search_query))
        .cloned()
        .collect();

    let total_games = app.detected_games.len();
    let no_games = filtered_games.is_empty();
    let no_results = no_games && total_games > 0;

    // Games list
    ui.strong("Detected Games");
    ui.add_space(5.0);

    egui::ScrollArea::vertical()
        .id_salt("games_list")
        .show(ui, |ui| {
            if no_games {
                if no_results {
                    ui.label("No games match your search.");
                } else {
                    ui.label("No games detected. Make sure Steam or Heroic is installed.");
                }
            }

            for game in &filtered_games {
                render_game_card(app, ui, game);
            }
        });
}

fn render_game_card(app: &mut MyApp, ui: &mut egui::Ui, game: &DetectedGame) {
    let has_prefix = game.has_prefix;
    let source_text = match &game.source {
        GameSource::Steam { app_id } => format!("Steam ({})", app_id),
        GameSource::Heroic { store } => format!("Heroic ({})", store),
    };

    egui::Frame::group(ui.style())
        .rounding(egui::Rounding::same(4.0))
        .fill(egui::Color32::from_gray(28))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_gray(50)))
        .inner_margin(8.0)
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.vertical(|ui| {
                    ui.strong(&game.name);
                    ui.label(
                        egui::RichText::new(&source_text)
                            .size(11.0)
                            .color(egui::Color32::from_gray(150)),
                    );

                    // Prefix status
                    if has_prefix {
                        ui.label(
                            egui::RichText::new("[OK] Has Wine prefix")
                                .size(11.0)
                                .color(egui::Color32::GREEN),
                        );
                    } else {
                        ui.label(
                            egui::RichText::new("[--] No prefix (run game first)")
                                .size(11.0)
                                .color(egui::Color32::YELLOW),
                        );
                    }
                });

                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    let can_fix = has_prefix
                        && app.winetricks_path.lock().unwrap().is_some()
                        && app.config.selected_proton.is_some();

                    if ui
                        .add_enabled(can_fix, egui::Button::new("Apply Fixes"))
                        .on_disabled_hover_text(if !has_prefix {
                            "Run the game first to create a Wine prefix"
                        } else if app.config.selected_proton.is_none() {
                            "Select a Proton version first"
                        } else {
                            "Winetricks not available"
                        })
                        .clicked()
                    {
                        apply_fixes_to_game(app, game.clone());
                    }

                    if ui
                        .button("Open")
                        .on_hover_text("Open install folder")
                        .clicked()
                    {
                        let _ = std::process::Command::new("xdg-open")
                            .arg(&game.install_path)
                            .spawn();
                    }
                });
            });
        });
    ui.add_space(4.0);
}

fn render_applying_status(app: &mut MyApp, ui: &mut egui::Ui) {
    ui.vertical_centered(|ui| {
        ui.add_space(50.0);
        ui.heading("Applying Fixes...");
        ui.add_space(20.0);

        let status = app.game_fix_status.lock().unwrap().clone();
        ui.label(&status);

        ui.add_space(20.0);

        // Show logs
        let logs = app.game_fix_logs.lock().unwrap().clone();
        egui::ScrollArea::vertical()
            .max_height(300.0)
            .show(ui, |ui| {
                for log in &logs {
                    ui.label(
                        egui::RichText::new(log)
                            .size(12.0)
                            .color(egui::Color32::from_gray(180)),
                    );
                }
            });

        ui.add_space(20.0);

        if ui.button("Cancel").clicked() {
            *app.is_applying_game_fix.lock().unwrap() = false;
        }
    });
}

fn apply_fixes_to_game(app: &mut MyApp, game: DetectedGame) {
    // Get proton
    let selected_proton = app.config.selected_proton.clone();
    let proton = if let Some(ref name) = selected_proton {
        app.proton_versions.iter().find(|p| &p.name == name).cloned()
    } else {
        None
    };

    let Some(proton) = proton else {
        *app.game_fix_status.lock().unwrap() = "Error: No Proton version selected!".to_string();
        return;
    };

    let winetricks = app.winetricks_path.lock().unwrap().clone();
    let Some(winetricks_path) = winetricks else {
        *app.game_fix_status.lock().unwrap() = "Error: Winetricks not available!".to_string();
        return;
    };

    // Set state
    *app.is_applying_game_fix.lock().unwrap() = true;
    *app.game_fix_status.lock().unwrap() = format!("Preparing to fix {}...", game.name);
    app.game_fix_logs.lock().unwrap().clear();

    let is_applying = app.is_applying_game_fix.clone();
    let status = app.game_fix_status.clone();
    let logs = app.game_fix_logs.clone();
    let cancel_flag = Arc::new(AtomicBool::new(false));

    // Use STANDARD_DEPS but exclude dotnet48
    let deps: Vec<&str> = STANDARD_DEPS
        .iter()
        .filter(|d| *d != &"dotnet48")
        .copied()
        .collect();

    thread::spawn(move || {
        let log_callback = {
            let logs = logs.clone();
            let status = status.clone();
            move |msg: String| {
                if let Ok(mut guard) = status.lock() {
                    *guard = msg.clone();
                }
                if let Ok(mut guard) = logs.lock() {
                    guard.push(msg);
                }
            }
        };

        match GameFixer::apply_fixes(
            &game,
            &proton,
            &winetricks_path,
            &deps,
            true, // apply registry
            log_callback,
            cancel_flag,
        ) {
            Ok(()) => {
                if let Ok(mut guard) = status.lock() {
                    *guard = format!("Fixes applied successfully to {}!", game.name);
                }
            }
            Err(e) => {
                if let Ok(mut guard) = status.lock() {
                    *guard = format!("Error: {}", e);
                }
            }
        }

        // Keep the dialog open for a moment to show results
        std::thread::sleep(std::time::Duration::from_secs(2));

        if let Ok(mut guard) = is_applying.lock() {
            *guard = false;
        }
    });
}
