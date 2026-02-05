//! Application state and initialization

use std::path::PathBuf;
use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex};
use std::thread;

use nak_rust::config::AppConfig;
use nak_rust::nxm::NxmHandler;
use nak_rust::deps::{check_command_available, ensure_cabextract, ensure_winetricks};
use nak_rust::steam::detect_steam_path_checked;

// ============================================================================
// Types
// ============================================================================

#[derive(PartialEq, Clone, Copy, Debug)]
pub enum Page {
    FirstRunSetup,
    GettingStarted,
    ModManagers,
    Marketplace,
    Settings,
    Updater,
}

#[derive(PartialEq, Clone, Copy, Debug)]
pub enum WizardStep {
    Selection,
    NameInput,
    PathInput,
    ProtonSelect, // Proton version selection (after path, before install)
    DpiSetup, // DPI scaling configuration (after install, before finished)
    Finished,
}

#[derive(Clone, Debug)]
pub struct InstallWizard {
    pub step: WizardStep,
    pub manager_type: String, // "MO2"
    pub install_type: String, // "New" or "Existing"
    pub name: String,
    pub path: String,
    pub validation_error: Option<String>,
    pub force_install: bool,
    pub last_install_error: Option<String>,
    // DPI Setup state
    pub selected_dpi: u32,      // Selected DPI value (96, 120, 144, 192, or custom)
    // Steam AppID after installation (for DPI setup)
    pub installed_app_id: Option<u32>,
    // Steam prefix path after installation (for DPI setup)
    pub installed_prefix_path: Option<PathBuf>,
    // Disk space override
    pub low_disk_space: bool,           // True if disk space is below recommended
    pub disk_space_override: bool,      // User acknowledged low disk space and wants to proceed
    pub available_disk_gb: f64,         // Available disk space in GB (cached)
    // Proton selection
    pub selected_proton: Option<String>, // Selected Proton config_name
}

impl Default for InstallWizard {
    fn default() -> Self {
        Self {
            step: WizardStep::Selection,
            manager_type: String::new(),
            install_type: String::new(),
            name: String::new(),
            path: String::new(),
            validation_error: None,
            force_install: false,
            last_install_error: None,
            selected_dpi: 96, // Default 100% scaling
            installed_app_id: None,
            installed_prefix_path: None,
            low_disk_space: false,
            disk_space_override: false,
            available_disk_gb: 0.0,
            selected_proton: None,
        }
    }
}

// ============================================================================
// Application State
// ============================================================================

pub struct MyApp {
    // Navigation
    pub current_page: Page,

    // Installation Wizard State
    pub install_wizard: InstallWizard,

    pub is_installing_manager: Arc<Mutex<bool>>,
    pub install_status: Arc<Mutex<String>>,
    // Removed old scattered input fields in favor of InstallWizard

    pub logs: Arc<Mutex<Vec<String>>>,
    pub install_progress: Arc<Mutex<f32>>,

    pub cancel_install: Arc<AtomicBool>,

    // Configuration (Persisted)
    pub config: AppConfig,

    // Flags
    pub missing_deps: Arc<Mutex<Vec<String>>>,

    // Steam Detection
    pub steam_detected: bool,
    pub steam_path: Option<String>,
    pub steam_protons: Vec<nak_rust::steam::SteamProton>,

    // Steam migration popup (for users with legacy prefixes)
    pub show_steam_migration_popup: bool,

    // Updater state
    pub update_info: Arc<Mutex<Option<nak_rust::updater::UpdateInfo>>>,
    pub is_checking_update: Arc<Mutex<bool>>,
    pub is_installing_update: Arc<Mutex<bool>>,
    pub update_error: Arc<Mutex<Option<String>>>,
    pub update_installed: Arc<Mutex<bool>>,

    // DPI test process tracking
    pub dpi_test_processes: Arc<Mutex<Vec<u32>>>, // PIDs of running test apps

    // Install result communication (from install thread to UI thread)
    pub install_result_app_id: Arc<Mutex<Option<u32>>>,       // Steam AppID after installation
    pub install_result_prefix_path: Arc<Mutex<Option<PathBuf>>>, // Prefix path after installation

    // Marketplace state
    pub marketplace_state: Option<crate::ui::MarketplaceState>,
}

impl Default for MyApp {
    fn default() -> Self {
        // Load Configuration
        let config = AppConfig::load();

        // Ensure config directories exist (Steam-native uses ~/.config/nak/ for everything)
        // Note: We no longer create ~/NaK directories - that was for the old standalone system
        // Note: Logs now go to current working directory for easy access
        let config_dir = AppConfig::get_config_dir();
        let _ = std::fs::create_dir_all(&config_dir);
        let _ = std::fs::create_dir_all(config_dir.join("bin"));
        let _ = std::fs::create_dir_all(config_dir.join("tmp"));

        // Detect Steam at startup (with logging)
        let steam_path = detect_steam_path_checked();
        let steam_detected = steam_path.is_some();

        // Check Dependencies (uses check_command_available which also checks $DATA_PATH/bin)
        // Note: cabextract will be auto-downloaded if missing, so we check it later
        // Note: 7z extraction is now handled natively in Rust (sevenz-rust crate)
        let mut missing = Vec::new();

        if !check_command_available("curl") && !check_command_available("wget") {
            missing.push("curl or wget".to_string());
        }

        let missing_deps_arc = Arc::new(Mutex::new(missing));

        // Determine starting page based on first-run status
        let starting_page = if config.first_run_completed {
            Page::GettingStarted
        } else {
            Page::FirstRunSetup
        };

        let app = Self {
            current_page: starting_page,

            install_wizard: InstallWizard::default(),

            is_installing_manager: Arc::new(Mutex::new(false)),
            install_status: Arc::new(Mutex::new(String::new())),

            logs: Arc::new(Mutex::new(Vec::new())),
            install_progress: Arc::new(Mutex::new(0.0)),

            cancel_install: Arc::new(AtomicBool::new(false)),

            config,

            missing_deps: missing_deps_arc.clone(),

            steam_detected,
            steam_path,
            steam_protons: nak_rust::steam::find_steam_protons(),

            show_steam_migration_popup: false, // Will be set below if legacy data found

            // Updater
            update_info: Arc::new(Mutex::new(None)),
            is_checking_update: Arc::new(Mutex::new(false)),
            is_installing_update: Arc::new(Mutex::new(false)),
            update_error: Arc::new(Mutex::new(None)),
            update_installed: Arc::new(Mutex::new(false)),

            // DPI test processes
            dpi_test_processes: Arc::new(Mutex::new(Vec::new())),

            // Install result communication
            install_result_app_id: Arc::new(Mutex::new(None)),
            install_result_prefix_path: Arc::new(Mutex::new(None)),

            // Marketplace
            marketplace_state: None,
        };

        // Auto-check for updates on startup
        let update_info_arc = app.update_info.clone();
        let is_checking_arc = app.is_checking_update.clone();
        thread::spawn(move || {
            match nak_rust::updater::check_for_updates() {
                Ok(info) => {
                    *update_info_arc.lock().unwrap() = Some(info);
                }
                Err(e) => {
                    eprintln!("Failed to check for updates: {}", e);
                }
            }
            *is_checking_arc.lock().unwrap() = false;
        });

        // Ensure dependencies are downloaded and NXM handler is set up
        let missing_deps_for_thread = missing_deps_arc.clone();
        thread::spawn(move || {
            // Ensure cabextract (for SteamOS/immutable systems)
            match ensure_cabextract() {
                Ok(path) => println!("cabextract available at: {:?}", path),
                Err(e) => {
                    eprintln!("Failed to ensure cabextract: {}", e);
                    missing_deps_for_thread
                        .lock()
                        .unwrap()
                        .push("cabextract".to_string());
                }
            }

            // Ensure winetricks (downloaded to NaK bin, auto-updates)
            match ensure_winetricks() {
                Ok(path) => println!("winetricks available at: {:?}", path),
                Err(e) => eprintln!("Failed to ensure winetricks: {}", e),
            }

            // Ensure NXM Handler
            if let Err(e) = NxmHandler::setup() {
                eprintln!("Failed to setup NXM handler: {}", e);
            }
        });

        // Check for legacy NaK data and show migration notice (once)
        let mut app = app;
        if !app.config.steam_migration_shown {
            // Check if user has legacy NaK data (old Prefixes or ProtonGE folders)
            let legacy_prefixes = app.config.get_prefixes_path();
            let legacy_proton = app.config.get_data_path().join("ProtonGE");

            let has_legacy_prefixes = legacy_prefixes.exists()
                && legacy_prefixes.read_dir().map(|mut d| d.next().is_some()).unwrap_or(false);
            let has_legacy_proton = legacy_proton.exists()
                && legacy_proton.read_dir().map(|mut d| d.next().is_some()).unwrap_or(false);

            if has_legacy_prefixes || has_legacy_proton {
                app.show_steam_migration_popup = true;
            }
        }

        app
    }
}

