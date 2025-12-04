//! Application state and initialization

use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::sync::atomic::AtomicBool;
use std::thread;

use crate::wine::{ProtonInfo, ProtonFinder, NakPrefix, PrefixManager, GithubRelease};
use crate::wine::{fetch_ge_releases, ensure_winetricks, ensure_cabextract, check_command_available};
use crate::config::AppConfig;
use crate::nxm::NxmHandler;

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

pub struct ModManagerInstance {
    pub name: String,
    pub game: String,
    pub manager_type: String,
    pub status: String,
    #[allow(dead_code)]
    pub path: String,
}

// ============================================================================
// Application State
// ============================================================================

pub struct MyApp {
    // Navigation
    pub current_page: Page,

    // Page State: Mod Managers
    pub installed_instances: Vec<ModManagerInstance>,
    #[allow(dead_code)]
    pub show_prefix_manager: bool,
    #[allow(dead_code)]
    pub show_mo2_manager: bool,
    #[allow(dead_code)]
    pub show_vortex_manager: bool,

    pub is_installing_manager: Arc<Mutex<bool>>,
    pub install_status: Arc<Mutex<String>>,
    pub install_name_input: String,
    pub install_path_input: String,

    pub vortex_install_name: String,
    pub vortex_install_path: String,

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

    // Page State: Proton Tools
    pub proton_versions: Vec<ProtonInfo>,

    // GE-Proton Downloader State
    pub available_ge_versions: Arc<Mutex<Vec<GithubRelease>>>,
    pub ge_search_query: String,
    pub is_fetching_ge: Arc<Mutex<bool>>,

    pub is_downloading: Arc<Mutex<bool>>,
    pub download_status: Arc<Mutex<String>>,
    pub download_progress: Arc<Mutex<f32>>,

    // Flags
    pub should_refresh_proton: bool,
    pub missing_deps: Vec<String>,
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

        // Check Dependencies (uses check_command_available which also checks ~/NaK/bin)
        let mut missing = Vec::new();

        if !check_command_available("cabextract") { missing.push("cabextract".to_string()); }
        if !check_command_available("unzip") && !check_command_available("7z") { missing.push("unzip or 7z".to_string()); }
        if !check_command_available("curl") && !check_command_available("wget") { missing.push("curl or wget".to_string()); }

        let app = Self {
            current_page: Page::ModManagers,
            installed_instances: Vec::new(),
            show_prefix_manager: true,
            show_mo2_manager: true,
            show_vortex_manager: true,

            is_installing_manager: Arc::new(Mutex::new(false)),
            install_status: Arc::new(Mutex::new(String::new())),
            install_name_input: String::new(),
            install_path_input: String::new(),

            vortex_install_name: String::new(),
            vortex_install_path: String::new(),

            logs: Arc::new(Mutex::new(Vec::new())),
            install_progress: Arc::new(Mutex::new(0.0)),

            cancel_install: Arc::new(AtomicBool::new(false)),

            detected_prefixes: prefixes,
            prefix_manager: prefix_mgr,
            winetricks_path: winetricks_path_arc.clone(),

            config,

            proton_versions: protons,

            available_ge_versions: Arc::new(Mutex::new(Vec::new())),
            ge_search_query: String::new(),
            is_fetching_ge: Arc::new(Mutex::new(true)),

            is_downloading: Arc::new(Mutex::new(false)),
            download_status: Arc::new(Mutex::new(String::new())),
            download_progress: Arc::new(Mutex::new(0.0)),

            should_refresh_proton: false,
            missing_deps: missing,
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

        // Ensure Winetricks and cabextract are downloaded
        let wt_path = winetricks_path_arc.clone();
        thread::spawn(move || {
            // Ensure cabextract (for SteamOS/immutable systems)
            match ensure_cabextract() {
                Ok(path) => println!("cabextract available at: {:?}", path),
                Err(e) => eprintln!("Failed to ensure cabextract: {}", e),
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
