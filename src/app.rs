//! Application state and initialization

use std::path::PathBuf;
use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex};
use std::thread;

use crate::config::{AppConfig, CacheConfig};
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
    GettingStarted,
    ModManagers,
    Marketplace,
    ProtonTools,
    Settings,
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

    // Page State: Mod Managers
    #[allow(dead_code)]
    pub show_prefix_manager: bool,
    #[allow(dead_code)]
    pub show_mo2_manager: bool,
    #[allow(dead_code)]
    pub show_vortex_manager: bool,

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
    #[allow(dead_code)]
    pub prefix_manager: PrefixManager,
    pub winetricks_path: Arc<Mutex<Option<PathBuf>>>,

    // Configuration (Persisted)
    pub config: AppConfig,
    pub cache_config: CacheConfig,

    // Page State: Proton Tools
    pub proton_versions: Vec<ProtonInfo>,

    // GE-Proton Downloader State
    pub available_ge_versions: Arc<Mutex<Vec<GithubRelease>>>,
    pub ge_search_query: String,
    pub is_fetching_ge: Arc<Mutex<bool>>,

    // CachyOS Proton Downloader State
    pub available_cachyos_versions: Arc<Mutex<Vec<GithubRelease>>>,
    pub cachyos_search_query: String,
    pub is_fetching_cachyos: Arc<Mutex<bool>>,

    pub is_downloading: Arc<Mutex<bool>>,
    pub download_status: Arc<Mutex<String>>,
    pub download_progress: Arc<Mutex<f32>>,

    // Flags
    pub should_refresh_proton: bool,
    pub missing_deps: Arc<Mutex<Vec<String>>>,

    // Steam Detection
    pub steam_detected: bool,
    pub steam_path: Option<String>,

    // Settings page state
    pub migration_path_input: String,
}

impl Default for MyApp {
    fn default() -> Self {
        // Initialize Proton Finder
        let finder = ProtonFinder::new();
        let protons = finder.find_all();

        // Initialize Prefix Manager
        let prefix_mgr = PrefixManager::new();
        let prefixes = prefix_mgr.scan_prefixes();

        let winetricks_path_arc = Arc::new(Mutex::new(None));

        // Load Configuration
        let config = AppConfig::load();
        let cache_config = CacheConfig::load();

        // Detect Steam at startup (with logging)
        let steam_path = detect_steam_path_checked();
        let steam_detected = steam_path.is_some();

        // Check Dependencies (uses check_command_available which also checks ~/NaK/bin)
        // Note: cabextract will be auto-downloaded if missing, so we check it later
        let mut missing = Vec::new();

        if !check_command_available("unzip") && !check_command_available("7z") {
            missing.push("unzip or 7z".to_string());
        }
        if !check_command_available("curl") && !check_command_available("wget") {
            missing.push("curl or wget".to_string());
        }

        let missing_deps_arc = Arc::new(Mutex::new(missing));

        let app = Self {
            current_page: Page::GettingStarted,
            mod_manager_view: ModManagerView::Dashboard,
            show_prefix_manager: true,
            show_mo2_manager: true,
            show_vortex_manager: true,

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
            ge_search_query: String::new(),
            is_fetching_ge: Arc::new(Mutex::new(true)),

            available_cachyos_versions: Arc::new(Mutex::new(Vec::new())),
            cachyos_search_query: String::new(),
            is_fetching_cachyos: Arc::new(Mutex::new(true)),

            is_downloading: Arc::new(Mutex::new(false)),
            download_status: Arc::new(Mutex::new(String::new())),
            download_progress: Arc::new(Mutex::new(0.0)),

            should_refresh_proton: false,
            missing_deps: missing_deps_arc.clone(),

            steam_detected,
            steam_path,

            migration_path_input: String::new(),
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
    #[allow(dead_code)]
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
}
