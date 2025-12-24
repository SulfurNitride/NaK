//! Mod Managers page UI

use eframe::egui;
use std::sync::atomic::Ordering;
use std::thread;

use crate::app::{InstallWizard, ModManagerView, MyApp, WizardStep};
use crate::installers::{
    install_mo2, install_vortex, setup_existing_mo2, setup_existing_vortex, TaskContext,
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
        ui.label("No NaK prefixes found.");
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
            });
        ui.add_space(8.0);
    }
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
        }
        WizardAction::Cancel => {
             app.cancel_install.store(true, Ordering::Relaxed);
             *app.install_status.lock().unwrap() = "Cancelling...".to_string();
        }
        WizardAction::None => {}
    }
}

enum WizardAction {
    None,
    Start,
    Reset,
    Cancel,
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

    // Simple hack: If status contains "Complete!" and !is_busy, verify we are not already at Finished.
    // Check for error after installation finishes
    if !is_busy && status.starts_with("Error:") {
        wizard.last_install_error = Some(status.to_string());
        wizard.step = WizardStep::Finished; // Transition to finished state even on error
    } else if !is_busy && status.contains("Complete!") && wizard.step != WizardStep::Finished && wizard.step != WizardStep::Selection {
        wizard.last_install_error = None; // Clear any previous errors on success
        wizard.step = WizardStep::Finished;
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
                    wizard.validation_error = None;
                    wizard.force_install = false;
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
                ui.text_edit_singleline(&mut wizard.path);
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
        WizardStep::Finished => {
            ui.vertical_centered(|ui| {
                ui.add_space(20.0);
                if let Some(error_msg) = &wizard.last_install_error {
                    ui.heading(egui::RichText::new("Installation Failed!").color(egui::Color32::RED));
                    ui.add_space(10.0);
                    ui.label(format!("Error: {}", error_msg));
                    ui.add_space(10.0);
                    ui.label(egui::RichText::new("Please check the logs for more details:").strong());
                    ui.label(nak_path!("logs").to_string_lossy());
                } else {
                    ui.heading("Installation Successful!");
                    ui.add_space(10.0);
                    ui.label(format!("{} has been set up successfully.", manager_name));
                }
                ui.add_space(20.0);
                
                if ui.button("Return to Menu").clicked() {
                    *action_ref = WizardAction::Reset;
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
    let is_linked = manager_link.exists() || std::fs::symlink_metadata(&manager_link).is_ok();

    let path_str = prefix.path.to_string_lossy().to_string();
    let is_active = app.config.active_nxm_prefix.as_ref() == Some(&path_str);

    if is_active {
        ui.colored_label(egui::Color32::GREEN, "Active NXM");
    } else if ui
        .add_enabled(is_linked, egui::Button::new("Activate NXM"))
        .on_disabled_hover_text("Not a NaK-managed MO2/Vortex prefix")
        .clicked()
    {
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
                 
                 // Update "Launch [Manager]" symlink in the install directory
                 // path is .../pfx/../start.sh usually
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
                 }
             }
             Err(e) => crate::logging::log_error(&format!("Failed to regenerate script: {}", e)),
        }
    } else {
         crate::logging::log_error("No Proton version selected! Please select one in Proton Picker.");
    }
}
