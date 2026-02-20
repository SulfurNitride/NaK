//! Slint UI Bridge - Connects Rust application state to Slint UI

use std::path::PathBuf;
use parking_lot::Mutex;
use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::thread;
use std::time::Duration;
use std::rc::Rc;
use std::cell::RefCell;

use slint::{ComponentHandle, ModelRc, SharedString, VecModel};

use crate::app::{InstallWizard, MyApp, Page, WizardStep};
use nak_rust::config::ManagedPrefixes;
use nak_rust::installers::{
    apply_dpi, get_available_disk_space, install_mo2, kill_wineserver,
    launch_dpi_test_app, setup_existing_mo2, TaskContext, MIN_REQUIRED_DISK_SPACE_GB,
};
use nak_rust::logging::{log_action, log_error, log_info, log_warning};
use nak_rust::steam::{get_steam_accounts, ShortcutsVdf};

// Include the generated Slint code
slint::include_modules!();

/// Convert Rust Page enum to Slint PageType enum
fn page_to_slint(page: Page) -> PageType {
    match page {
        Page::FirstRunSetup => PageType::FirstRunSetup,
        Page::GettingStarted => PageType::GettingStarted,
        Page::ModManagers => PageType::MO2,
        Page::Marketplace => PageType::Marketplace,
        Page::Settings => PageType::Settings,
        Page::Updater => PageType::Version,
    }
}

/// Convert Slint PageType to Rust Page enum
fn slint_to_page(page: PageType) -> Page {
    match page {
        PageType::FirstRunSetup => Page::FirstRunSetup,
        PageType::GettingStarted => Page::GettingStarted,
        PageType::MO2 => Page::ModManagers,
        PageType::Marketplace => Page::Marketplace,
        PageType::Settings => Page::Settings,
        PageType::Version => Page::Updater,
    }
}

/// Convert WizardStep to integer for Slint
fn wizard_step_to_int(step: WizardStep) -> i32 {
    match step {
        WizardStep::Selection => 0,
        WizardStep::NameInput => 1,
        WizardStep::PathInput => 2,
        WizardStep::ProtonSelect => 3,
        WizardStep::DpiSetup => 4,
        WizardStep::Finished => 5,
    }
}

/// Build prefix info for Slint
fn build_prefix_info(app: &MyApp) -> ModelRc<PrefixInfo> {
    let managed = ManagedPrefixes::load();
    let active_app_ids = get_active_shortcut_app_ids();

    let prefixes: Vec<PrefixInfo> = managed.prefixes.iter().map(|prefix| {
        let is_active = active_app_ids.contains(&prefix.app_id);
        let prefix_exists = std::path::Path::new(&prefix.prefix_path).exists();
        let proton_name = prefix.proton_config_name.as_deref()
            .and_then(|name| app.steam_protons.iter().find(|p| p.config_name == name))
            .map(|p| p.name.clone())
            .unwrap_or_else(|| "Unknown".to_string());

        PrefixInfo {
            name: prefix.name.clone().into(),
            app_id: prefix.app_id.to_string().into(),
            prefix_path: prefix.prefix_path.clone().into(),
            manager_type: format!("{}", prefix.manager_type).into(),
            is_active,
            prefix_exists,
            proton_name: proton_name.into(),
        }
    }).collect();

    ModelRc::new(VecModel::from(prefixes))
}

/// Get all AppIDs currently in Steam's shortcuts.vdf
fn get_active_shortcut_app_ids() -> std::collections::HashSet<u32> {
    let mut app_ids = std::collections::HashSet::new();

    if let Some(steam_path) = nak_rust::steam::find_steam_path() {
        let userdata_path = std::path::Path::new(&steam_path).join("userdata");
        if let Ok(entries) = std::fs::read_dir(&userdata_path) {
            for entry in entries.flatten() {
                if let Some(name) = entry.path().file_name() {
                    if name.to_string_lossy() == "0" {
                        continue;
                    }
                }
                let shortcuts_path = entry.path().join("config/shortcuts.vdf");
                if shortcuts_path.exists() {
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

/// Run the Slint UI with the application state
pub fn run_slint_ui(app: Rc<RefCell<MyApp>>) -> Result<(), slint::PlatformError> {
    let window = MainWindow::new()?;

    // Get initial state from app
    {
        let app_ref = app.borrow();

        // Set initial page and app version
        window.set_current_page(page_to_slint(app_ref.current_page));
        window.set_app_version(env!("CARGO_PKG_VERSION").into());
        window.set_current_version(env!("CARGO_PKG_VERSION").into());

        // Steam detection
        window.set_steam_detected(app_ref.steam_detected);
        if let Some(ref path) = app_ref.steam_path {
            window.set_steam_path(path.clone().into());
        }

        // Steam accounts
        let accounts = get_steam_accounts();
        let account_names: Vec<SharedString> = accounts.iter()
            .map(|a| SharedString::from(a.persona_name.clone()))
            .collect();
        window.set_steam_accounts(ModelRc::new(VecModel::from(account_names)));

        // Proton options
        let proton_names: Vec<SharedString> = app_ref.steam_protons.iter()
            .map(|p| SharedString::from(p.name.clone()))
            .collect();
        window.set_proton_options(ModelRc::new(VecModel::from(proton_names)));

        // Missing deps
        let missing = app_ref.missing_deps.lock();
        let missing_strings: Vec<SharedString> = missing.iter()
            .map(|s| SharedString::from(s.clone()))
            .collect();
        window.set_missing_deps(ModelRc::new(VecModel::from(missing_strings)));

        // Migration popup
        window.set_show_migration_popup(app_ref.show_steam_migration_popup);
        window.set_legacy_path(app_ref.config.get_data_path().to_string_lossy().to_string().into());

        // Prefixes
        window.set_prefixes(build_prefix_info(&app_ref));
    }

    // Setup navigation callback
    {
        let app_weak = Rc::downgrade(&app);
        let window_weak = window.as_weak();
        window.on_navigate(move |page| {
            if let Some(app_rc) = app_weak.upgrade() {
                let mut app_ref = app_rc.borrow_mut();
                let rust_page = slint_to_page(page);
                log_action(&format!("Navigate to {:?}", rust_page));

                // Handle first run completion
                if app_ref.current_page == Page::FirstRunSetup && rust_page == Page::GettingStarted {
                    app_ref.config.first_run_completed = true;
                    app_ref.config.save();
                }

                app_ref.current_page = rust_page;

                if let Some(window) = window_weak.upgrade() {
                    window.set_current_page(page);
                }
            }
        });
    }

    // Account selection callback
    {
        let app_weak = Rc::downgrade(&app);
        window.on_account_selected(move |idx| {
            if let Some(app_rc) = app_weak.upgrade() {
                let mut app_ref = app_rc.borrow_mut();
                let accounts = get_steam_accounts();
                if let Some(account) = accounts.get(idx as usize) {
                    app_ref.config.selected_steam_account = account.account_id.clone();
                    app_ref.config.save();
                    log_action(&format!("Selected Steam account: {}", account.persona_name));
                }
            }
        });
    }

    // MO2 Wizard callbacks
    setup_mo2_callbacks(&window, &app);

    // Getting Started callbacks
    setup_getting_started_callbacks(&window);

    // Marketplace callbacks
    setup_marketplace_callbacks(&window, &app);

    // Settings/Prefix callbacks
    setup_settings_callbacks(&window, &app);

    // Version/Updater callbacks
    setup_version_callbacks(&window, &app);

    // Migration popup callbacks
    setup_migration_callbacks(&window, &app);

    // Browse custom Steam path callback
    {
        let app_weak = Rc::downgrade(&app);
        let window_weak = window.as_weak();
        window.on_browse_steam_path(move || {
            log_action("Browse Steam path clicked");
            if let Some(path) = rfd::FileDialog::new().pick_folder() {
                if nak_rust::steam::is_valid_steam_path(&path) {
                    if let Some(app_rc) = app_weak.upgrade() {
                        let mut app_ref = app_rc.borrow_mut();
                        app_ref.config.custom_steam_path = path.to_string_lossy().to_string();
                        app_ref.config.save();
                        log_info(&format!("Custom Steam path set to: {}", path.display()));

                        // Re-detect Steam with the new custom path
                        let steam_path = nak_rust::steam::detect_steam_path_checked();
                        let steam_detected = steam_path.is_some();
                        app_ref.steam_detected = steam_detected;
                        app_ref.steam_path = steam_path;
                        app_ref.steam_protons = nak_rust::steam::find_steam_protons();

                        if let Some(window) = window_weak.upgrade() {
                            window.set_steam_detected(steam_detected);
                            if let Some(ref p) = app_ref.steam_path {
                                window.set_steam_path(p.clone().into());
                            }
                            let proton_names: Vec<SharedString> = app_ref.steam_protons.iter()
                                .map(|p| SharedString::from(p.name.clone()))
                                .collect();
                            window.set_proton_options(ModelRc::new(VecModel::from(proton_names)));
                        }
                    }
                } else {
                    log_warning(&format!(
                        "Selected path is not a valid Steam installation (no steamapps/ subdirectory): {}",
                        path.display()
                    ));
                }
            }
        });
    }

    // Setup polling timer for state synchronization (100ms)
    let app_poll = Rc::clone(&app);
    let window_weak = window.as_weak();
    let timer = slint::Timer::default();
    timer.start(slint::TimerMode::Repeated, Duration::from_millis(100), move || {
        if let Some(window) = window_weak.upgrade() {
            // First pass: read installation state
            let (is_installing, status, progress, current_step);
            {
                let app_ref = app_poll.borrow();
                is_installing = *app_ref.is_installing_manager.lock();
                status = app_ref.install_status.lock().clone();
                progress = *app_ref.install_progress.lock();
                current_step = app_ref.install_wizard.step;
            }

            // Sync installation state to UI
            window.set_is_installing(is_installing);
            window.set_install_status(status.clone().into());
            window.set_install_progress(progress);
            window.set_wizard_step(wizard_step_to_int(current_step));

            // Check for install completion state changes (needs mutable access)
            if !is_installing {
                if let Ok(mut app_mut) = app_poll.try_borrow_mut() {
                    if status.contains("Cancelled") {
                        app_mut.install_wizard.step = WizardStep::Selection;
                        window.set_wizard_step(0);
                    } else if status.starts_with("Error:") {
                        window.set_last_error(status.clone().into());
                        app_mut.install_wizard.step = WizardStep::Finished;
                        window.set_wizard_step(5);
                    } else if (status.contains("Dependencies installed") || status.contains("Complete!") || status.contains("Installed!") || status.contains("Setup Complete!"))
                        && app_mut.install_wizard.step == WizardStep::ProtonSelect {
                        // Sync install results to wizard before moving to DPI setup
                        let app_id_result = *app_mut.install_result_app_id.lock();
                        let prefix_path_result = app_mut.install_result_prefix_path.lock().clone();
                        app_mut.install_wizard.installed_app_id = app_id_result;
                        app_mut.install_wizard.installed_prefix_path = prefix_path_result;
                        // Move to DPI setup
                        app_mut.install_wizard.step = WizardStep::DpiSetup;
                        window.set_wizard_step(4);
                    }
                }
            }

            // Second pass: read update state
            {
                let app_ref = app_poll.borrow();

                let update_info = app_ref.update_info.lock().clone();
                if let Some(ref info) = update_info {
                    window.set_update_available(info.is_update_available);
                    window.set_latest_version(info.latest_version.clone().into());
                    window.set_release_notes(info.release_notes.clone().into());
                }

                window.set_is_checking_update(*app_ref.is_checking_update.lock());
                window.set_is_installing_update(*app_ref.is_installing_update.lock());
                window.set_update_installed(*app_ref.update_installed.lock());

                let err_opt = app_ref.update_error.lock().clone();
                if let Some(ref err) = err_opt {
                    window.set_update_error(err.clone().into());
                }
            }

            // Third pass: marketplace async results
            // Take all results with a single short-lived borrow, then process
            let (registry_result, detail_result, install_result) = {
                let app_ref = app_poll.borrow();
                let reg = app_ref.marketplace_async.registry_result.lock().take();
                let det = app_ref.marketplace_async.detail_result.lock().take();
                let inst = app_ref.marketplace_async.install_result.lock().take();
                (reg, det, inst)
            };

            if let Some(result) = registry_result {
                match result {
                    Ok(registry) => {
                        let names: Vec<SharedString> = registry.plugins.iter()
                            .map(|p| SharedString::from(p.name.clone()))
                            .collect();
                        let descs: Vec<SharedString> = registry.plugins.iter()
                            .map(|p| SharedString::from(p.description.clone()))
                            .collect();

                        window.set_plugin_names(ModelRc::new(VecModel::from(names)));
                        window.set_plugin_descriptions(ModelRc::new(VecModel::from(descs)));
                        window.set_marketplace_loading(false);
                        window.set_marketplace_error("".into());

                        // Reset detail properties when registry refreshes
                        window.set_selected_plugin_index(-1);
                        window.set_plugin_detail_author("".into());
                        window.set_plugin_detail_version("".into());
                        window.set_plugin_detail_compatible(false);

                        if let Ok(mut app_mut) = app_poll.try_borrow_mut() {
                            if app_mut.marketplace_state.is_none() {
                                app_mut.marketplace_state = Some(MarketplaceState::default());
                            }
                            if let Some(ref mut state) = app_mut.marketplace_state {
                                state.registry = Some(registry);
                                state.manifests.clear();
                            }
                        }
                    }
                    Err(e) => {
                        log_error(&format!("Failed to fetch marketplace: {}", e));
                        window.set_marketplace_error(e.into());
                        window.set_marketplace_loading(false);
                    }
                }
            }

            if let Some((idx, result)) = detail_result {
                match result {
                    Ok(manifest) => {
                        let compatible = nak_rust::marketplace::check_version_compatible(
                            &manifest.plugin.min_nak_version,
                        );
                        window.set_selected_plugin_index(idx as i32);
                        window.set_plugin_detail_author(manifest.plugin.author.clone().into());
                        window.set_plugin_detail_version(manifest.plugin.min_nak_version.clone().into());
                        window.set_plugin_detail_compatible(compatible);
                        window.set_marketplace_loading(false);

                        if let Ok(mut app_mut) = app_poll.try_borrow_mut() {
                            if app_mut.marketplace_state.is_none() {
                                app_mut.marketplace_state = Some(MarketplaceState::default());
                            }
                            if let Some(ref mut state) = app_mut.marketplace_state {
                                state.manifests.insert(idx, manifest);
                            }
                        }
                    }
                    Err(e) => {
                        log_error(&format!("Failed to fetch plugin details: {}", e));
                        window.set_marketplace_error(e.into());
                        window.set_marketplace_loading(false);
                    }
                }
            }

            if let Some(result) = install_result {
                match result {
                    Ok(msg) => {
                        log_info(&msg);
                    }
                    Err(e) => {
                        log_error(&format!("Plugin installation failed: {}", e));
                    }
                }
            }
        }
    });

    window.run()
}

fn setup_mo2_callbacks(window: &MainWindow, app: &Rc<RefCell<MyApp>>) {
    // Select New installation
    {
        let app_weak = Rc::downgrade(app);
        let window_weak = window.as_weak();
        window.on_mo2_select_new(move || {
            if let Some(app_rc) = app_weak.upgrade() {
                let mut app_ref = app_rc.borrow_mut();
                log_action("MO2: Selected New installation");
                app_ref.install_wizard.manager_type = "MO2".to_string();
                app_ref.install_wizard.install_type = "New".to_string();
                app_ref.install_wizard.step = WizardStep::NameInput;

                if let Some(window) = window_weak.upgrade() {
                    window.set_install_type("New".into());
                    window.set_wizard_step(1);
                }
            }
        });
    }

    // Select Existing installation
    {
        let app_weak = Rc::downgrade(app);
        let window_weak = window.as_weak();
        window.on_mo2_select_existing(move || {
            if let Some(app_rc) = app_weak.upgrade() {
                let mut app_ref = app_rc.borrow_mut();
                log_action("MO2: Selected Existing installation");
                app_ref.install_wizard.manager_type = "MO2".to_string();
                app_ref.install_wizard.install_type = "Existing".to_string();
                app_ref.install_wizard.step = WizardStep::NameInput;

                if let Some(window) = window_weak.upgrade() {
                    window.set_install_type("Existing".into());
                    window.set_wizard_step(1);
                }
            }
        });
    }

    // Go back
    {
        let app_weak = Rc::downgrade(app);
        let window_weak = window.as_weak();
        window.on_mo2_go_back(move || {
            if let Some(app_rc) = app_weak.upgrade() {
                let mut app_ref = app_rc.borrow_mut();
                let current = app_ref.install_wizard.step;
                let new_step = match current {
                    WizardStep::NameInput => WizardStep::Selection,
                    WizardStep::PathInput => WizardStep::NameInput,
                    WizardStep::ProtonSelect => WizardStep::PathInput,
                    _ => current,
                };
                log_action(&format!("MO2: Go back from {:?} to {:?}", current, new_step));
                app_ref.install_wizard.step = new_step;

                if let Some(window) = window_weak.upgrade() {
                    window.set_wizard_step(wizard_step_to_int(new_step));
                }
            }
        });
    }

    // Go next
    {
        let app_weak = Rc::downgrade(app);
        let window_weak = window.as_weak();
        window.on_mo2_go_next(move || {
            if let Some(app_rc) = app_weak.upgrade() {
                let mut app_ref = app_rc.borrow_mut();

                if let Some(window) = window_weak.upgrade() {
                    // Sync from UI
                    app_ref.install_wizard.name = window.get_instance_name().to_string();
                    app_ref.install_wizard.path = window.get_install_path().to_string();
                    app_ref.install_wizard.force_install = window.get_force_install();
                    app_ref.install_wizard.disk_space_override = window.get_disk_override();
                }

                let current = app_ref.install_wizard.step;
                let new_step = match current {
                    WizardStep::NameInput => {
                        // Validate name
                        if app_ref.install_wizard.name.trim().is_empty() {
                            return;
                        }
                        WizardStep::PathInput
                    }
                    WizardStep::PathInput => {
                        // Validate path
                        validate_path(&mut app_ref.install_wizard);
                        if let Some(ref err) = app_ref.install_wizard.validation_error {
                            if !err.contains("not empty") || !app_ref.install_wizard.force_install {
                                if let Some(window) = window_weak.upgrade() {
                                    window.set_validation_error(err.clone().into());
                                }
                                return;
                            }
                        }
                        if app_ref.install_wizard.low_disk_space && !app_ref.install_wizard.disk_space_override {
                            return;
                        }
                        WizardStep::ProtonSelect
                    }
                    _ => current,
                };

                log_action(&format!("MO2: Go next from {:?} to {:?}", current, new_step));
                app_ref.install_wizard.step = new_step;

                if let Some(window) = window_weak.upgrade() {
                    window.set_wizard_step(wizard_step_to_int(new_step));
                    window.set_validation_error(
                        app_ref.install_wizard.validation_error.clone().unwrap_or_default().into()
                    );
                    window.set_low_disk_space(app_ref.install_wizard.low_disk_space);
                    window.set_available_disk_gb(app_ref.install_wizard.available_disk_gb as f32);
                }
            }
        });
    }

    // Browse path
    {
        let app_weak = Rc::downgrade(app);
        let window_weak = window.as_weak();
        window.on_mo2_browse_path(move || {
            log_action("MO2: Browse path clicked");
            if let Some(path) = rfd::FileDialog::new().pick_folder() {
                if let Some(app_rc) = app_weak.upgrade() {
                    let mut app_ref = app_rc.borrow_mut();
                    app_ref.install_wizard.path = path.to_string_lossy().to_string();
                    validate_path(&mut app_ref.install_wizard);

                    if let Some(window) = window_weak.upgrade() {
                        window.set_install_path(app_ref.install_wizard.path.clone().into());
                        window.set_validation_error(
                            app_ref.install_wizard.validation_error.clone().unwrap_or_default().into()
                        );
                        window.set_low_disk_space(app_ref.install_wizard.low_disk_space);
                        window.set_available_disk_gb(app_ref.install_wizard.available_disk_gb as f32);
                    }
                }
            }
        });
    }

    // Start installation
    {
        let app_weak = Rc::downgrade(app);
        let window_weak = window.as_weak();
        window.on_mo2_start_install(move || {
            if let Some(app_rc) = app_weak.upgrade() {
                // Sync UI state before starting
                if let Some(window) = window_weak.upgrade() {
                    let mut app_ref = app_rc.borrow_mut();
                    app_ref.install_wizard.name = window.get_instance_name().to_string();
                    app_ref.install_wizard.path = window.get_install_path().to_string();

                    if let Ok(proton_idx) = usize::try_from(window.get_selected_proton_index()) {
                        if proton_idx < app_ref.steam_protons.len() {
                            app_ref.install_wizard.selected_proton = Some(app_ref.steam_protons[proton_idx].config_name.clone());
                        }
                    }
                }

                start_installation(app_rc);
            }
        });
    }

    // Cancel installation
    {
        let app_weak = Rc::downgrade(app);
        window.on_mo2_cancel_install(move || {
            if let Some(app_rc) = app_weak.upgrade() {
                let app_ref = app_rc.borrow();
                log_action("MO2: Cancel installation");
                app_ref.cancel_install.store(true, Ordering::Relaxed);
                *app_ref.install_status.lock() = "Cancelling...".to_string();
            }
        });
    }

    // Reset wizard
    {
        let app_weak = Rc::downgrade(app);
        let window_weak = window.as_weak();
        window.on_mo2_reset_wizard(move || {
            if let Some(app_rc) = app_weak.upgrade() {
                let mut app_ref = app_rc.borrow_mut();
                log_action("MO2: Reset wizard");

                app_ref.install_wizard = InstallWizard::default();
                app_ref.install_wizard.manager_type = "MO2".to_string();
                *app_ref.install_status.lock() = String::new();
                *app_ref.install_progress.lock() = 0.0;
                app_ref.logs.lock().clear();
                app_ref.dpi_test_processes.lock().clear();
                app_ref.cancel_install.store(false, Ordering::Relaxed);

                if let Some(window) = window_weak.upgrade() {
                    window.set_wizard_step(0);
                    window.set_instance_name("".into());
                    window.set_install_path("".into());
                    window.set_install_type("".into());
                    window.set_validation_error("".into());
                    window.set_last_error("".into());
                    window.set_force_install(false);
                    window.set_disk_override(false);
                    window.set_selected_dpi(96);
                }
            }
        });
    }

    // Apply DPI
    {
        let app_weak = Rc::downgrade(app);
        let window_weak = window.as_weak();
        window.on_mo2_apply_dpi(move |dpi| {
            if let Some(app_rc) = app_weak.upgrade() {
                let mut app_ref = app_rc.borrow_mut();
                log_action(&format!("MO2: Apply DPI {}", dpi));
                handle_apply_dpi(&mut app_ref, dpi as u32);

                if let Some(window) = window_weak.upgrade() {
                    window.set_selected_dpi(dpi);
                }
            }
        });
    }

    // Launch test app
    {
        let app_weak = Rc::downgrade(app);
        window.on_mo2_launch_test_app(move |app_name| {
            if let Some(app_rc) = app_weak.upgrade() {
                let mut app_ref = app_rc.borrow_mut();
                log_action(&format!("MO2: Launch test app {}", app_name));
                handle_launch_test_app(&mut app_ref, &app_name);
            }
        });
    }

    // Confirm DPI
    {
        let app_weak = Rc::downgrade(app);
        let window_weak = window.as_weak();
        window.on_mo2_confirm_dpi(move || {
            if let Some(app_rc) = app_weak.upgrade() {
                let mut app_ref = app_rc.borrow_mut();

                if let Some(window) = window_weak.upgrade() {
                    app_ref.install_wizard.selected_dpi = window.get_selected_dpi() as u32;
                }

                log_action(&format!("MO2: Confirm DPI {}", app_ref.install_wizard.selected_dpi));
                handle_confirm_dpi(&mut app_ref);

                if let Some(window) = window_weak.upgrade() {
                    window.set_wizard_step(5); // Finished
                }
            }
        });
    }

    // Skip DPI
    {
        let app_weak = Rc::downgrade(app);
        let window_weak = window.as_weak();
        window.on_mo2_skip_dpi(move || {
            if let Some(app_rc) = app_weak.upgrade() {
                let mut app_ref = app_rc.borrow_mut();
                log_action("MO2: Skip DPI (use default 96)");
                app_ref.install_wizard.selected_dpi = 96;
                handle_confirm_dpi(&mut app_ref);

                if let Some(window) = window_weak.upgrade() {
                    window.set_wizard_step(5); // Finished
                }
            }
        });
    }
}

fn setup_getting_started_callbacks(window: &MainWindow) {
    window.on_open_faq(|| {
        log_action("Open FAQ in browser");
        let _ = std::process::Command::new("xdg-open")
            .arg("https://github.com/SulfurNitride/NaK/blob/main/docs/FAQ.md")
            .spawn();
    });

    window.on_open_github(|| {
        log_action("Open GitHub Issues");
        let _ = std::process::Command::new("xdg-open")
            .arg("https://github.com/SulfurNitride/NaK/issues")
            .spawn();
    });

    window.on_open_discord(|| {
        log_action("Open Discord");
        let _ = std::process::Command::new("xdg-open")
            .arg("https://discord.gg/9JWQzSeUWt")
            .spawn();
    });

    window.on_open_kofi(|| {
        log_action("Open Ko-Fi");
        let _ = std::process::Command::new("xdg-open")
            .arg("https://ko-fi.com/sulfurnitride")
            .spawn();
    });
}

fn setup_marketplace_callbacks(window: &MainWindow, app: &Rc<RefCell<MyApp>>) {
    // Refresh marketplace
    {
        let app_weak = Rc::downgrade(app);
        let window_weak = window.as_weak();
        window.on_marketplace_refresh(move || {
            log_action("Marketplace: Refresh");
            if let Some(window) = window_weak.upgrade() {
                window.set_marketplace_loading(true);
                window.set_marketplace_error("".into());
            }

            if let Some(app_rc) = app_weak.upgrade() {
                let app_ref = app_rc.borrow();
                let result_arc = app_ref.marketplace_async.registry_result.clone();
                *result_arc.lock() = None;

                thread::spawn(move || {
                    let result = nak_rust::marketplace::fetch_registry()
                        .map_err(|e| e.to_string());
                    *result_arc.lock() = Some(result);
                });
            }
        });
    }

    // Load plugin details
    {
        let app_weak = Rc::downgrade(app);
        let window_weak = window.as_weak();
        window.on_marketplace_load_details(move |idx| {
            log_action(&format!("Marketplace: Load details for plugin {}", idx));

            if let Some(app_rc) = app_weak.upgrade() {
                let app_ref = app_rc.borrow();

                // Get the folder name from the registry
                let folder = app_ref.marketplace_state.as_ref()
                    .and_then(|s| s.registry.as_ref())
                    .and_then(|r| r.plugins.get(idx as usize))
                    .map(|p| p.folder.clone());

                if let Some(folder) = folder {
                    let result_arc = app_ref.marketplace_async.detail_result.clone();
                    *result_arc.lock() = None;

                    if let Some(window) = window_weak.upgrade() {
                        window.set_marketplace_loading(true);
                    }

                    let plugin_idx = idx as usize;
                    thread::spawn(move || {
                        let result = nak_rust::marketplace::fetch_plugin_manifest(&folder)
                            .map_err(|e| e.to_string());
                        *result_arc.lock() = Some((plugin_idx, result));
                    });
                }
            }
        });
    }

    // Install plugin
    {
        let app_weak = Rc::downgrade(app);
        let window_weak = window.as_weak();
        window.on_marketplace_install(move |idx| {
            log_action(&format!("Marketplace: Install plugin {}", idx));

            if let Some(app_rc) = app_weak.upgrade() {
                start_plugin_installation(app_rc, idx as usize, &window_weak);
            }
        });
    }
}

fn setup_settings_callbacks(window: &MainWindow, app: &Rc<RefCell<MyApp>>) {
    // Open folder
    {
        window.on_prefix_open_folder(move |idx| {
            log_action(&format!("Settings: Open folder for prefix {}", idx));
            let managed = ManagedPrefixes::load();
            if let Some(prefix) = managed.prefixes.get(idx as usize) {
                let _ = std::process::Command::new("xdg-open")
                    .arg(&prefix.prefix_path)
                    .spawn();
            }
        });
    }

    // Update scripts
    {
        let app_weak = Rc::downgrade(app);
        let window_weak = window.as_weak();
        window.on_prefix_update_scripts(move |idx| {
            log_action(&format!("Settings: Update scripts for prefix {}", idx));
            let managed = ManagedPrefixes::load();
            if let Some(prefix) = managed.prefixes.get(idx as usize) {
                if let Some(app_rc) = app_weak.upgrade() {
                    let app_ref = app_rc.borrow();

                    let proton = prefix.proton_config_name.as_deref()
                        .and_then(|name| app_ref.steam_protons.iter().find(|p| p.config_name == name))
                        .or_else(|| app_ref.steam_protons.first());

                    if let Some(proton) = proton {
                        let install_path = std::path::Path::new(&prefix.install_path);
                        let prefix_path = std::path::Path::new(&prefix.prefix_path);

                        match nak_rust::installers::regenerate_nak_tools_scripts(
                            prefix.manager_type,
                            install_path,
                            prefix_path,
                            prefix.app_id,
                            &proton.path,
                        ) {
                            Ok(_) => {
                                log_info(&format!("Updated scripts for {} using {}", prefix.name, proton.name));
                                ManagedPrefixes::update_proton(prefix.app_id, &proton.config_name);
                            }
                            Err(e) => {
                                log_error(&format!("Failed to update scripts: {}", e));
                            }
                        }
                    }
                }
            }

            // Refresh prefixes
            if let Some(app_rc) = app_weak.upgrade() {
                if let Some(window) = window_weak.upgrade() {
                    window.set_prefixes(build_prefix_info(&app_rc.borrow()));
                }
            }
        });
    }

    // Delete prefix (now just sets confirm-delete-index in Slint, actual deletion via confirm)
    // The on_prefix_delete callback is no longer used for actual deletion — Slint handles it.

    // Confirm delete prefix (actual deletion)
    {
        let app_weak = Rc::downgrade(app);
        let window_weak = window.as_weak();
        window.on_prefix_confirm_delete(move |idx| {
            log_action(&format!("Settings: Confirmed delete prefix {}", idx));
            let managed = ManagedPrefixes::load();
            if let Some(prefix) = managed.prefixes.get(idx as usize) {
                match ManagedPrefixes::delete_prefix(prefix.app_id) {
                    Ok(_) => log_info(&format!("Deleted prefix with AppID: {}", prefix.app_id)),
                    Err(e) => log_error(&format!("Failed to delete prefix: {}", e)),
                }
            }

            // Refresh prefixes
            if let Some(app_rc) = app_weak.upgrade() {
                if let Some(window) = window_weak.upgrade() {
                    window.set_prefixes(build_prefix_info(&app_rc.borrow()));
                }
            }
        });
    }

    // Cancel delete prefix
    {
        window.on_prefix_cancel_delete(|| {
            log_action("Settings: Cancelled prefix deletion");
        });
    }

    // Remove entry
    {
        let app_weak = Rc::downgrade(app);
        let window_weak = window.as_weak();
        window.on_prefix_remove_entry(move |idx| {
            log_action(&format!("Settings: Remove entry for prefix {}", idx));
            let managed = ManagedPrefixes::load();
            if let Some(prefix) = managed.prefixes.get(idx as usize) {
                ManagedPrefixes::unregister(prefix.app_id);
            }

            // Refresh prefixes
            if let Some(app_rc) = app_weak.upgrade() {
                if let Some(window) = window_weak.upgrade() {
                    window.set_prefixes(build_prefix_info(&app_rc.borrow()));
                }
            }
        });
    }

    // Change proton
    {
        window.on_prefix_change_proton(move |_prefix_idx, _proton_idx| {
            log_action(&format!("Settings: Change proton for prefix {} to proton {}", _prefix_idx, _proton_idx));
            // Simplified - would update proton config
        });
    }
}

fn setup_version_callbacks(window: &MainWindow, app: &Rc<RefCell<MyApp>>) {
    // Check for updates
    {
        let app_weak = Rc::downgrade(app);
        window.on_check_for_updates(move || {
            log_action("Version: Check for updates");

            if let Some(app_rc) = app_weak.upgrade() {
                let app_ref = app_rc.borrow();

                *app_ref.is_checking_update.lock() = true;
                *app_ref.update_error.lock() = None;

                let is_checking = app_ref.is_checking_update.clone();
                let update_info = app_ref.update_info.clone();
                let update_error = app_ref.update_error.clone();

                thread::spawn(move || {
                    match nak_rust::updater::check_for_updates() {
                        Ok(info) => {
                            *update_info.lock() = Some(info);
                        }
                        Err(e) => {
                            *update_error.lock() = Some(e.to_string());
                        }
                    }
                    *is_checking.lock() = false;
                });
            }
        });
    }

    // Install update
    {
        let app_weak = Rc::downgrade(app);
        window.on_install_update(move || {
            log_action("Version: Install update");

            if let Some(app_rc) = app_weak.upgrade() {
                let app_ref = app_rc.borrow();

                let url = app_ref.update_info.lock()
                    .as_ref()
                    .and_then(|i| i.download_url.clone());

                if let Some(url) = url {
                    *app_ref.is_installing_update.lock() = true;
                    *app_ref.update_error.lock() = None;

                    let is_installing = app_ref.is_installing_update.clone();
                    let update_error = app_ref.update_error.clone();
                    let update_installed = app_ref.update_installed.clone();

                    thread::spawn(move || {
                        match nak_rust::updater::install_update(&url) {
                            Ok(_) => {
                                *update_installed.lock() = true;
                            }
                            Err(e) => {
                                *update_error.lock() = Some(e.to_string());
                            }
                        }
                        *is_installing.lock() = false;
                    });
                }
            }
        });
    }

    // Restart app
    {
        window.on_restart_app(|| {
            log_action("Version: Restart app");
            if let Ok(exe) = std::env::current_exe() {
                match std::process::Command::new(&exe).spawn() {
                    Ok(_) => std::process::exit(0),
                    Err(e) => {
                        log_error(&format!("Failed to restart: {}", e));
                        // Attempt to restore from backup
                        if let Some(dir) = exe.parent() {
                            let backup = dir.join(".nak_backup");
                            if backup.exists() {
                                log_warning("Attempting to restore from backup...");
                                if std::fs::rename(&backup, &exe).is_ok()
                                    && std::process::Command::new(&exe).spawn().is_ok() {
                                    std::process::exit(0);
                                }
                                log_error("Failed to restore from backup");
                            }
                        }
                    }
                }
            }
        });
    }

    // Open releases
    {
        window.on_open_releases(|| {
            log_action("Version: Open releases");
            let _ = std::process::Command::new("xdg-open")
                .arg("https://github.com/SulfurNitride/NaK/releases")
                .spawn();
        });
    }

    // Set can_self_update
    window.set_can_self_update(nak_rust::updater::can_self_update());
}

fn setup_migration_callbacks(window: &MainWindow, app: &Rc<RefCell<MyApp>>) {
    // Open folder
    {
        let app_weak = Rc::downgrade(app);
        window.on_migration_open_folder(move || {
            if let Some(app_rc) = app_weak.upgrade() {
                let app_ref = app_rc.borrow();
                let folder = app_ref.config.get_data_path();
                let _ = std::process::Command::new("xdg-open")
                    .arg(&folder)
                    .spawn();
            }
        });
    }

    // Delete data
    {
        let app_weak = Rc::downgrade(app);
        let window_weak = window.as_weak();
        window.on_migration_delete_data(move || {
            if let Some(app_rc) = app_weak.upgrade() {
                let mut app_ref = app_rc.borrow_mut();
                let folder = app_ref.config.get_data_path();

                if let Err(e) = std::fs::remove_dir_all(&folder) {
                    log_error(&format!("Failed to delete {}: {}", folder.display(), e));
                } else {
                    log_info(&format!("Deleted old NaK folder: {}", folder.display()));
                }

                app_ref.show_steam_migration_popup = false;
                app_ref.config.steam_migration_shown = true;
                app_ref.config.save();

                if let Some(window) = window_weak.upgrade() {
                    window.set_show_migration_popup(false);
                }
            }
        });
    }

    // Dismiss
    {
        let app_weak = Rc::downgrade(app);
        let window_weak = window.as_weak();
        window.on_migration_dismiss(move || {
            if let Some(app_rc) = app_weak.upgrade() {
                let mut app_ref = app_rc.borrow_mut();
                app_ref.show_steam_migration_popup = false;
                app_ref.config.steam_migration_shown = true;
                app_ref.config.save();

                if let Some(window) = window_weak.upgrade() {
                    window.set_show_migration_popup(false);
                }
            }
        });
    }
}

// ============================================================================
// Installation Logic (moved from mod_managers.rs)
// ============================================================================

fn validate_path(wizard: &mut InstallWizard) {
    let path = std::path::Path::new(&wizard.path);
    wizard.validation_error = None;
    wizard.low_disk_space = false;
    wizard.available_disk_gb = 0.0;

    if !path.exists()
        && wizard.install_type == "Existing" {
        wizard.validation_error = Some("Path does not exist!".to_string());
        return;
    }

    // Check disk space for new installations
    if wizard.install_type != "Existing" {
        let check_path = if path.exists() { path } else { path.parent().unwrap_or(path) };
        if let Some(available) = get_available_disk_space(check_path) {
            wizard.available_disk_gb = available;
            let required = if wizard.install_type == "Linked" { 1.0 } else { MIN_REQUIRED_DISK_SPACE_GB };
            if available < required {
                wizard.low_disk_space = true;
            }
        }
    }

    if wizard.install_type == "New" || wizard.install_type == "Linked" {
        if path.exists() {
            if let Ok(read_dir) = std::fs::read_dir(path) {
                if read_dir.count() > 0 {
                    wizard.validation_error = Some("Warning: Directory is not empty!".to_string());
                }
            }
        }
    } else {
        // Existing
        let exe_name = "ModOrganizer.exe";
        let has_exe = path.join(exe_name).exists();
        if !has_exe {
            wizard.validation_error = Some(format!("Could not find {} in selected folder.", exe_name));
        }
    }
}

fn start_installation(app: Rc<RefCell<MyApp>>) {
    // Clone Arc fields first, before borrowing wizard mutably
    let (status_arc, busy_arc, logs_arc, progress_arc, cancel_arc, result_app_id_arc, result_prefix_path_arc);
    let (instance_name, install_path, manager_type, install_type, skip_disk_check, selected_proton_name, steam_proton);
    let plugin_manifest;

    {
        let app_ref = app.borrow();
        status_arc = app_ref.install_status.clone();
        busy_arc = app_ref.is_installing_manager.clone();
        logs_arc = app_ref.logs.clone();
        progress_arc = app_ref.install_progress.clone();
        cancel_arc = app_ref.cancel_install.clone();
        result_app_id_arc = app_ref.install_result_app_id.clone();
        result_prefix_path_arc = app_ref.install_result_prefix_path.clone();

        // Get wizard data
        let wizard = &app_ref.install_wizard;
        instance_name = wizard.name.clone();
        install_path = PathBuf::from(&wizard.path);
        manager_type = wizard.manager_type.clone();
        install_type = wizard.install_type.clone();
        skip_disk_check = wizard.disk_space_override;
        plugin_manifest = wizard.plugin_manifest.clone();

        selected_proton_name = match &wizard.selected_proton {
            Some(name) => name.clone(),
            None => {
                drop(app_ref);
                app.borrow_mut().install_wizard.last_install_error = Some("No Proton version selected".to_string());
                return;
            }
        };

        steam_proton = app_ref.steam_protons.iter()
            .find(|p| p.config_name == selected_proton_name)
            .cloned();
    }

    if steam_proton.is_none() {
        app.borrow_mut().install_wizard.last_install_error = Some("Selected Proton not found".to_string());
        return;
    }
    let steam_proton = steam_proton.unwrap();

    // Now update state
    {
        let mut app_ref = app.borrow_mut();
        app_ref.install_wizard.last_install_error = None;
    }

    log_action(&format!("Starting {} {} for {}", install_type, manager_type, instance_name));

    *result_app_id_arc.lock() = None;
    *result_prefix_path_arc.lock() = None;

    let proton_config_name = selected_proton_name.clone();

    *busy_arc.lock() = true;
    *status_arc.lock() = format!("Preparing to install {}...", manager_type);
    *progress_arc.lock() = 0.0;
    cancel_arc.store(false, Ordering::Relaxed);

    thread::spawn(move || {
        let cb_status = status_arc.clone();
        let cb_logs = logs_arc.clone();
        let cb_prog = progress_arc.clone();

        struct BusyGuard(Arc<Mutex<bool>>);
        impl Drop for BusyGuard {
            fn drop(&mut self) {
                *self.0.lock() = false;
            }
        }
        let _guard = BusyGuard(busy_arc.clone());

        let ctx = TaskContext::new(
            move |msg| *cb_status.lock() = msg,
            move |msg| cb_logs.lock().push(msg),
            move |p| *cb_prog.lock() = p,
            cancel_arc,
        );

        let install_result: Result<(u32, PathBuf), String> = match (manager_type.as_str(), install_type.as_str()) {
            ("MO2", "New") => install_mo2(&instance_name, install_path, &steam_proton, ctx, skip_disk_check)
                .map(|r| (r.app_id, r.prefix_path))
                .map_err(|e| e.to_string()),
            ("MO2", "Existing") => setup_existing_mo2(&instance_name, install_path, &steam_proton, ctx)
                .map(|r| (r.app_id, r.prefix_path))
                .map_err(|e| e.to_string()),
            ("Plugin", _) => {
                match plugin_manifest {
                    Some(ref manifest) => {
                        nak_rust::installers::install_plugin(
                            manifest,
                            &instance_name,
                            install_path.clone(),
                            &steam_proton,
                            ctx,
                            skip_disk_check,
                        )
                        .map(|r| {
                            // Plugin installer doesn't return prefix_path, derive it
                            let prefix_path = nak_rust::steam::find_steam_path()
                                .map(|sp| sp.join("steamapps/compatdata").join(r.app_id.to_string()).join("pfx"))
                                .unwrap_or_default();
                            (r.app_id, prefix_path)
                        })
                        .map_err(|e| e.to_string())
                    }
                    None => Err("No plugin manifest available".to_string()),
                }
            }
            _ => Err("Unknown installation type".to_string()),
        };

        match install_result {
            Ok((app_id, prefix_path)) => {
                *result_app_id_arc.lock() = Some(app_id);
                *result_prefix_path_arc.lock() = Some(prefix_path);

                *status_arc.lock() = "Applying Proton compatibility settings...".to_string();
                if let Err(e) = nak_rust::steam::set_compat_tool(app_id, &proton_config_name) {
                    log_warning(&format!("Failed to set Proton compat tool: {}", e));
                } else {
                    log_info(&format!("Set Proton '{}' for AppID {}", proton_config_name, app_id));
                }

                *status_arc.lock() = "Restarting Steam...".to_string();
                match nak_rust::steam::restart_steam() {
                    Ok(_) => {
                        *status_arc.lock() = "Dependencies installed. Configuring DPI...".to_string();
                    }
                    Err(e) => {
                        log_warning(&format!("Failed to restart Steam automatically: {}", e));
                        *status_arc.lock() = "Dependencies installed. Please restart Steam manually after setup.".to_string();
                    }
                }
            }
            Err(e) => {
                // Cleanup is handled inside install_mo2/setup_existing_mo2 themselves
                if e.contains("Cancelled") {
                    *status_arc.lock() = "Cancelled — installation cleaned up.".to_string();
                } else {
                    *status_arc.lock() = format!("Error: {}", e);
                }
            }
        }
    });
}

fn get_wizard_prefix_path(app: &MyApp) -> Option<PathBuf> {
    if let Some(ref prefix_path) = app.install_wizard.installed_prefix_path {
        return Some(prefix_path.clone());
    }

    if let Some(app_id) = app.install_wizard.installed_app_id {
        if let Some(steam_path) = nak_rust::steam::find_steam_path() {
            return Some(steam_path.join("steamapps/compatdata").join(app_id.to_string()).join("pfx"));
        }
    }

    None
}

fn handle_apply_dpi(app: &mut MyApp, dpi_value: u32) {
    log_action(&format!("Applying DPI {} to prefix", dpi_value));

    let prefix_path = match get_wizard_prefix_path(app) {
        Some(p) => p,
        None => {
            log_error("No prefix path available for DPI setting");
            return;
        }
    };

    let proton = match app.install_wizard.selected_proton.as_ref() {
        Some(name) => app.steam_protons.iter().find(|p| &p.config_name == name).cloned(),
        None => None,
    };

    let proton = match proton {
        Some(p) => p,
        None => {
            log_error("No proton selected for DPI setting");
            return;
        }
    };

    kill_wineserver(&prefix_path, &proton);
    app.dpi_test_processes.lock().clear();

    if let Err(e) = apply_dpi(&prefix_path, &proton, dpi_value) {
        log_error(&format!("Failed to apply DPI: {}", e));
    } else {
        app.install_wizard.selected_dpi = dpi_value;
        log_info(&format!("DPI set to {}", dpi_value));
    }
}

fn handle_launch_test_app(app: &mut MyApp, app_name: &str) {
    log_action(&format!("Launching DPI test app: {}", app_name));

    let prefix_path = match get_wizard_prefix_path(app) {
        Some(p) => p,
        None => {
            log_error("No prefix path available for test app");
            return;
        }
    };

    let proton = match app.install_wizard.selected_proton.as_ref() {
        Some(name) => app.steam_protons.iter().find(|p| &p.config_name == name).cloned(),
        None => None,
    };

    let proton = match proton {
        Some(p) => p,
        None => {
            log_error("No proton selected for test app");
            return;
        }
    };

    match launch_dpi_test_app(&prefix_path, &proton, app_name) {
        Ok(child) => {
            app.dpi_test_processes.lock().push(child.id());
            log_info(&format!("Launched {} (PID: {})", app_name, child.id()));
        }
        Err(e) => {
            log_error(&format!("Failed to launch {}: {}", app_name, e));
        }
    }
}

fn handle_confirm_dpi(app: &mut MyApp) {
    log_action(&format!("Confirming DPI: {}", app.install_wizard.selected_dpi));

    let prefix_path = match get_wizard_prefix_path(app) {
        Some(p) => p,
        None => {
            log_error("No prefix path available");
            app.install_wizard.step = WizardStep::Finished;
            return;
        }
    };

    let proton = match app.install_wizard.selected_proton.as_ref() {
        Some(name) => app.steam_protons.iter().find(|p| &p.config_name == name).cloned(),
        None => None,
    };

    if let Some(proton) = proton {
        kill_wineserver(&prefix_path, &proton);
        app.dpi_test_processes.lock().clear();

        if app.install_wizard.selected_dpi != 96 {
            if let Err(e) = apply_dpi(&prefix_path, &proton, app.install_wizard.selected_dpi) {
                log_error(&format!("Failed to apply final DPI: {}", e));
            }
        }
    }

    app.install_wizard.step = WizardStep::Finished;
    log_info("DPI setup complete");
}

// ============================================================================
// Plugin Installation
// ============================================================================

/// Set up the install wizard for a marketplace plugin, then navigate to the MO2 page
/// so the user can choose name, path, and proton before installation starts.
fn start_plugin_installation(app: Rc<RefCell<MyApp>>, plugin_idx: usize, window_weak: &slint::Weak<MainWindow>) {
    let plugin_name;
    {
        let mut app_ref = app.borrow_mut();

        // Get manifest from marketplace state
        let manifest = app_ref.marketplace_state.as_ref()
            .and_then(|s| s.manifests.get(&plugin_idx).cloned());
        let manifest = match manifest {
            Some(m) => m,
            None => {
                log_error("No manifest loaded for this plugin. Load details first.");
                return;
            }
        };

        plugin_name = manifest.plugin.name.clone();
        log_action(&format!("Plugin install wizard: {}", plugin_name));

        // Reset wizard and pre-populate for plugin install
        app_ref.install_wizard = InstallWizard::default();
        app_ref.install_wizard.manager_type = "Plugin".to_string();
        app_ref.install_wizard.install_type = "New".to_string();
        app_ref.install_wizard.name = plugin_name.clone();
        app_ref.install_wizard.plugin_manifest = Some(manifest);
        app_ref.install_wizard.step = WizardStep::NameInput;

        // Navigate to MO2 page (which hosts the install wizard)
        app_ref.current_page = crate::app::Page::ModManagers;

        // Clear previous install state
        *app_ref.install_status.lock() = String::new();
        *app_ref.install_progress.lock() = 0.0;
        app_ref.logs.lock().clear();
        app_ref.cancel_install.store(false, Ordering::Relaxed);
    }

    // Update the Slint window to reflect the navigation and wizard state
    if let Some(window) = window_weak.upgrade() {
        window.set_current_page(PageType::MO2);
        window.set_wizard_step(wizard_step_to_int(WizardStep::NameInput));
        window.set_instance_name(plugin_name.into());
        window.set_install_path("".into());
        window.set_install_type("New".into());
        window.set_validation_error("".into());
        window.set_last_error("".into());
        window.set_force_install(false);
        window.set_disk_override(false);
    }
}

// ============================================================================
// Marketplace State
// ============================================================================

#[derive(Default)]
pub struct MarketplaceState {
    pub registry: Option<nak_rust::marketplace::Registry>,
    pub manifests: std::collections::HashMap<usize, nak_rust::marketplace::PluginManifest>,
}

type PluginDetailResult = (usize, Result<nak_rust::marketplace::PluginManifest, String>);

/// Shared state for async marketplace operations
pub struct MarketplaceAsync {
    pub registry_result: Arc<Mutex<Option<Result<nak_rust::marketplace::Registry, String>>>>,
    pub detail_result: Arc<Mutex<Option<PluginDetailResult>>>,
    pub install_result: Arc<Mutex<Option<Result<String, String>>>>,
}
