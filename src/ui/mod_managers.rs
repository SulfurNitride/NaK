//! Mod Managers page UI

use eframe::egui;
use std::sync::atomic::Ordering;
use std::thread;

use crate::app::{InstallWizard, MyApp, WizardStep};
use crate::installers::{
    apply_dpi, get_available_disk_space, install_mo2, kill_wineserver,
    launch_dpi_test_app, setup_existing_mo2, TaskContext, DPI_PRESETS,
    MIN_REQUIRED_DISK_SPACE_GB,
};
use crate::logging::log_action;

pub fn render_mod_managers(app: &mut MyApp, ui: &mut egui::Ui) {
    ui.heading("MO2 Installation");
    ui.separator();
    ui.add_space(10.0);

    // Set manager type for MO2 (only option now)
    if app.install_wizard.manager_type.is_empty() {
        app.install_wizard.manager_type = "MO2".to_string();
    }

    // Main Content - go directly to MO2 manager view
    egui::ScrollArea::vertical().show(ui, |ui| {
        render_manager_view(app, ui, "MO2");
    });
}

fn render_manager_view(app: &mut MyApp, ui: &mut egui::Ui, manager_name: &str) {
    ui.label("Install or set up an existing MO2 installation.");
    ui.add_space(10.0);

    let is_busy = *app.is_installing_manager.lock().unwrap();
    let status = app.install_status.lock().unwrap().clone();
    let progress = *app.install_progress.lock().unwrap();

    // Check for install result and update wizard state
    if !is_busy && status.contains("Complete!") {
        // Read the result values from the install thread
        if let Some(app_id) = app.install_result_app_id.lock().unwrap().take() {
            app.install_wizard.installed_app_id = Some(app_id);
        }
        if let Some(prefix_path) = app.install_result_prefix_path.lock().unwrap().take() {
            app.install_wizard.installed_prefix_path = Some(prefix_path);
        }
    }

    // Render Wizard
    let action = render_install_wizard(
        &mut app.install_wizard,
        is_busy,
        &status,
        progress,
        manager_name,
        &app.steam_protons,
        ui
    );

    match action {
        WizardAction::Start => start_installation(app),
        WizardAction::Reset => {
            // Reset wizard to start over
            app.install_wizard = InstallWizard::default();
            // Ensure we are back on the right manager page if reset changes things (it shouldn't here)
            app.install_wizard.manager_type = manager_name.to_string();
            // Clear installation status to prevent state detection issues
            *app.install_status.lock().unwrap() = String::new();
            *app.install_progress.lock().unwrap() = 0.0;
            app.logs.lock().unwrap().clear();
            // Clear DPI test processes
            app.dpi_test_processes.lock().unwrap().clear();
            // Reset cancel flag so new installations can start
            app.cancel_install.store(false, Ordering::Relaxed);
        }
        WizardAction::Cancel => {
             app.cancel_install.store(true, Ordering::Relaxed);
             *app.install_status.lock().unwrap() = "Cancelling...".to_string();
        }
        WizardAction::ApplyDpi(dpi_value) => {
            handle_apply_dpi(app, dpi_value);
        }
        WizardAction::LaunchTestApp(app_name) => {
            handle_launch_test_app(app, &app_name);
        }
        WizardAction::ConfirmDpi => {
            handle_confirm_dpi(app);
        }
        WizardAction::None => {}
    }
}

enum WizardAction {
    None,
    Start,
    Reset,
    Cancel,
    ApplyDpi(u32),           // Apply DPI value
    LaunchTestApp(String),   // Launch test app by name
    ConfirmDpi,              // Confirm DPI and proceed to finished
}

fn render_install_wizard(
    wizard: &mut InstallWizard,
    is_busy: bool,
    status: &str,
    _progress: f32,
    manager_name: &str,
    steam_protons: &[crate::steam::SteamProton],
    ui: &mut egui::Ui
) -> WizardAction {
    let mut action = WizardAction::None;
    // We use a mutable reference to action inside the closure to bubble up the event
    let action_ref = &mut action;

    if is_busy {
            ui.vertical_centered(|ui| {
            ui.add_space(20.0);
            // Global progress bar is shown at the top of the window, so we just show status here
            ui.label(egui::RichText::new("Installation in Progress...").heading());
            ui.add_space(10.0);
            ui.label(status);
            ui.add_space(20.0);
            
            if ui.button("Cancel").clicked() {
                    *action_ref = WizardAction::Cancel;
            }
        });
        return action;
    }

    // Handle installation completion states
    // Check when install finishes (from ProtonSelect step where "Start Installation" is clicked)
    if !is_busy && wizard.step != WizardStep::Finished && wizard.step != WizardStep::Selection && wizard.step != WizardStep::DpiSetup {
        if status.contains("Cancelled") {
            // Installation was cancelled - reset wizard to allow retry
            wizard.step = WizardStep::Selection;
            wizard.last_install_error = None;
            wizard.name.clear();
            wizard.path.clear();
            wizard.validation_error = None;
            wizard.force_install = false;
        } else if status.starts_with("Error:") {
            // Installation failed with error
            wizard.last_install_error = Some(status.to_string());
            wizard.step = WizardStep::Finished;
        } else if status.contains("Complete!") || status.contains("Installed!") || status.contains("Setup Complete!") {
            // Installation succeeded - move to DPI setup
            wizard.last_install_error = None;
            wizard.step = WizardStep::DpiSetup;
        }
    }

    match wizard.step {
        WizardStep::Selection => {
            // Allow buttons to expand
            let btn_size = egui::vec2(ui.available_width() / 2.0 - 10.0, 50.0);

            ui.horizontal(|ui| {
                if ui.add_sized(btn_size, egui::Button::new(format!("Install New {}", manager_name))).clicked() {
                    wizard.install_type = "New".to_string();
                    wizard.step = WizardStep::NameInput;
                }
                if ui.add_sized(btn_size, egui::Button::new(format!("Setup Existing {}", manager_name))).clicked() {
                    wizard.install_type = "Existing".to_string();
                    wizard.step = WizardStep::NameInput;
                }
            });
        },
        WizardStep::NameInput => {
            ui.heading("Step 1: Instance Name");
            ui.label("Give your installation a unique name. This will be used to identify the prefix folder.");
            ui.add_space(5.0);

            ui.text_edit_singleline(&mut wizard.name);

            ui.add_space(10.0);
            ui.horizontal(|ui| {
                if ui.button("Back").clicked() {
                    wizard.step = WizardStep::Selection;
                }
                if !wizard.name.trim().is_empty() && ui.button("Next").clicked() {
                    wizard.step = WizardStep::PathInput;
                    wizard.force_install = false;
                    // Validate existing path if any
                    if !wizard.path.is_empty() {
                        validate_path(wizard);
                    } else {
                        wizard.validation_error = None;
                    }
                }
            });
        },
        WizardStep::PathInput => {
            ui.heading("Step 2: Install Location");
            if wizard.install_type == "New" {
                ui.label("Select an EMPTY directory where you want to install.");
            } else {
                ui.label(format!("Select the existing {} directory.", manager_name));
            }
            ui.add_space(5.0);
            
            ui.horizontal(|ui| {
                let old_path = wizard.path.clone();
                ui.text_edit_singleline(&mut wizard.path);
                // Validate when path changes (either by typing or browsing)
                if wizard.path != old_path {
                    validate_path(wizard);
                }
                if ui.button("Browse").clicked() {
                    if let Some(path) = rfd::FileDialog::new().pick_folder() {
                        wizard.path = path.to_string_lossy().to_string();
                        validate_path(wizard);
                    }
                }
            });

            // Live Validation feedback
            if let Some(err) = &wizard.validation_error {
                ui.colored_label(egui::Color32::RED, err);

                // If it's the "not empty" warning, offer override
                if err.contains("not empty") {
                    ui.checkbox(&mut wizard.force_install, "I acknowledge this folder is not empty and files might be overwritten.");
                }
            } else if !wizard.path.is_empty() {
                ui.colored_label(egui::Color32::GREEN, "Path looks good");
            }

            // Disk space warning and override
            if wizard.low_disk_space && !wizard.path.is_empty() {
                ui.add_space(10.0);
                egui::Frame::none()
                    .fill(egui::Color32::from_rgb(80, 50, 30))
                    .rounding(egui::Rounding::same(4.0))
                    .inner_margin(10.0)
                    .show(ui, |ui| {
                        let required = if wizard.install_type == "Linked" { 1.0 } else { MIN_REQUIRED_DISK_SPACE_GB };
                        ui.colored_label(
                            egui::Color32::from_rgb(255, 180, 100),
                            format!(
                                "⚠ Low disk space: {:.1}GB available, {:.0}GB recommended",
                                wizard.available_disk_gb, required
                            ),
                        );
                        ui.label(
                            egui::RichText::new("Installation may fail or cause issues with insufficient space.")
                                .size(11.0)
                                .color(egui::Color32::from_rgb(200, 180, 150)),
                        );
                        ui.checkbox(
                            &mut wizard.disk_space_override,
                            "I understand and want to proceed anyway",
                        );
                    });
            }

            ui.add_space(15.0);
            ui.separator();
            ui.add_space(10.0);

            // Show warning if no Proton selected
            ui.add_space(10.0);
            ui.horizontal(|ui| {
                if ui.button("Back").clicked() {
                        wizard.step = WizardStep::NameInput;
                }

                // Proceed logic
                let mut can_proceed = !wizard.path.trim().is_empty();

                if let Some(err) = &wizard.validation_error {
                    if err.contains("not empty") {
                        // Allow if forced
                        if !wizard.force_install {
                            can_proceed = false;
                        }
                    } else {
                        // Block on other errors (like doesn't exist for Existing install)
                        can_proceed = false;
                    }
                }

                // Block if low disk space and override not checked
                if wizard.low_disk_space && !wizard.disk_space_override {
                    can_proceed = false;
                }

                let hover_text = if wizard.low_disk_space && !wizard.disk_space_override {
                    "Please acknowledge the low disk space warning to proceed."
                } else {
                    "Please resolve the path issues."
                };

                if ui.add_enabled(can_proceed, egui::Button::new("Next"))
                    .on_disabled_hover_text(hover_text)
                    .clicked()
                {
                    wizard.step = WizardStep::ProtonSelect;
                }
            });
        },
        WizardStep::ProtonSelect => {
            ui.heading("Step 3: Select Proton Version");
            ui.label("Choose which Proton version to use for MO2.");
            ui.add_space(10.0);

            if steam_protons.is_empty() {
                ui.colored_label(
                    egui::Color32::from_rgb(255, 150, 100),
                    "No Proton versions found in Steam!",
                );
                ui.add_space(5.0);
                ui.label("Please install a Proton version through Steam or ProtonUp-Qt.");
                ui.add_space(5.0);
                if ui.button("Open ProtonUp-Qt (Flathub)").clicked() {
                    let _ = std::process::Command::new("xdg-open")
                        .arg("https://flathub.org/apps/net.davidotek.pupgui2")
                        .spawn();
                }
            } else {
                ui.label(egui::RichText::new("Available Proton Versions:").strong());
                ui.add_space(5.0);

                egui::ScrollArea::vertical()
                    .max_height(300.0)
                    .show(ui, |ui| {
                        for proton in steam_protons {
                            let is_selected = wizard.selected_proton.as_ref() == Some(&proton.config_name);

                            let mut frame = egui::Frame::none()
                                .inner_margin(8.0)
                                .rounding(egui::Rounding::same(4.0));

                            if is_selected {
                                frame = frame.fill(egui::Color32::from_rgb(50, 80, 50));
                            }

                            frame.show(ui, |ui| {
                                ui.horizontal(|ui| {
                                    let radio = ui.radio(is_selected, "");

                                    ui.vertical(|ui| {
                                        let name_text = if proton.is_experimental {
                                            egui::RichText::new(&proton.name).strong().color(egui::Color32::from_rgb(150, 200, 255))
                                        } else if proton.name.contains("GE-Proton") {
                                            egui::RichText::new(&proton.name).strong().color(egui::Color32::from_rgb(255, 200, 100))
                                        } else {
                                            egui::RichText::new(&proton.name).strong()
                                        };
                                        ui.label(name_text);

                                        let desc = if proton.is_experimental {
                                            "Valve's experimental branch - Good for most games"
                                        } else if proton.name.contains("GE-Proton") {
                                            "GloriousEggroll - Extra patches for modding tools"
                                        } else if proton.is_steam_proton {
                                            "Steam's built-in Proton version"
                                        } else {
                                            "Custom Proton version"
                                        };
                                        ui.label(egui::RichText::new(desc).size(11.0).color(egui::Color32::GRAY));
                                    });

                                    if radio.clicked() || ui.interact(ui.min_rect(), ui.id().with(&proton.name), egui::Sense::click()).clicked() {
                                        wizard.selected_proton = Some(proton.config_name.clone());
                                    }
                                });
                            });
                        }
                    });
            }

            ui.add_space(15.0);

            // Recommendation box
            egui::Frame::none()
                .fill(egui::Color32::from_rgb(40, 50, 60))
                .rounding(egui::Rounding::same(6.0))
                .inner_margin(10.0)
                .show(ui, |ui| {
                    ui.label(egui::RichText::new("💡 Recommendation").strong());
                    ui.label("GE-Proton is recommended for modding tools like MO2 and Vortex.");
                    ui.label("Install it via ProtonUp-Qt if you don't have it.");
                });

            ui.add_space(15.0);
            ui.horizontal(|ui| {
                if ui.button("Back").clicked() {
                    wizard.step = WizardStep::PathInput;
                }

                let can_proceed = wizard.selected_proton.is_some();
                let button_label = match wizard.install_type.as_str() {
                    "New" | "Linked" => "Start Installation",
                    _ => "Setup Instance",
                };

                if ui.add_enabled(can_proceed, egui::Button::new(button_label))
                    .on_disabled_hover_text("Please select a Proton version.")
                    .clicked()
                {
                    *action_ref = WizardAction::Start;
                }
            });
        },
        WizardStep::DpiSetup => {
            ui.heading("Step 4: DPI Scaling");
            ui.label("Configure display scaling for MO2.");
            ui.add_space(5.0);

            ui.label(
                egui::RichText::new("Select a DPI value and test with sample applications to find the best setting.")
                    .size(12.0)
                    .color(egui::Color32::GRAY),
            );
            ui.add_space(15.0);

            // Current DPI display
            let current_label = DPI_PRESETS.iter()
                .find(|(v, _)| *v == wizard.selected_dpi)
                .map(|(_, l)| format!("{} ({})", l, wizard.selected_dpi))
                .unwrap_or_else(|| format!("Custom ({})", wizard.selected_dpi));
            ui.label(format!("Current: {}", current_label));
            ui.add_space(10.0);

            // DPI Preset buttons
            ui.label(egui::RichText::new("Presets:").strong());
            ui.add_space(5.0);
            ui.horizontal(|ui| {
                for (dpi_value, label) in DPI_PRESETS {
                    let is_selected = wizard.selected_dpi == *dpi_value;
                    let btn_text = format!("{} ({})", label, dpi_value);

                    let button = egui::Button::new(&btn_text)
                        .fill(if is_selected {
                            egui::Color32::from_rgb(60, 100, 60)
                        } else {
                            egui::Color32::from_gray(45)
                        });

                    if ui.add_sized([100.0, 35.0], button).clicked() {
                        wizard.custom_dpi_input = dpi_value.to_string();
                        *action_ref = WizardAction::ApplyDpi(*dpi_value);
                    }
                }
            });

            ui.add_space(10.0);

            // Custom DPI input
            ui.horizontal(|ui| {
                ui.label("Custom DPI:");
                let response = ui.add(
                    egui::TextEdit::singleline(&mut wizard.custom_dpi_input)
                        .desired_width(80.0)
                        .hint_text("e.g. 110")
                );

                if ui.button("Apply").clicked() || (response.lost_focus() && ui.input(|i| i.key_pressed(egui::Key::Enter))) {
                    if let Ok(custom_dpi) = wizard.custom_dpi_input.trim().parse::<u32>() {
                        if (72..=480).contains(&custom_dpi) {
                            *action_ref = WizardAction::ApplyDpi(custom_dpi);
                        }
                    }
                }

                ui.label(
                    egui::RichText::new("(72-480)")
                        .size(11.0)
                        .color(egui::Color32::GRAY),
                );
            });

            ui.add_space(15.0);
            ui.separator();
            ui.add_space(10.0);

            // Test Applications
            ui.label(egui::RichText::new("Test Applications:").strong());
            ui.label(
                egui::RichText::new("Launch these to preview how your DPI setting looks.")
                    .size(11.0)
                    .color(egui::Color32::GRAY),
            );
            ui.add_space(5.0);

            ui.horizontal(|ui| {
                let test_apps = [
                    ("winecfg", "Wine Config"),
                    ("regedit", "Registry Editor"),
                    ("notepad", "Notepad"),
                    ("control", "Control Panel"),
                ];

                for (app_cmd, app_label) in test_apps {
                    if ui.button(app_label).clicked() {
                        *action_ref = WizardAction::LaunchTestApp(app_cmd.to_string());
                    }
                }
            });

            ui.add_space(10.0);
            ui.label(
                egui::RichText::new("Note: Changing DPI or confirming will close all test applications.")
                    .size(11.0)
                    .color(egui::Color32::from_rgb(255, 200, 100)),
            );

            ui.add_space(20.0);
            ui.separator();
            ui.add_space(10.0);

            // Confirm button
            ui.horizontal(|ui| {
                if ui.button("Skip (Use 96/100%)").clicked() {
                    wizard.selected_dpi = 96;
                    *action_ref = WizardAction::ConfirmDpi;
                }

                ui.add_space(20.0);

                let confirm_label = DPI_PRESETS.iter()
                    .find(|(v, _)| *v == wizard.selected_dpi)
                    .map(|(v, l)| format!("{} ({})", l, v))
                    .unwrap_or_else(|| format!("{}", wizard.selected_dpi));

                if ui.add(egui::Button::new(format!("Confirm DPI: {}", confirm_label))
                    .fill(egui::Color32::from_rgb(60, 100, 60)))
                    .clicked()
                {
                    *action_ref = WizardAction::ConfirmDpi;
                }
            });
        },
        WizardStep::Finished => {
            ui.vertical_centered(|ui| {
                ui.add_space(20.0);
                if let Some(error_msg) = &wizard.last_install_error {
                    ui.heading(egui::RichText::new("Installation Failed!").color(egui::Color32::RED));
                    ui.add_space(10.0);
                    ui.label(format!("Error: {}", error_msg));
                    ui.add_space(10.0);
                    ui.label(egui::RichText::new("Please check the logs for more details:").strong());
                    let logs_dir = std::env::current_dir().unwrap_or_else(|_| std::path::PathBuf::from("."));
                    ui.label(format!("{}/nak_*.log", logs_dir.display()));
                    ui.add_space(20.0);

                    ui.horizontal(|ui| {
                        if ui.button("Try Again").clicked() {
                            *action_ref = WizardAction::Reset;
                        }
                        ui.add_space(10.0);
                        if ui.button("Return to Dashboard").clicked() {
                            *action_ref = WizardAction::Reset;
                        }
                    });
                } else {
                    ui.heading(egui::RichText::new("Installation Successful!").color(egui::Color32::from_rgb(100, 255, 100)));
                    ui.add_space(15.0);

                    ui.label(format!("{} has been set up successfully.", manager_name));
                    ui.add_space(15.0);

                    // Steam status
                    // status is passed as a parameter to render_install_wizard
                    if status.contains("restarted") {
                        egui::Frame::none()
                            .fill(egui::Color32::from_rgb(40, 60, 40))
                            .rounding(egui::Rounding::same(6.0))
                            .inner_margin(12.0)
                            .show(ui, |ui| {
                                ui.label(egui::RichText::new("Steam has been restarted").strong().color(egui::Color32::from_rgb(100, 200, 100)));
                                ui.add_space(4.0);
                                ui.label("Your shortcut should now appear in your Steam library.");
                            });
                    } else if status.contains("manually") {
                        egui::Frame::none()
                            .fill(egui::Color32::from_rgb(60, 50, 40))
                            .rounding(egui::Rounding::same(6.0))
                            .inner_margin(12.0)
                            .show(ui, |ui| {
                                ui.label(egui::RichText::new("Please restart Steam").strong().color(egui::Color32::from_rgb(255, 200, 100)));
                                ui.add_space(8.0);
                                ui.label("Steam needs to be restarted for the shortcut to appear.");
                                ui.add_space(8.0);
                                ui.horizontal(|ui| {
                                    if ui.button("Restart Steam Now").clicked() {
                                        if let Err(e) = crate::steam::restart_steam() {
                                            crate::logging::log_error(&format!("Failed to restart Steam: {}", e));
                                        }
                                    }
                                });
                            });
                    }

                    ui.add_space(15.0);

                    // How to launch
                    ui.label(egui::RichText::new("How to Launch").strong().size(14.0));
                    ui.add_space(4.0);
                    ui.label(format!("Find '{}' in your Steam library under Non-Steam Games.", wizard.name));
                    ui.add_space(6.0);
                    ui.colored_label(
                        egui::Color32::from_rgb(150, 200, 255),
                        "Click Play in Steam to launch MO2.",
                    );

                    ui.add_space(15.0);

                    // Installation location
                    ui.label(egui::RichText::new("Installation Location").strong());
                    ui.add_space(4.0);
                    ui.label(egui::RichText::new(format!("{}:  {}", manager_name, &wizard.path)).monospace().size(11.0));

                    ui.add_space(15.0);

                    // Steam Deck tip
                    ui.label(egui::RichText::new("Steam Deck / Game Mode").strong());
                    ui.add_space(4.0);
                    ui.label("The shortcut will automatically appear in Game Mode!");
                    ui.label("You can also add it to your favorites for quick access.");

                    ui.add_space(20.0);

                    if ui.button("Return to Menu").clicked() {
                        *action_ref = WizardAction::Reset;
                    }
                }
            });
        }
    }
        
    action
}

fn validate_path(wizard: &mut InstallWizard) {
    let path = std::path::Path::new(&wizard.path);
    wizard.validation_error = None; // clear first
    wizard.low_disk_space = false;
    wizard.available_disk_gb = 0.0;

    if !path.exists() {
        // If "New" or "Linked", non-existent is fine (we create it). If "Existing", it must exist.
        if wizard.install_type == "Existing" {
            wizard.validation_error = Some("Path does not exist!".to_string());
            return;
        }
    }

    // Check disk space for new installations (not for "Existing" setups)
    if wizard.install_type != "Existing" {
        // Use parent directory if path doesn't exist yet
        let check_path = if path.exists() { path } else { path.parent().unwrap_or(path) };
        if let Some(available) = get_available_disk_space(check_path) {
            wizard.available_disk_gb = available;
            // For linked installs, we need less space (no deps)
            let required = if wizard.install_type == "Linked" { 1.0 } else { MIN_REQUIRED_DISK_SPACE_GB };
            if available < required {
                wizard.low_disk_space = true;
            }
        }
    }

    if wizard.install_type == "New" || wizard.install_type == "Linked" {
        if path.exists() {
            // Check emptiness
            if let Ok(read_dir) = std::fs::read_dir(path) {
                if read_dir.count() > 0 {
                    wizard.validation_error = Some("Warning: Directory is not empty!".to_string());
                }
            }
        }
    } else {
        // Existing
        // Check for Executable
        let exe_name = "ModOrganizer.exe";
        let has_exe = path.join(exe_name).exists();

        if !has_exe {
            wizard.validation_error = Some(format!("Could not find {} in selected folder.", exe_name));
        }
    }
}


fn start_installation(app: &mut MyApp) {
    let wizard = &mut app.install_wizard; // Mutably borrow wizard here

    // Clear previous error before starting new installation
    wizard.last_install_error = None;

    log_action(&format!("Starting {} {} for {}", wizard.install_type, wizard.manager_type, wizard.name));

    // Setup Variables
    let status_arc = app.install_status.clone();
    let busy_arc = app.is_installing_manager.clone();
    let logs_arc = app.logs.clone();
    let progress_arc = app.install_progress.clone();
    let cancel_arc = app.cancel_install.clone();
    let result_app_id_arc = app.install_result_app_id.clone();
    let result_prefix_path_arc = app.install_result_prefix_path.clone();

    // Clear previous result
    *result_app_id_arc.lock().unwrap() = None;
    *result_prefix_path_arc.lock().unwrap() = None;

    // Get the selected Steam Proton from the wizard
    let selected_proton_name = match &wizard.selected_proton {
        Some(name) => name.clone(),
        None => {
            wizard.last_install_error = Some("No Proton version selected".to_string());
            return;
        }
    };
    let steam_proton = app.steam_protons.iter().find(|p| p.config_name == selected_proton_name).cloned();
    if steam_proton.is_none() {
        wizard.last_install_error = Some("Selected Proton not found".to_string());
        return;
    }
    let steam_proton = steam_proton.unwrap();

    // Clone data needed for the thread before moving
    let instance_name = wizard.name.clone();
    let install_path = std::path::PathBuf::from(&wizard.path);
    let manager_type = wizard.manager_type.clone();
    let install_type = wizard.install_type.clone();
    let skip_disk_check = wizard.disk_space_override;
    let proton_config_name = selected_proton_name.clone();
    
    // We can't update a field in `app.install_wizard` directly from the thread.
    // The thread can only update `Arc<Mutex<String>>` for status/logs/progress.
    // We use `app.install_status` to signal error, and then `render_install_wizard`
    // checks for the "Error: " prefix and sets `last_install_error` in the main thread.

    *busy_arc.lock().unwrap() = true;
    *status_arc.lock().unwrap() = format!("Preparing to install {}...", manager_type);
    *progress_arc.lock().unwrap() = 0.0;
    cancel_arc.store(false, Ordering::Relaxed);

    thread::spawn(move || {
        let cb_status = status_arc.clone();
        let cb_logs = logs_arc.clone();
        let cb_prog = progress_arc.clone();

        struct BusyGuard(std::sync::Arc<std::sync::Mutex<bool>>);
        impl Drop for BusyGuard {
            fn drop(&mut self) {
                *self.0.lock().unwrap() = false;
            }
        }
        let _guard = BusyGuard(busy_arc.clone());

        let ctx = TaskContext::new(
            move |msg| *cb_status.lock().unwrap() = msg,
            move |msg| cb_logs.lock().unwrap().push(msg),
            move |p| *cb_prog.lock().unwrap() = p,
            cancel_arc,
        );

        // Run the installation and capture the result
        let install_result: Result<(u32, std::path::PathBuf), String> = match (manager_type.as_str(), install_type.as_str()) {
            ("MO2", "New") => install_mo2(&instance_name, install_path, &steam_proton, ctx, skip_disk_check)
                .map(|r| (r.app_id, r.prefix_path))
                .map_err(|e| e.to_string()),
            ("MO2", "Existing") => setup_existing_mo2(&instance_name, install_path, &steam_proton, ctx)
                .map(|r| (r.app_id, r.prefix_path))
                .map_err(|e| e.to_string()),
            _ => Err("Unknown installation type".to_string()),
        };

        match install_result {
            Ok((app_id, prefix_path)) => {
                // Store the result for DPI setup
                *result_app_id_arc.lock().unwrap() = Some(app_id);
                *result_prefix_path_arc.lock().unwrap() = Some(prefix_path);

                // Apply the selected Proton version via Steam's config
                *status_arc.lock().unwrap() = "Applying Proton compatibility settings...".to_string();
                if let Err(e) = crate::steam::set_compat_tool(app_id, &proton_config_name) {
                    crate::logging::log_warning(&format!("Failed to set Proton compat tool: {}", e));
                } else {
                    crate::logging::log_info(&format!("Set Proton '{}' for AppID {}", proton_config_name, app_id));
                }

                // Auto-restart Steam so the shortcut appears
                *status_arc.lock().unwrap() = "Restarting Steam...".to_string();
                match crate::steam::restart_steam() {
                    Ok(_) => {
                        *status_arc.lock().unwrap() = "Installation Complete! Steam has been restarted.".to_string();
                    }
                    Err(e) => {
                        crate::logging::log_warning(&format!("Failed to restart Steam automatically: {}", e));
                        *status_arc.lock().unwrap() = "Installation Complete! Please restart Steam manually.".to_string();
                    }
                }
            }
            Err(e) => {
                *status_arc.lock().unwrap() = format!("Error: {}", e);
            }
        }
    });
}

// =============================================================================
// DPI Setup Handlers
// =============================================================================

/// Get the prefix path for the current wizard installation
/// With Steam-native integration, this uses the stored path from installation
fn get_wizard_prefix_path(app: &MyApp) -> Option<std::path::PathBuf> {
    // Use the stored prefix path from the installation result
    if let Some(ref prefix_path) = app.install_wizard.installed_prefix_path {
        return Some(prefix_path.clone());
    }

    // Fallback: try to compute from primary Steam path + AppID
    if let Some(app_id) = app.install_wizard.installed_app_id {
        if let Some(steam_path) = crate::steam::find_steam_path() {
            return Some(steam_path.join("steamapps/compatdata").join(app_id.to_string()).join("pfx"));
        }
    }

    None
}

/// Handle applying a new DPI value
fn handle_apply_dpi(app: &mut MyApp, dpi_value: u32) {
    log_action(&format!("Applying DPI {} to prefix", dpi_value));

    // Get prefix path
    let prefix_path = match get_wizard_prefix_path(app) {
        Some(p) => p,
        None => {
            crate::logging::log_error("No prefix path available for DPI setting");
            return;
        }
    };

    // Get proton from wizard selection (not app.config.selected_proton)
    let proton = match app.install_wizard.selected_proton.as_ref() {
        Some(name) => app.steam_protons.iter().find(|p| &p.config_name == name).cloned(),
        None => None,
    };

    let proton = match proton {
        Some(p) => p,
        None => {
            crate::logging::log_error("No proton selected for DPI setting");
            return;
        }
    };

    // Kill any running test processes first
    kill_wineserver(&prefix_path, &proton);
    app.dpi_test_processes.lock().unwrap().clear();

    // Apply the DPI setting
    if let Err(e) = apply_dpi(&prefix_path, &proton, dpi_value) {
        crate::logging::log_error(&format!("Failed to apply DPI: {}", e));
    } else {
        app.install_wizard.selected_dpi = dpi_value;
        crate::logging::log_info(&format!("DPI set to {}", dpi_value));
    }
}

/// Handle launching a test application
fn handle_launch_test_app(app: &mut MyApp, app_name: &str) {
    log_action(&format!("Launching DPI test app: {}", app_name));

    // Get prefix path
    let prefix_path = match get_wizard_prefix_path(app) {
        Some(p) => p,
        None => {
            crate::logging::log_error("No prefix path available for test app");
            return;
        }
    };

    // Get proton from wizard selection (not app.config.selected_proton)
    let proton = match app.install_wizard.selected_proton.as_ref() {
        Some(name) => app.steam_protons.iter().find(|p| &p.config_name == name).cloned(),
        None => None,
    };

    let proton = match proton {
        Some(p) => p,
        None => {
            crate::logging::log_error("No proton selected for test app");
            return;
        }
    };

    // Launch the test app
    match launch_dpi_test_app(&prefix_path, &proton, app_name) {
        Ok(child) => {
            // Track the PID
            app.dpi_test_processes.lock().unwrap().push(child.id());
            crate::logging::log_info(&format!("Launched {} (PID: {})", app_name, child.id()));
        }
        Err(e) => {
            crate::logging::log_error(&format!("Failed to launch {}: {}", app_name, e));
        }
    }
}

/// Handle confirming DPI and moving to finished
fn handle_confirm_dpi(app: &mut MyApp) {
    log_action(&format!("Confirming DPI: {}", app.install_wizard.selected_dpi));

    // Get prefix path
    let prefix_path = match get_wizard_prefix_path(app) {
        Some(p) => p,
        None => {
            crate::logging::log_error("No prefix path available");
            app.install_wizard.step = WizardStep::Finished;
            return;
        }
    };

    // Get proton from wizard selection (not app.config.selected_proton)
    let proton = match app.install_wizard.selected_proton.as_ref() {
        Some(name) => app.steam_protons.iter().find(|p| &p.config_name == name).cloned(),
        None => None,
    };

    if let Some(proton) = proton {
        // Kill any running test processes
        kill_wineserver(&prefix_path, &proton);
        app.dpi_test_processes.lock().unwrap().clear();

        // Apply final DPI setting if not default
        if app.install_wizard.selected_dpi != 96 {
            if let Err(e) = apply_dpi(&prefix_path, &proton, app.install_wizard.selected_dpi) {
                crate::logging::log_error(&format!("Failed to apply final DPI: {}", e));
            }
        }
    }

    // Move to finished
    app.install_wizard.step = WizardStep::Finished;
    crate::logging::log_info("DPI setup complete");
}

// Helper to launch winetricks
