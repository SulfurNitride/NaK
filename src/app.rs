//! Application state and initialization

use std::path::PathBuf;
use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex};
use std::thread;

use crate::config::{AppConfig, CacheConfig};
use crate::games::{DetectedGame, GameFinder};
use crate::nxm::NxmHandler;
use crate::utils::detect_steam_path_checked;
use crate::wine::{
    check_command_available, ensure_cabextract, ensure_winetricks, fetch_cachyos_releases,
    fetch_ge_releases,
};
use crate::wine::{GithubRelease, NakPrefix, PrefixManager, ProtonFinder, ProtonInfo};

// ============================================================================
// Types
// ============================================================================

#[derive(PartialEq, Clone, Copy)]
pub enum Page {
    FirstRunSetup,
    GettingStarted,
    ModManagers,
    GameFixer,
    Marketplace,
    ProtonTools,
    Settings,
    Updater,
}

#[derive(PartialEq, Clone, Copy, Debug)]
pub enum ModManagerView {
    Dashboard,
    PrefixManager,
    Mo2Manager,
    VortexManager,
}

#[derive(PartialEq, Clone, Copy, Debug)]
pub enum WizardStep {
    Selection,
    NameInput,
    PathInput,
    DpiSetup, // DPI scaling configuration (after install, before finished)
    Finished,
}

#[derive(Clone, Debug)]
pub struct InstallWizard {
    pub step: WizardStep,
    pub manager_type: String, // "MO2" or "Vortex"
    pub install_type: String, // "New" or "Existing"
    pub name: String,
    pub path: String,
    pub validation_error: Option<String>,
    pub force_install: bool,
    pub last_install_error: Option<String>,
    pub use_slr: bool, // Whether to use Steam Linux Runtime for this installation
    // DPI Setup state
    pub selected_dpi: u32,      // Selected DPI value (96, 120, 144, 192, or custom)
    pub custom_dpi_input: String, // Text input for custom DPI value
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
            use_slr: true, // Default to using SLR (user can toggle)
            selected_dpi: 96, // Default 100% scaling
            custom_dpi_input: String::new(),
        }
    }
}

// ============================================================================
// Application State
// ============================================================================

pub struct MyApp {
    // Navigation
    pub current_page: Page,
    pub mod_manager_view: ModManagerView,

    // Installation Wizard State
    pub install_wizard: InstallWizard,

    pub is_installing_manager: Arc<Mutex<bool>>,
    pub install_status: Arc<Mutex<String>>,
    // Removed old scattered input fields in favor of InstallWizard

    pub logs: Arc<Mutex<Vec<String>>>,
    pub install_progress: Arc<Mutex<f32>>,

    pub cancel_install: Arc<AtomicBool>,

    // Page State: Prefix Manager
    pub detected_prefixes: Vec<NakPrefix>,
    pub prefix_manager: PrefixManager,
    pub winetricks_path: Arc<Mutex<Option<PathBuf>>>,

    // Configuration (Persisted)
    pub config: AppConfig,
    pub cache_config: CacheConfig,

    // Page State: Proton Tools
    pub proton_versions: Vec<ProtonInfo>,

    // Proton Downloader State (unified)
    pub available_ge_versions: Arc<Mutex<Vec<GithubRelease>>>,
    pub available_cachyos_versions: Arc<Mutex<Vec<GithubRelease>>>,
    pub proton_search_query: String,
    pub proton_download_source: String, // "ge" or "cachyos"
    pub is_fetching_ge: Arc<Mutex<bool>>,
    pub is_fetching_cachyos: Arc<Mutex<bool>>,

    pub is_downloading: Arc<Mutex<bool>>,
    pub download_status: Arc<Mutex<String>>,
    pub download_progress: Arc<Mutex<f32>>,

    // Flags
    pub should_refresh_proton: bool,
    pub download_needs_refresh: Arc<AtomicBool>, // Signal from background downloads to refresh UI
    pub missing_deps: Arc<Mutex<Vec<String>>>,

    // Steam Detection
    pub steam_detected: bool,
    pub steam_path: Option<String>,

    // Settings page state
    pub migration_path_input: String,
    pub cached_storage_info: Option<crate::config::StorageInfo>,
    pub storage_info_last_update: std::time::Instant,

    // Confirmation dialog state
    pub pending_prefix_delete: Option<String>,
    pub pending_proton_delete: Option<(String, String)>, // (name, type: "ge" or "cachyos")

    // Game Modding Helper state
    pub detected_games: Vec<DetectedGame>,
    pub game_search_query: String,
    pub is_applying_game_fix: Arc<Mutex<bool>>,
    pub game_fix_status: Arc<Mutex<String>>,
    pub game_fix_logs: Arc<Mutex<Vec<String>>>,

    // Updater state
    pub update_info: Arc<Mutex<Option<crate::updater::UpdateInfo>>>,
    pub is_checking_update: Arc<Mutex<bool>>,
    pub is_installing_update: Arc<Mutex<bool>>,
    pub update_error: Arc<Mutex<Option<String>>>,
    pub update_installed: Arc<Mutex<bool>>,

    // DPI test process tracking
    pub dpi_test_processes: Arc<Mutex<Vec<u32>>>, // PIDs of running test apps

    // Prefix manager DPI custom input (shared across all prefixes)
    pub prefix_custom_dpi_input: String,
}

impl Default for MyApp {
    fn default() -> Self {
        // Initialize Proton Finder
        let finder = ProtonFinder::new();
        let protons = finder.find_all();

        // Initialize Prefix Manager
        let prefix_mgr = PrefixManager::new();
        let prefixes = prefix_mgr.scan_prefixes();

        // Initialize Game Finder
        let game_finder = GameFinder::new();
        let detected_games = game_finder.find_all_games();

        let winetricks_path_arc = Arc::new(Mutex::new(None));

        // Load Configuration
        let config = AppConfig::load();
        let cache_config = CacheConfig::load();

        // Ensure data directories exist (for new installs or after data path change)
        let data_path = config.get_data_path();
        let _ = std::fs::create_dir_all(&data_path);
        let _ = std::fs::create_dir_all(data_path.join("Prefixes"));
        let _ = std::fs::create_dir_all(data_path.join("ProtonGE"));
        let _ = std::fs::create_dir_all(data_path.join("tmp"));
        let _ = std::fs::create_dir_all(data_path.join("bin"));
        let _ = std::fs::create_dir_all(data_path.join("logs"));

        // Ensure active proton symlink exists (for updating users)
        // If user has a selected proton but no active symlink, create it
        let active_link = data_path.join("ProtonGE/active");
        if !active_link.exists() {
            if let Some(selected_name) = &config.selected_proton {
                // Find the selected proton in available versions
                if let Some(selected_proton) = protons.iter().find(|p| &p.name == selected_name) {
                    let _ = crate::wine::set_active_proton(selected_proton);
                }
            } else if let Some(first_proton) = protons.first() {
                // No proton selected but we have some available - select the first one
                let _ = crate::wine::set_active_proton(first_proton);
            }
        }

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
            mod_manager_view: ModManagerView::Dashboard,

            install_wizard: InstallWizard::default(),

            is_installing_manager: Arc::new(Mutex::new(false)),
            install_status: Arc::new(Mutex::new(String::new())),

            logs: Arc::new(Mutex::new(Vec::new())),
            install_progress: Arc::new(Mutex::new(0.0)),

            cancel_install: Arc::new(AtomicBool::new(false)),

            detected_prefixes: prefixes,
            prefix_manager: prefix_mgr,
            winetricks_path: winetricks_path_arc.clone(),

            config,
            cache_config,

            proton_versions: protons,

            available_ge_versions: Arc::new(Mutex::new(Vec::new())),
            available_cachyos_versions: Arc::new(Mutex::new(Vec::new())),
            proton_search_query: String::new(),
            proton_download_source: "ge".to_string(),
            is_fetching_ge: Arc::new(Mutex::new(true)),
            is_fetching_cachyos: Arc::new(Mutex::new(true)),

            is_downloading: Arc::new(Mutex::new(false)),
            download_status: Arc::new(Mutex::new(String::new())),
            download_progress: Arc::new(Mutex::new(0.0)),

            should_refresh_proton: false,
            download_needs_refresh: Arc::new(AtomicBool::new(false)),
            missing_deps: missing_deps_arc.clone(),

            steam_detected,
            steam_path,

            migration_path_input: String::new(),
            cached_storage_info: None,
            storage_info_last_update: std::time::Instant::now(),

            pending_prefix_delete: None,
            pending_proton_delete: None,

            detected_games,
            game_search_query: String::new(),
            is_applying_game_fix: Arc::new(Mutex::new(false)),
            game_fix_status: Arc::new(Mutex::new(String::new())),
            game_fix_logs: Arc::new(Mutex::new(Vec::new())),

            // Updater
            update_info: Arc::new(Mutex::new(None)),
            is_checking_update: Arc::new(Mutex::new(false)),
            is_installing_update: Arc::new(Mutex::new(false)),
            update_error: Arc::new(Mutex::new(None)),
            update_installed: Arc::new(Mutex::new(false)),

            // DPI test processes
            dpi_test_processes: Arc::new(Mutex::new(Vec::new())),

            // Prefix manager DPI input
            prefix_custom_dpi_input: String::new(),
        };

        // Auto-fetch on startup (GE Proton)
        let is_fetching = app.is_fetching_ge.clone();
        let versions = app.available_ge_versions.clone();

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

        // Auto-fetch on startup (CachyOS Proton)
        let is_fetching_cachyos = app.is_fetching_cachyos.clone();
        let cachyos_versions = app.available_cachyos_versions.clone();

        thread::spawn(move || {
            match fetch_cachyos_releases() {
                Ok(releases) => {
                    *cachyos_versions.lock().unwrap() = releases;
                }
                Err(e) => {
                    eprintln!("Failed to fetch CachyOS releases: {}", e);
                }
            }
            *is_fetching_cachyos.lock().unwrap() = false;
        });

        // Auto-download Steam Runtime only if:
        // 1. First-run setup is complete (user has made their choice)
        // 2. User has opted to use SLR
        // 3. SLR is not already installed
        if app.config.first_run_completed
            && app.config.use_steam_runtime
            && !crate::wine::runtime::is_runtime_installed()
        {
            let status = app.download_status.clone();
            let progress = app.download_progress.clone();
            let is_downloading = app.is_downloading.clone();

            *is_downloading.lock().unwrap() = true;
            *status.lock().unwrap() = "Initializing Steam Runtime...".to_string();

            thread::spawn(move || {
                let cb_status = status.clone();
                let cb_progress = progress.clone();
                let cb_downloading = is_downloading.clone();

                // Create inner clones for the callback
                let cb_status_inner = cb_status.clone();
                let cb_progress_inner = cb_progress.clone();

                let callback = move |current: u64, total: u64| {
                    if total > 0 {
                        let p = current as f32 / total as f32;
                        *cb_progress_inner.lock().unwrap() = p;
                        *cb_status_inner.lock().unwrap() = format!("Downloading Runtime: {:.1}%", p * 100.0);
                    }
                };

                match crate::wine::runtime::download_runtime(callback) {
                    Ok(_) => {
                        *cb_status.lock().unwrap() = "Runtime Ready!".to_string();
                        *cb_progress.lock().unwrap() = 1.0;
                    }
                    Err(e) => {
                        *cb_status.lock().unwrap() = format!("Error downloading runtime: {}", e);
                    }
                }
                *cb_downloading.lock().unwrap() = false;
            });
        }

        // Auto-check for updates on startup
        let update_info_arc = app.update_info.clone();
        let is_checking_arc = app.is_checking_update.clone();
        thread::spawn(move || {
            match crate::updater::check_for_updates() {
                Ok(info) => {
                    *update_info_arc.lock().unwrap() = Some(info);
                }
                Err(e) => {
                    eprintln!("Failed to check for updates: {}", e);
                }
            }
            *is_checking_arc.lock().unwrap() = false;
        });

        // Ensure Winetricks and cabextract are downloaded
        let wt_path = winetricks_path_arc.clone();
        let missing_deps_for_thread = missing_deps_arc.clone();
        thread::spawn(move || {
            // Ensure cabextract (for SteamOS/immutable systems)
            match ensure_cabextract() {
                Ok(path) => println!("cabextract available at: {:?}", path),
                Err(e) => {
                    eprintln!("Failed to ensure cabextract: {}", e);
                    // Add to missing deps if download failed
                    missing_deps_for_thread
                        .lock()
                        .unwrap()
                        .push("cabextract".to_string());
                }
            }

            // Ensure winetricks
            match ensure_winetricks() {
                Ok(path) => *wt_path.lock().unwrap() = Some(path),
                Err(e) => eprintln!("Failed to download winetricks: {}", e),
            }

            // Ensure NXM Handler
            if let Err(e) = NxmHandler::setup() {
                eprintln!("Failed to setup NXM handler: {}", e);
            }
        });

        app
    }
}

impl MyApp {
    pub fn refresh_proton_versions(&mut self) {
        let finder = ProtonFinder::new();
        self.proton_versions = finder.find_all();

        // Check if selected proton is still valid
        let mut changed = false;
        if let Some(selected) = &self.config.selected_proton {
            let exists = self.proton_versions.iter().any(|p| &p.name == selected);
            if !exists {
                // Default to first available or None
                if let Some(first) = self.proton_versions.first() {
                    self.config.selected_proton = Some(first.name.clone());
                } else {
                    self.config.selected_proton = None;
                }
                changed = true;
            }
        } else if let Some(first) = self.proton_versions.first() {
            // If nothing was selected but we have versions, select the first one
            self.config.selected_proton = Some(first.name.clone());
            changed = true;
        }

        if changed {
            self.config.save();
        }

        // Also refresh prefixes
        self.detected_prefixes = self.prefix_manager.scan_prefixes();
    }

    pub fn refresh_detected_games(&mut self) {
        let game_finder = GameFinder::new();
        self.detected_games = game_finder.find_all_games();
    }

    /// Trigger SLR download if not already installed/downloading
    pub fn start_slr_download(&self) {
        if crate::wine::runtime::is_runtime_installed() {
            return; // Already installed
        }

        if *self.is_downloading.lock().unwrap() {
            return; // Already downloading
        }

        let status = self.download_status.clone();
        let progress = self.download_progress.clone();
        let is_downloading = self.is_downloading.clone();

        *is_downloading.lock().unwrap() = true;
        *status.lock().unwrap() = "Starting Steam Runtime download...".to_string();

        thread::spawn(move || {
            let cb_status = status.clone();
            let cb_progress = progress.clone();
            let cb_downloading = is_downloading.clone();

            let cb_status_inner = cb_status.clone();
            let cb_progress_inner = cb_progress.clone();

            let callback = move |current: u64, total: u64| {
                if total > 0 {
                    let p = current as f32 / total as f32;
                    *cb_progress_inner.lock().unwrap() = p;
                    *cb_status_inner.lock().unwrap() = format!("Downloading Runtime: {:.1}%", p * 100.0);
                }
            };

            match crate::wine::runtime::download_runtime(callback) {
                Ok(_) => {
                    *cb_status.lock().unwrap() = "Runtime Ready!".to_string();
                    *cb_progress.lock().unwrap() = 1.0;
                }
                Err(e) => {
                    *cb_status.lock().unwrap() = format!("Error downloading runtime: {}", e);
                }
            }
            *cb_downloading.lock().unwrap() = false;
        });
    }
}
