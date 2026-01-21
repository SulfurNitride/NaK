//! Universal Steam compatdata scanner
//!
//! Scans ALL Steam compatdata folders across all libraries to discover
//! game save folders (Documents/My Games, AppData/Local, AppData/Roaming).
//! Uses "most recently modified wins" strategy for duplicate folder names.

use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::SystemTime;

use crate::logging::{log_info, log_warning};

// ============================================================================
// Types
// ============================================================================

/// Type of folder discovered in a prefix
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum FolderType {
    /// Documents/My Games/*
    MyGames,
    /// Documents/* (top-level, not My Games)
    DocumentsRoot,
    /// AppData/Local/*
    AppDataLocal,
    /// AppData/Roaming/*
    AppDataRoaming,
}

/// A folder discovered in a compatdata prefix
#[derive(Debug, Clone)]
#[allow(dead_code)] // folder_type stored for debugging/future use
pub struct DiscoveredFolder {
    /// Name of the folder (e.g., "Skyrim Special Edition")
    pub name: String,
    /// Full path to the folder in the compatdata prefix
    pub source_path: PathBuf,
    /// Steam App ID of the game this folder belongs to
    pub app_id: String,
    /// Modification time of the folder
    pub mtime: SystemTime,
    /// Type of folder (My Games, Documents root, AppData Local/Roaming)
    pub folder_type: FolderType,
}

/// Result of scanning all compatdata folders
#[derive(Debug, Default)]
pub struct ScanResult {
    /// Discovered folders, keyed by (FolderType, folder_name)
    /// When duplicates exist, contains the one with newest mtime
    pub folders: HashMap<(FolderType, String), DiscoveredFolder>,
    /// Duplicates that were skipped: (skipped_folder, kept_folder)
    pub duplicates: Vec<(DiscoveredFolder, DiscoveredFolder)>,
}

// ============================================================================
// Blacklists
// ============================================================================

/// Folders to skip in AppData/Local and AppData/Roaming
const APPDATA_BLACKLIST: &[&str] = &[
    // Wine/Proton internals
    "wine",
    "Wine",
    // Cache folders
    "cache",
    "Cache",
    "fontconfig",
    "Temp",
    "temp",
    "tmp",
    // Windows system folders
    "Microsoft",
    "Packages",
    "D3DSCache",
    "INetCache",
    "INetCookies",
    "LocalLow",
    "VirtualStore",
    "CrashDumps",
    // Browser data
    "Google",
    "Mozilla",
    "BraveSoftware",
    "chromium",
    "Chromium",
    // Other common non-game folders
    "FontForge",
    "gtk-3.0",
    "gtk-2.0",
    "dconf",
    "recently-used.xbel",
];

/// Folders to skip in Documents
const DOCUMENTS_BLACKLIST: &[&str] = &[
    "My Music",
    "My Pictures",
    "My Videos",
];

// ============================================================================
// Steam Library Detection
// ============================================================================

/// Get all Steam library paths by parsing libraryfolders.vdf from ALL Steam installations
pub fn get_all_steam_libraries() -> Vec<PathBuf> {
    let mut libraries = Vec::new();

    // Check ALL possible Steam installations (native, Flatpak, Snap)
    let home = match std::env::var("HOME") {
        Ok(h) => h,
        Err(_) => return libraries,
    };

    let steam_roots = [
        format!("{}/.steam/steam", home),
        format!("{}/.local/share/Steam", home),
        format!("{}/.var/app/com.valvesoftware.Steam/.steam/steam", home),  // Flatpak
        format!("{}/snap/steam/common/.steam/steam", home),                  // Snap
    ];

    for steam_root in &steam_roots {
        let steam_path = PathBuf::from(steam_root);
        if !steam_path.exists() {
            continue;
        }

        // Parse libraryfolders.vdf from this Steam installation
        let vdf_path = steam_path.join("steamapps/libraryfolders.vdf");
        if let Ok(content) = fs::read_to_string(&vdf_path) {
            for path in parse_library_paths(&content) {
                let steamapps = PathBuf::from(&path).join("steamapps");
                if steamapps.exists() && !libraries.contains(&steamapps) {
                    libraries.push(steamapps);
                }
            }
        }
    }

    log_info(&format!("Found {} Steam libraries for compatdata scan", libraries.len()));
    for lib in &libraries {
        log_info(&format!("  - {}", lib.display()));
    }

    libraries
}

/// Parse library paths from libraryfolders.vdf content
fn parse_library_paths(content: &str) -> Vec<String> {
    let mut paths = Vec::new();

    // VDF format: "path"		"/path/to/library"
    for line in content.lines() {
        let trimmed = line.trim();
        if let Some((key, value)) = parse_vdf_kv(trimmed) {
            if key == "path" {
                paths.push(value);
            }
        }
    }

    paths
}

/// Parse a VDF key-value pair like: "key"    "value"
fn parse_vdf_kv(line: &str) -> Option<(String, String)> {
    let mut parts = Vec::new();
    let mut current = String::new();
    let mut in_quotes = false;

    for c in line.chars() {
        match c {
            '"' => {
                if in_quotes {
                    parts.push(current.clone());
                    current.clear();
                }
                in_quotes = !in_quotes;
            }
            _ if in_quotes => current.push(c),
            _ => {} // Skip whitespace outside quotes
        }
    }

    if parts.len() >= 2 {
        Some((parts[0].clone(), parts[1].clone()))
    } else {
        None
    }
}

// ============================================================================
// Scanning Functions
// ============================================================================

/// Scan all Steam compatdata folders across all libraries
pub fn scan_all_compatdata() -> ScanResult {
    let mut result = ScanResult::default();
    let libraries = get_all_steam_libraries();

    for library in libraries {
        let compatdata_dir = library.join("compatdata");
        if !compatdata_dir.exists() {
            continue;
        }

        // Iterate over all app ID folders
        let Ok(entries) = fs::read_dir(&compatdata_dir) else {
            continue;
        };

        for entry in entries.flatten() {
            let app_id_path = entry.path();
            let Some(app_id) = app_id_path.file_name().and_then(|n| n.to_str()) else {
                continue;
            };

            // Skip non-numeric folders
            if !app_id.chars().all(|c| c.is_ascii_digit()) {
                continue;
            }

            // Skip "0" folder (anonymous/offline mode)
            if app_id == "0" {
                continue;
            }

            let prefix_path = app_id_path.join("pfx");
            if prefix_path.exists() {
                scan_prefix(&prefix_path, app_id, &mut result);
            }
        }
    }

    result
}

/// Scan a single Wine prefix for Documents and AppData folders
fn scan_prefix(prefix_path: &Path, app_id: &str, result: &mut ScanResult) {
    let users_dir = prefix_path.join("drive_c/users");
    let username = find_prefix_username(&users_dir);

    let user_dir = users_dir.join(&username);

    // Scan Documents/My Games
    let my_games = user_dir.join("Documents/My Games");
    if my_games.exists() {
        scan_directory(&my_games, app_id, FolderType::MyGames, DOCUMENTS_BLACKLIST, result);
    }

    // Scan Documents root (excluding My Games)
    let documents = user_dir.join("Documents");
    if documents.exists() {
        scan_directory_excluding(&documents, app_id, FolderType::DocumentsRoot, DOCUMENTS_BLACKLIST, &["My Games"], result);
    }

    // Scan AppData/Local
    let appdata_local = user_dir.join("AppData/Local");
    if appdata_local.exists() {
        scan_directory(&appdata_local, app_id, FolderType::AppDataLocal, APPDATA_BLACKLIST, result);
    }

    // Scan AppData/Roaming
    let appdata_roaming = user_dir.join("AppData/Roaming");
    if appdata_roaming.exists() {
        scan_directory(&appdata_roaming, app_id, FolderType::AppDataRoaming, APPDATA_BLACKLIST, result);
    }
}

/// Scan a directory for non-blacklisted, non-empty folders
fn scan_directory(
    dir: &Path,
    app_id: &str,
    folder_type: FolderType,
    blacklist: &[&str],
    result: &mut ScanResult,
) {
    scan_directory_excluding(dir, app_id, folder_type, blacklist, &[], result);
}

/// Scan a directory, excluding specific folder names in addition to blacklist
fn scan_directory_excluding(
    dir: &Path,
    app_id: &str,
    folder_type: FolderType,
    blacklist: &[&str],
    exclude: &[&str],
    result: &mut ScanResult,
) {
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }

        // Skip symlinks - we only want real folders, not symlinks to other locations
        // This prevents symlink stacking (creating symlinks to symlinks)
        if path.is_symlink() {
            continue;
        }

        let Some(name) = path.file_name().and_then(|n| n.to_str()) else {
            continue;
        };

        // Skip blacklisted folders
        if is_blacklisted(name, blacklist) {
            continue;
        }

        // Skip folders with file extensions (e.g., "Skyrim.INI" folder is a mistake)
        if name.contains('.') && name.rsplit('.').next().is_some_and(|ext| ext.len() <= 4) {
            continue;
        }

        // Skip explicitly excluded folders
        if exclude.contains(&name) {
            continue;
        }

        // Skip empty directories
        if is_empty_directory(&path) {
            continue;
        }

        // Get modification time
        let mtime = fs::metadata(&path)
            .and_then(|m| m.modified())
            .unwrap_or(SystemTime::UNIX_EPOCH);

        let folder = DiscoveredFolder {
            name: name.to_string(),
            source_path: path.clone(),
            app_id: app_id.to_string(),
            mtime,
            folder_type,
        };

        let key = (folder_type, name.to_string());

        // Handle duplicates: most recently modified wins
        if let Some(existing) = result.folders.get(&key) {
            if folder.mtime > existing.mtime {
                // New folder is newer, replace
                let old = existing.clone();
                result.folders.insert(key, folder.clone());
                result.duplicates.push((old, folder));
            } else {
                // Existing is newer, skip new one
                result.duplicates.push((folder, existing.clone()));
            }
        } else {
            result.folders.insert(key, folder);
        }
    }
}

/// Check if a folder name is in the blacklist
fn is_blacklisted(name: &str, blacklist: &[&str]) -> bool {
    blacklist.contains(&name)
}

/// Check if a directory is empty (has no files or subdirectories)
fn is_empty_directory(path: &Path) -> bool {
    match fs::read_dir(path) {
        Ok(mut entries) => entries.next().is_none(),
        Err(_) => true, // Treat unreadable as empty
    }
}

/// Find the username from a Wine prefix users directory
fn find_prefix_username(users_dir: &Path) -> String {
    if let Ok(entries) = fs::read_dir(users_dir) {
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().to_string();
            if name != "Public" && name != "root" {
                return name;
            }
        }
    }
    "steamuser".to_string()
}

// ============================================================================
// Import Function
// ============================================================================

/// Import discovered folders into NaK Tools by creating symlinks
///
/// Creates symlinks in:
/// - Prefix Documents/My Games/ for MyGames folders
/// - Prefix Documents/ for DocumentsRoot folders
/// - Prefix AppData Local/ for AppDataLocal folders
/// - Prefix AppData Roaming/ for AppDataRoaming folders
pub fn auto_import_from_all_compatdata(tools_dir: &Path) {
    let scan_result = scan_all_compatdata();

    // Log duplicates
    for (skipped, kept) in &scan_result.duplicates {
        log_info(&format!(
            "Duplicate '{}': using App {} (newer), skipping App {}",
            skipped.name, kept.app_id, skipped.app_id
        ));
    }

    // Set up target directories
    let prefix_docs = tools_dir.join("Prefix Documents");
    let my_games_dir = prefix_docs.join("My Games");
    let prefix_appdata_local = tools_dir.join("Prefix AppData Local");
    let prefix_appdata_roaming = tools_dir.join("Prefix AppData Roaming");

    // Ensure directories exist
    let _ = fs::create_dir_all(&my_games_dir);

    let mut imported_count = 0;

    // Create symlinks for each discovered folder
    for ((folder_type, name), folder) in &scan_result.folders {
        let target_dir = match folder_type {
            FolderType::MyGames => my_games_dir.join(name),
            FolderType::DocumentsRoot => prefix_docs.join(name),
            FolderType::AppDataLocal => prefix_appdata_local.join(name),
            FolderType::AppDataRoaming => prefix_appdata_roaming.join(name),
        };

        // Skip if target already exists (don't overwrite user's setup)
        if target_dir.exists() || target_dir.is_symlink() {
            continue;
        }

        // Ensure parent directory exists
        if let Some(parent) = target_dir.parent() {
            let _ = fs::create_dir_all(parent);
        }

        // Create symlink
        match std::os::unix::fs::symlink(&folder.source_path, &target_dir) {
            Ok(()) => {
                log_info(&format!(
                    "Imported {:?}/{} from App {}",
                    folder_type, name, folder.app_id
                ));
                imported_count += 1;
            }
            Err(e) => {
                log_warning(&format!(
                    "Failed to import {:?}/{}: {}",
                    folder_type, name, e
                ));
            }
        }
    }

    if imported_count > 0 {
        log_info(&format!(
            "Auto-imported {} folder(s) from Steam compatdata",
            imported_count
        ));
    }
}
