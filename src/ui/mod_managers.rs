//! Mod Managers page UI

use eframe::egui;
use std::sync::atomic::Ordering;
use std::thread;

use crate::app::{InstallWizard, ModManagerView, MyApp, WizardStep};
use crate::config::AppConfig;
use crate::installers::{
    apply_dpi, apply_wine_registry_settings, install_mo2, install_vortex, kill_wineserver,
    launch_dpi_test_app, setup_existing_mo2, setup_existing_vortex, TaskContext, DPI_PRESETS,
};
use crate::logging::log_action;
use crate::nxm::NxmHandler;
use crate::scripts::ScriptGenerator;

pub fn render_mod_managers(app: &mut MyApp, ui: &mut egui::Ui) {
    let is_busy = *app.is_installing_manager.lock().unwrap();

    ui.heading("Mod Managers & Prefixes");
    ui.separator();
    ui.add_space(10.0);

    // Navigation / Breadcrumbs logic
    if app.mod_manager_view != ModManagerView::Dashboard {
        if ui.add_enabled(!is_busy, egui::Button::new("⬅ Back to Dashboard")).clicked() {
            app.mod_manager_view = ModManagerView::Dashboard;
            // Reset wizard state when leaving
            app.install_wizard = InstallWizard::default();
        }
        ui.add_space(10.0);
    }

    // Main Content
    egui::ScrollArea::vertical().show(ui, |ui| match app.mod_manager_view {
        ModManagerView::Dashboard => render_dashboard(app, ui),
        ModManagerView::PrefixManager => render_prefix_manager(app, ui),
        ModManagerView::Mo2Manager => render_manager_view(app, ui, "MO2"),
        ModManagerView::VortexManager => render_manager_view(app, ui, "Vortex"),
    });
}

fn render_dashboard(app: &mut MyApp, ui: &mut egui::Ui) {
    ui.label("Select a manager to configure:");
    ui.add_space(10.0);

    let button_size = egui::vec2(ui.available_width(), 80.0);

    if ui
        .add_sized(
            button_size,
            egui::Button::new(egui::RichText::new("🍷 Prefix Manager").heading()),
        )
        .clicked()
    {
        app.mod_manager_view = ModManagerView::PrefixManager;
    }
    ui.add_space(10.0);

    if ui
        .add_sized(
            button_size,
            egui::Button::new(egui::RichText::new("Mod Organizer 2").heading()),
        )
        .clicked()
    {
        app.mod_manager_view = ModManagerView::Mo2Manager;
        app.install_wizard.manager_type = "MO2".to_string();
        app.install_wizard.use_slr = app.config.use_steam_runtime;
    }
    ui.add_space(10.0);

    if ui
        .add_sized(
            button_size,
            egui::Button::new(egui::RichText::new("Vortex").heading()),
        )
        .clicked()
    {
        app.mod_manager_view = ModManagerView::VortexManager;
        app.install_wizard.manager_type = "Vortex".to_string();
        app.install_wizard.use_slr = app.config.use_steam_runtime;
    }
}

fn render_prefix_manager(app: &mut MyApp, ui: &mut egui::Ui) {
    ui.heading("Prefix Manager");
    ui.label("Manage your Wine prefixes directly.");
    ui.add_space(5.0);
    ui.horizontal(|ui| {
        if ui.button("Scan for New Prefixes").clicked() {
            app.detected_prefixes = app.prefix_manager.scan_prefixes();
        }
    });

    ui.add_space(10.0);

    // Clone prefixes to safely iterate while mutating app later
    let prefixes = app.detected_prefixes.clone();

    if prefixes.is_empty() {
        ui.add_space(10.0);
        egui::Frame::none()
            .fill(egui::Color32::from_rgb(40, 40, 50))
            .rounding(egui::Rounding::same(8.0))
            .inner_margin(15.0)
            .show(ui, |ui| {
                ui.label(egui::RichText::new("No prefixes detected!").size(16.0).strong());
                ui.add_space(8.0);
                ui.label("To get started, install MO2 or Vortex from the Mod Managers page.");
                ui.add_space(5.0);
                ui.label(
                    egui::RichText::new("You can have multiple MO2 instances and multiple Vortex instances.")
                        .color(egui::Color32::LIGHT_GRAY)
                        .size(12.0),
                );
                ui.add_space(10.0);
                ui.horizontal(|ui| {
                    if ui.button("Install MO2").clicked() {
                        app.mod_manager_view = crate::app::ModManagerView::Mo2Manager;
                        app.install_wizard.manager_type = "MO2".to_string();
                        app.install_wizard.use_slr = app.config.use_steam_runtime;
                    }
                    if ui.button("Install Vortex").clicked() {
                        app.mod_manager_view = crate::app::ModManagerView::VortexManager;
                        app.install_wizard.manager_type = "Vortex".to_string();
                        app.install_wizard.use_slr = app.config.use_steam_runtime;
                    }
                });
            });
    }

    for prefix in &prefixes {
        egui::Frame::group(ui.style())
            .rounding(egui::Rounding::same(6.0))
            .fill(egui::Color32::from_gray(32))
            .stroke(egui::Stroke::new(1.0, egui::Color32::from_gray(60)))
            .inner_margin(10.0)
            .show(ui, |ui| {
                // Header: Name + Orphan Status
                ui.horizontal(|ui| {
                    ui.heading(&prefix.name);
                    if prefix.is_orphaned {
                        ui.add_space(10.0);
                        ui.colored_label(egui::Color32::RED, "Orphaned");
                    }
                });

                // Path
                ui.label(egui::RichText::new(prefix.path.to_string_lossy()).color(egui::Color32::from_gray(180)).size(12.0));
                ui.add_space(5.0);

                // Actions
                ui.horizontal(|ui| {
                    let winetricks_ready = app.winetricks_path.lock().unwrap().is_some();

                    if ui.add_enabled(winetricks_ready, egui::Button::new("Winetricks")).clicked() {
                        launch_winetricks(app, prefix.path.clone());
                    }

                    if ui.button("Open Folder").clicked() {
                        let _ = std::process::Command::new("xdg-open")
                            .arg(&prefix.path)
                            .spawn();
                    }

                    render_nxm_toggle(app, ui, prefix);

                    // Regenerate Script Button
                    let prefix_base = prefix.path.parent().unwrap();
                    let manager_link = prefix_base.join("manager_link");
                    let is_managed = manager_link.exists() || std::fs::symlink_metadata(&manager_link).is_ok();

                    // Fix Game Registry button (for MO2 global instances)
                    let registry_fix_script = prefix_base.join("game_registry_fix.sh");
                    if registry_fix_script.exists()
                        && ui.button("Fix Registry").on_hover_text("Run game registry fix (for global instances)").clicked()
                    {
                        // Launch the registry fix script in a terminal
                        let script_path = registry_fix_script.to_string_lossy().to_string();
                        let _ = std::process::Command::new("sh")
                            .arg("-c")
                            .arg(format!(
                                "x-terminal-emulator -e '{}' || gnome-terminal -- '{}' || konsole -e '{}' || xterm -e '{}'",
                                script_path, script_path, script_path, script_path
                            ))
                            .spawn();
                    }

                    if is_managed && ui.button("Regenerate Scripts").clicked() {
                        // Resolve target to pass correct exe path
                        let target = std::fs::read_link(&manager_link).unwrap_or(manager_link.clone());
                        regenerate_script(app, prefix, &target);
                    }

                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        if ui.button("Delete").on_hover_text("Delete Prefix").clicked() {
                            app.pending_prefix_delete = Some(prefix.name.clone());
                        }
                    });
                });

                // SLR toggle row (below main actions)
                let prefix_base = prefix.path.parent().unwrap();
                let manager_link = prefix_base.join("manager_link");
                let is_managed = manager_link.exists() || std::fs::symlink_metadata(&manager_link).is_ok();

                if is_managed {
                    let script_path = prefix_base.join("start.sh");
                    let current_slr = ScriptGenerator::script_uses_slr(&script_path);

                    ui.horizontal(|ui| {
                        ui.label("SLR:");
                        match current_slr {
                            Some(true) => {
                                ui.colored_label(
                                    egui::Color32::from_rgb(100, 200, 100),
                                    "Enabled",
                                );
                                if ui.small_button("Disable SLR").on_hover_text("Regenerate scripts without Steam Linux Runtime").clicked() {
                                    let target = std::fs::read_link(&manager_link).unwrap_or(manager_link.clone());
                                    regenerate_script_with_slr(app, prefix, &target, false);
                                }
                            }
                            Some(false) => {
                                ui.colored_label(
                                    egui::Color32::from_rgb(255, 200, 100),
                                    "Disabled",
                                );
                                let slr_available = crate::wine::runtime::is_runtime_installed();
                                if ui.add_enabled(slr_available, egui::Button::new("Enable SLR").small())
                                    .on_hover_text(if slr_available {
                                        "Regenerate scripts with Steam Linux Runtime"
                                    } else {
                                        "SLR not installed - download in Proton Picker"
                                    })
                                    .clicked()
                                {
                                    let target = std::fs::read_link(&manager_link).unwrap_or(manager_link.clone());
                                    regenerate_script_with_slr(app, prefix, &target, true);
                                }
                            }
                            None => {
                                ui.colored_label(
                                    egui::Color32::GRAY,
                                    "Unknown",
                                );
                            }
                        }
                    });

                    // DPI Settings row
                    render_dpi_settings(app, ui, prefix);
                }
            });
        ui.add_space(8.0);
    }
}

/// Render DPI settings for a prefix in the prefix manager
fn render_dpi_settings(app: &mut MyApp, ui: &mut egui::Ui, prefix: &crate::wine::NakPrefix) {
    // Get proton for DPI operations
    let proton = match app.config.selected_proton.as_ref() {
        Some(name) => app.proton_versions.iter().find(|p| &p.name == name).cloned(),
        None => None,
    };

    // Clone prefix path for use in closures
    let prefix_path = prefix.path.clone();
    let prefix_name = prefix.name.clone();

    ui.horizontal(|ui| {
        ui.label("DPI:");

        if let Some(proton) = &proton {
            // Display preset buttons with percentage and value
            for (dpi_value, label) in DPI_PRESETS {
                let btn_text = format!("{} ({})", label, dpi_value);
                if ui.small_button(&btn_text).on_hover_text(format!("Set DPI to {}", dpi_value)).clicked() {
                    // Kill any running processes
                    kill_wineserver(&prefix_path, proton);

                    // Apply the new DPI
                    if let Err(e) = apply_dpi(&prefix_path, proton, *dpi_value) {
                        crate::logging::log_error(&format!("Failed to apply DPI {}: {}", dpi_value, e));
                    } else {
                        crate::logging::log_info(&format!("Set DPI to {} for {}", dpi_value, prefix_name));
                    }
                }
            }

            // Custom DPI input
            ui.add_space(10.0);
            ui.add(
                egui::TextEdit::singleline(&mut app.prefix_custom_dpi_input)
                    .desired_width(50.0)
                    .hint_text("DPI")
            );
            if ui.small_button("Set").on_hover_text("Apply custom DPI (72-480)").clicked() {
                if let Ok(custom_dpi) = app.prefix_custom_dpi_input.trim().parse::<u32>() {
                    if (72..=480).contains(&custom_dpi) {
                        kill_wineserver(&prefix_path, proton);
                        if let Err(e) = apply_dpi(&prefix_path, proton, custom_dpi) {
                            crate::logging::log_error(&format!("Failed to apply DPI {}: {}", custom_dpi, e));
                        } else {
                            crate::logging::log_info(&format!("Set DPI to {} for {}", custom_dpi, prefix_name));
                        }
                    }
                }
            }
        } else {
            ui.colored_label(egui::Color32::GRAY, "No Proton selected");
        }
    });
}

fn render_manager_view(app: &mut MyApp, ui: &mut egui::Ui, manager_name: &str) {
    ui.heading(format!("{} Manager", manager_name));
    ui.label(format!("Manage your {} installations.", manager_name));
    ui.add_space(10.0);

    let is_busy = *app.is_installing_manager.lock().unwrap();
    let status = app.install_status.lock().unwrap().clone();
    let progress = *app.install_progress.lock().unwrap();
    let proton_selected = app.config.selected_proton.is_some();

    // Render Wizard
    let action = render_install_wizard(
        &mut app.install_wizard,
        is_busy,
        &status,
        progress,
        proton_selected,
        manager_name,
        ui
    );

    match action {
        WizardAction::Start => start_installation(app),
        WizardAction::Reset => {
            // Reset wizard to start over
            app.install_wizard = InstallWizard::default();
            // Ensure we are back on the right manager page if reset changes things (it shouldn't here)
            app.install_wizard.manager_type = manager_name.to_string();
            // Initialize SLR toggle from config
            app.install_wizard.use_slr = app.config.use_steam_runtime;
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
    proton_selected: bool,
    manager_name: &str,
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
        } else if status.contains("Complete!") {
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

            ui.add_space(15.0);
            ui.separator();
            ui.add_space(10.0);

            // SLR toggle
            let slr_available = crate::wine::runtime::is_runtime_installed();
            ui.horizontal(|ui| {
                ui.label("Use Steam Linux Runtime (SLR):");
                if slr_available {
                    ui.checkbox(&mut wizard.use_slr, "");
                    if wizard.use_slr {
                        ui.colored_label(egui::Color32::from_rgb(100, 200, 100), "Enabled");
                    } else {
                        ui.colored_label(egui::Color32::from_rgb(255, 200, 100), "Disabled");
                    }
                } else {
                    wizard.use_slr = false;
                    ui.colored_label(egui::Color32::GRAY, "Not installed");
                    ui.label("(Download in Proton Picker)");
                }
            });
            ui.label(egui::RichText::new("SLR provides better compatibility but might cause unexpected issues.").small().weak());

            // Show warning if no Proton selected
            if !proton_selected {
                ui.add_space(5.0);
                ui.colored_label(
                    egui::Color32::from_rgb(255, 150, 100),
                    "⚠ Please select a Proton version in 'Proton Picker' first",
                );
            }

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
                
                if ui.add_enabled(can_proceed && proton_selected, egui::Button::new(if wizard.install_type == "New" { "Start Installation" } else { "Setup Instance" }))
                    .on_disabled_hover_text(if !proton_selected { "Please select a Proton version in 'Proton Picker' first."} else { "Please resolve the path issues." })
                    .clicked()
                {
                    *action_ref = WizardAction::Start;
                }
            });
        },
        WizardStep::DpiSetup => {
            ui.heading("Step 3: DPI Scaling");
            ui.label("Configure display scaling for your mod manager.");
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
                    let config = AppConfig::load();
                    ui.label(config.get_data_path().join("logs").to_string_lossy().to_string());
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

                    // Build paths
                    let prefix_name = format!(
                        "{}_{}",
                        wizard.manager_type.to_lowercase(),
                        wizard.name.to_lowercase().replace(' ', "_")
                    );
                    let config = AppConfig::load();
                    let prefix_path = config.get_prefixes_path().join(&prefix_name);
                    let script_path = prefix_path.join("start.sh");

                    // How to launch
                    ui.label(egui::RichText::new("How to Launch").strong().size(14.0));
                    ui.add_space(4.0);
                    ui.label("Double-click the shortcut in your mod manager folder:");
                    ui.label(egui::RichText::new(format!("{}/Launch {}", wizard.path, manager_name)).monospace().color(egui::Color32::from_rgb(150, 200, 255)));
                    ui.add_space(6.0);
                    ui.label("Or run the script directly:");
                    ui.label(egui::RichText::new(script_path.to_string_lossy().to_string()).monospace().size(11.0).color(egui::Color32::from_rgb(150, 200, 255)));
                    ui.add_space(6.0);
                    ui.colored_label(
                        egui::Color32::from_rgb(255, 200, 100),
                        "Do NOT launch the .exe directly - it won't work correctly!",
                    );

                    ui.add_space(15.0);

                    // Installation paths
                    ui.label(egui::RichText::new("Installation Paths").strong());
                    ui.add_space(4.0);
                    ui.label(egui::RichText::new(format!("Prefix:  {}", prefix_path.display())).monospace().size(11.0));
                    ui.label(egui::RichText::new(format!("{}:  {}", manager_name, &wizard.path)).monospace().size(11.0));

                    ui.add_space(15.0);

                    // Steam Deck tip
                    ui.label(egui::RichText::new("Steam Deck / Game Mode").strong());
                    ui.add_space(4.0);
                    ui.label("Add the script above to Steam as a non-Steam game");
                    ui.label("to launch your mod manager from Game Mode.");

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
    
    if !path.exists() {
        // If "New", non-existent is fine (we create it). If "Existing", it must exist.
        if wizard.install_type == "Existing" {
             wizard.validation_error = Some("Path does not exist!".to_string());
             return;
        }
    }

    if wizard.install_type == "New" {
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
        let exe_name = if wizard.manager_type == "MO2" { "ModOrganizer.exe" } else { "Vortex.exe" };
        let has_exe = path.join(exe_name).exists() || (wizard.manager_type == "Vortex" && path.join("Vortex").join(exe_name).exists());
        
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

    // Apply the wizard's SLR choice to the config (so script generation uses it)
    app.config.use_steam_runtime = wizard.use_slr;
    app.config.save();

    // Setup Variables
    let status_arc = app.install_status.clone();
    let busy_arc = app.is_installing_manager.clone();
    let logs_arc = app.logs.clone();
    let progress_arc = app.install_progress.clone();
    let cancel_arc = app.cancel_install.clone();

    let wt_path = app.winetricks_path.lock().unwrap().clone().unwrap();
    let selected_name = app.config.selected_proton.as_ref().unwrap().clone();
    let proton = app.proton_versions.iter().find(|p| p.name == selected_name).cloned();

    // Clone data needed for the thread before moving
    let instance_name = wizard.name.clone();
    let install_path = std::path::PathBuf::from(&wizard.path);
    let manager_type = wizard.manager_type.clone();
    let install_type = wizard.install_type.clone();
    
    // We can't update a field in `app.install_wizard` directly from the thread.
    // The thread can only update `Arc<Mutex<String>>` for status/logs/progress.
    // We use `app.install_status` to signal error, and then `render_install_wizard`
    // checks for the "Error: " prefix and sets `last_install_error` in the main thread.

    if let Some(proton_info) = proton {
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
                wt_path,
            );

            let result = match (manager_type.as_str(), install_type.as_str()) {
                ("MO2", "New") => install_mo2(&instance_name, install_path, &proton_info, ctx),
                ("MO2", "Existing") => setup_existing_mo2(&instance_name, install_path, &proton_info, ctx),
                ("Vortex", "New") => install_vortex(&instance_name, install_path, &proton_info, ctx),
                ("Vortex", "Existing") => setup_existing_vortex(&instance_name, install_path, &proton_info, ctx),
                _ => Err("Unknown installation type".into()),
            };

            if let Err(e) = result {
                *status_arc.lock().unwrap() = format!("Error: {}", e);
                // Instead of setting wizard_error_clone, we'll let render_install_wizard react to status_arc
            } else {
                 *status_arc.lock().unwrap() = "Installation Complete!".to_string();
            }
        });
    }
}

// =============================================================================
// DPI Setup Handlers
// =============================================================================

/// Get the prefix path for the current wizard installation
fn get_wizard_prefix_path(app: &MyApp) -> Option<std::path::PathBuf> {
    let home = std::env::var("HOME").ok()?;
    let instance_name = &app.install_wizard.name;
    let manager_type = &app.install_wizard.manager_type;
    if instance_name.is_empty() {
        return None;
    }

    // Prefix name format: mo2_{name} or vortex_{name}
    let prefix_name = format!(
        "{}_{}",
        manager_type.to_lowercase(),
        instance_name.to_lowercase().replace(' ', "_")
    );

    Some(std::path::PathBuf::from(format!(
        "{}/NaK/Prefixes/{}/pfx",
        home, prefix_name
    )))
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

    // Get proton
    let proton = match app.config.selected_proton.as_ref() {
        Some(name) => app.proton_versions.iter().find(|p| &p.name == name).cloned(),
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

    // Get proton
    let proton = match app.config.selected_proton.as_ref() {
        Some(name) => app.proton_versions.iter().find(|p| &p.name == name).cloned(),
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

    // Get proton
    let proton = match app.config.selected_proton.as_ref() {
        Some(name) => app.proton_versions.iter().find(|p| &p.name == name).cloned(),
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
fn launch_winetricks(app: &MyApp, prefix_path: std::path::PathBuf) {
    let wt_path = app.winetricks_path.lock().unwrap().clone().unwrap();
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
        let mut cmd = std::process::Command::new(wt_path);
        cmd.arg("--gui").env("WINEPREFIX", prefix_path);

        if let Some(w) = wine_bin { cmd.env("WINE", w); }
        if let Some(ws) = wineserver_bin { cmd.env("WINESERVER", ws); }
        if let Some(p) = wine_path_env { cmd.env("PATH", p); }

        if let Err(e) = cmd.spawn() {
            eprintln!("Failed to launch winetricks: {}", e);
        }
    });
}

fn render_nxm_toggle(app: &mut MyApp, ui: &mut egui::Ui, prefix: &crate::wine::NakPrefix) {
    let prefix_base = prefix.path.parent().unwrap();
    let manager_link = prefix_base.join("manager_link");
    let nxm_script = prefix_base.join("nxm_handler.sh");

    // Only show NXM toggle if prefix has nxm_handler.sh (MO2 with nxmhandler.exe)
    let has_nxm = nxm_script.exists();
    let is_linked = manager_link.exists() || std::fs::symlink_metadata(&manager_link).is_ok();

    let path_str = prefix.path.to_string_lossy().to_string();
    let is_active = app.config.active_nxm_prefix.as_ref() == Some(&path_str);

    if !has_nxm {
        return; // No NXM handler for this prefix (Vortex or MO2 without nxmhandler.exe)
    }

    if is_active {
        ui.colored_label(egui::Color32::GREEN, "Active NXM");
    } else if ui
        .add_enabled(is_linked, egui::Button::new("Activate NXM"))
        .on_disabled_hover_text("Not a NaK-managed MO2/Vortex prefix")
        .clicked()
    {
        // Pass prefix_base to set_active_instance (it contains nxm_handler.sh)
        if let Err(e) = NxmHandler::set_active_instance(prefix_base) {
            eprintln!("Failed to set active instance: {}", e);
        } else {
            app.config.active_nxm_prefix = Some(path_str);
            app.config.save();
        }
    }
}

fn regenerate_script(app: &MyApp, prefix: &crate::wine::NakPrefix, exe_path: &std::path::Path) {
    let selected_name = app.config.selected_proton.clone().unwrap_or_default();
    let proton = app.proton_versions.iter().find(|p| p.name == selected_name);

    if let Some(proton_info) = proton {
        let mut final_exe_path = exe_path.to_path_buf();
        
        // If link points to a directory, look for known executables inside
        if final_exe_path.is_dir() {
            let try_mo2 = final_exe_path.join("ModOrganizer.exe");
            let try_vortex = final_exe_path.join("Vortex.exe");
            let try_vortex_sub = final_exe_path.join("Vortex").join("Vortex.exe"); // Standard Vortex path
            
            if try_mo2.exists() {
                final_exe_path = try_mo2;
            } else if try_vortex.exists() {
                final_exe_path = try_vortex;
            } else if try_vortex_sub.exists() {
                final_exe_path = try_vortex_sub;
            }
        }

        let exe_name = final_exe_path.file_name().unwrap_or_default().to_string_lossy().to_lowercase();
        let prefix_base = prefix.path.parent().unwrap(); // ~/NaK/Prefixes/Name

        // We output the script to the prefix base folder (where .start.sh usually lives)
        let output_dir = prefix_base;

        // 1. Generate Launch Script
        let result = if exe_name.contains("modorganizer") {
             ScriptGenerator::generate_mo2_launch_script(&prefix.path, &final_exe_path, &proton_info.path, prefix_base, output_dir)
        } else if exe_name.contains("vortex") {
             ScriptGenerator::generate_vortex_launch_script(&prefix.path, &final_exe_path, &proton_info.path, prefix_base, output_dir)
        } else {
             Err("Unknown manager executable. Link must point to ModOrganizer.exe or Vortex.exe".into())
        };

        match result {
             Ok(path) => {
                 crate::logging::log_info(&format!("Regenerated start.sh for {} at {:?}", prefix.name, path));
                 
                 // 2. Generate Kill Script
                 if let Err(e) = ScriptGenerator::generate_kill_prefix_script(&prefix.path, &proton_info.path, output_dir) {
                     crate::logging::log_error(&format!("Failed to regenerate kill script: {}", e));
                 } else {
                     crate::logging::log_info("Regenerated kill script.");
                 }

                 // 3. Generate Registry Fix Script
                 // Use prefix name as instance name (e.g. mo2_skyrim)
                 if let Err(e) = ScriptGenerator::generate_fix_game_registry_script(&prefix.path, &proton_info.path, &prefix.name, output_dir) {
                     crate::logging::log_error(&format!("Failed to regenerate registry script: {}", e));
                 } else {
                     crate::logging::log_info("Regenerated registry fix script.");
                 }

                 // 4. Generate NXM Handler Script (for both MO2 and Vortex)
                 let nxm_result = if exe_name.contains("modorganizer") {
                     ScriptGenerator::generate_mo2_nxm_script(&prefix.path, &final_exe_path, &proton_info.path, output_dir)
                 } else {
                     ScriptGenerator::generate_vortex_nxm_script(&prefix.path, &final_exe_path, &proton_info.path, output_dir)
                 };
                 match &nxm_result {
                     Ok(_) => crate::logging::log_info("Regenerated NXM handler script."),
                     Err(e) => crate::logging::log_error(&format!("Failed to regenerate NXM script: {}", e)),
                 }

                 // 5. Re-apply Wine Registry Settings (includes HIGHDPIAWARE fix)
                 if let Err(e) = apply_wine_registry_settings(&prefix.path, proton_info, &|msg| {
                     crate::logging::log_info(&msg);
                 }) {
                     crate::logging::log_error(&format!("Failed to apply Wine registry settings: {}", e));
                 } else {
                     crate::logging::log_info("Applied Wine registry settings (HIGHDPIAWARE, DLL overrides, etc.)");
                 }

                 // Update "Launch [Manager]" and "Handle NXM" symlinks in the install directory
                 if let Some(install_dir) = final_exe_path.parent() {
                     let link_name = if exe_name.contains("modorganizer") { "Launch MO2" } else { "Launch Vortex" };
                     let link_path = install_dir.join(link_name);

                     if link_path.exists() || std::fs::symlink_metadata(&link_path).is_ok() {
                         let _ = std::fs::remove_file(&link_path);
                     }
                     if let Err(e) = std::os::unix::fs::symlink(&path, &link_path) {
                         crate::logging::log_error(&format!("Failed to update Launch symlink: {}", e));
                     } else {
                         crate::logging::log_info("Updated Launch symlink.");
                     }

                     // Update Handle NXM symlink
                     if let Ok(nxm_script) = nxm_result {
                         let nxm_link = install_dir.join("Handle NXM");
                         if nxm_link.exists() || std::fs::symlink_metadata(&nxm_link).is_ok() {
                             let _ = std::fs::remove_file(&nxm_link);
                         }
                         if let Err(e) = std::os::unix::fs::symlink(&nxm_script, &nxm_link) {
                             crate::logging::log_error(&format!("Failed to update Handle NXM symlink: {}", e));
                         } else {
                             crate::logging::log_info("Updated Handle NXM symlink.");
                         }
                     }
                 }
             }
             Err(e) => crate::logging::log_error(&format!("Failed to regenerate script: {}", e)),
        }
    } else {
         crate::logging::log_error("No Proton version selected! Please select one in Proton Picker.");
    }
}

/// Regenerate scripts with explicit SLR setting (for per-prefix SLR toggle)
fn regenerate_script_with_slr(app: &MyApp, prefix: &crate::wine::NakPrefix, exe_path: &std::path::Path, use_slr: bool) {
    let selected_name = app.config.selected_proton.clone().unwrap_or_default();
    let proton = app.proton_versions.iter().find(|p| p.name == selected_name);

    if let Some(proton_info) = proton {
        let mut final_exe_path = exe_path.to_path_buf();

        // If link points to a directory, look for known executables inside
        if final_exe_path.is_dir() {
            let try_mo2 = final_exe_path.join("ModOrganizer.exe");
            let try_vortex = final_exe_path.join("Vortex.exe");
            let try_vortex_sub = final_exe_path.join("Vortex").join("Vortex.exe");

            if try_mo2.exists() {
                final_exe_path = try_mo2;
            } else if try_vortex.exists() {
                final_exe_path = try_vortex;
            } else if try_vortex_sub.exists() {
                final_exe_path = try_vortex_sub;
            }
        }

        let exe_name = final_exe_path.file_name().unwrap_or_default().to_string_lossy().to_lowercase();
        let prefix_base = prefix.path.parent().unwrap();
        let output_dir = prefix_base;

        // Generate Launch Script with explicit SLR setting
        let result = if exe_name.contains("modorganizer") {
            ScriptGenerator::generate_mo2_launch_script_with_slr(
                &prefix.path, &final_exe_path, &proton_info.path, prefix_base, output_dir, use_slr
            )
        } else if exe_name.contains("vortex") {
            ScriptGenerator::generate_vortex_launch_script_with_slr(
                &prefix.path, &final_exe_path, &proton_info.path, prefix_base, output_dir, use_slr
            )
        } else {
            Err("Unknown manager executable".into())
        };

        match result {
            Ok(path) => {
                let mode = if use_slr { "SLR enabled" } else { "SLR disabled" };
                crate::logging::log_info(&format!("Regenerated start.sh for {} ({}) at {:?}", prefix.name, mode, path));

                // Also regenerate kill and registry scripts
                let _ = ScriptGenerator::generate_kill_prefix_script(&prefix.path, &proton_info.path, output_dir);
                let _ = ScriptGenerator::generate_fix_game_registry_script(&prefix.path, &proton_info.path, &prefix.name, output_dir);

                // Generate NXM Handler Script
                let nxm_result = if exe_name.contains("modorganizer") {
                    ScriptGenerator::generate_mo2_nxm_script(&prefix.path, &final_exe_path, &proton_info.path, output_dir)
                } else {
                    ScriptGenerator::generate_vortex_nxm_script(&prefix.path, &final_exe_path, &proton_info.path, output_dir)
                };
                if let Err(e) = &nxm_result {
                    crate::logging::log_error(&format!("Failed to regenerate NXM script: {}", e));
                }

                // Re-apply Wine Registry Settings (includes HIGHDPIAWARE fix)
                if let Err(e) = apply_wine_registry_settings(&prefix.path, proton_info, &|msg| {
                    crate::logging::log_info(&msg);
                }) {
                    crate::logging::log_error(&format!("Failed to apply Wine registry settings: {}", e));
                }

                // Update symlinks in install directory
                if let Some(install_dir) = final_exe_path.parent() {
                    let link_name = if exe_name.contains("modorganizer") { "Launch MO2" } else { "Launch Vortex" };
                    let link_path = install_dir.join(link_name);
                    if link_path.exists() || std::fs::symlink_metadata(&link_path).is_ok() {
                        let _ = std::fs::remove_file(&link_path);
                    }
                    let _ = std::os::unix::fs::symlink(&path, &link_path);

                    // Update Handle NXM symlink
                    if let Ok(nxm_script) = nxm_result {
                        let nxm_link = install_dir.join("Handle NXM");
                        if nxm_link.exists() || std::fs::symlink_metadata(&nxm_link).is_ok() {
                            let _ = std::fs::remove_file(&nxm_link);
                        }
                        let _ = std::os::unix::fs::symlink(&nxm_script, &nxm_link);
                    }
                }
            }
            Err(e) => crate::logging::log_error(&format!("Failed to regenerate script: {}", e)),
        }
    } else {
        crate::logging::log_error("No Proton version selected!");
    }
}
