//! Steam Proton detection and management
//!
//! Finds Protons that Steam can see and use for non-Steam games.
//! This includes Steam's built-in Protons and custom Protons in compatibilitytools.d.

use std::fs;
use std::path::PathBuf;

use super::find_steam_path;

/// Information about an installed Proton version
#[derive(Debug, Clone)]
pub struct SteamProton {
    /// Display name (e.g., "GE-Proton9-20", "Proton Experimental")
    pub name: String,
    /// Internal name used in config.vdf (e.g., "proton_experimental", "GE-Proton9-20")
    pub config_name: String,
    /// Full path to the Proton installation
    pub path: PathBuf,
    /// Whether this is a Steam-provided Proton (vs custom)
    pub is_steam_proton: bool,
    /// Whether this is Proton Experimental
    pub is_experimental: bool,
}

impl SteamProton {
    /// Get the path to the wine binary.
    /// Checks multiple possible locations: files/bin/wine (standard) and dist/bin/wine (some builds)
    pub fn wine_binary(&self) -> Option<PathBuf> {
        let paths = [
            self.path.join("files/bin/wine"),
            self.path.join("dist/bin/wine"),
        ];
        paths.into_iter().find(|p| p.exists())
    }

    /// Get the path to the wineserver binary.
    pub fn wineserver_binary(&self) -> Option<PathBuf> {
        let paths = [
            self.path.join("files/bin/wineserver"),
            self.path.join("dist/bin/wineserver"),
        ];
        paths.into_iter().find(|p| p.exists())
    }

    /// Get the bin directory containing wine executables.
    pub fn bin_dir(&self) -> Option<PathBuf> {
        self.wine_binary().and_then(|p| p.parent().map(|p| p.to_path_buf()))
    }
}

/// Check if Steam is installed via Flatpak
pub fn is_flatpak_steam() -> bool {
    find_steam_path()
        .map(|p| p.to_string_lossy().contains(".var/app/com.valvesoftware.Steam"))
        .unwrap_or(false)
}

/// Find all Protons that Steam can use (Proton 10+ only)
pub fn find_steam_protons() -> Vec<SteamProton> {
    let mut protons = Vec::new();

    let Some(steam_path) = find_steam_path() else {
        return protons;
    };

    let is_flatpak = steam_path.to_string_lossy().contains(".var/app/com.valvesoftware.Steam");

    // 1. Steam's built-in Protons (steamapps/common/Proton*)
    protons.extend(find_builtin_protons(&steam_path));

    // 2. Custom Protons in user's compatibilitytools.d
    protons.extend(find_custom_protons(&steam_path));

    // 3. System-level Protons in /usr/share/steam/compatibilitytools.d/
    // Skip for Flatpak Steam - system protons won't work properly with Flatpak
    if is_flatpak {
        crate::logging::log_info("Flatpak Steam detected - skipping system protons in /usr/share/steam/compatibilitytools.d/");
    } else {
        protons.extend(find_system_protons());
    }

    // Filter to only include Proton 10+ (required for Steam-native integration)
    protons.retain(is_proton_10_or_newer);

    // Filter to only include Protons with valid wine binaries
    protons.retain(|p| {
        let has_wine = p.wine_binary().is_some();
        if !has_wine {
            crate::logging::log_warning(&format!(
                "Skipping Proton '{}': wine binary not found at expected paths (files/bin/wine or dist/bin/wine)",
                p.name
            ));
        }
        has_wine
    });

    // Sort: Experimental first, then by name descending (newest first)
    protons.sort_by(|a, b| {
        if a.is_experimental != b.is_experimental {
            return b.is_experimental.cmp(&a.is_experimental);
        }
        b.name.cmp(&a.name)
    });

    protons
}

/// Check if a Proton version is 10 or newer
/// Returns true for GE-Proton10+, Proton 10+, CachyOS, and Experimental
fn is_proton_10_or_newer(proton: &SteamProton) -> bool {
    let name = &proton.name;

    // Experimental is always allowed
    if proton.is_experimental || name.contains("Experimental") {
        return true;
    }

    // CachyOS is always 10+ based
    if name.contains("CachyOS") {
        return true;
    }

    // LegacyRuntime is not a Proton - skip it
    if name == "LegacyRuntime" || name.contains("Runtime") {
        return false;
    }

    // GE-Proton: extract version from "GE-Proton10-27" format
    if name.starts_with("GE-Proton") {
        if let Some(version_part) = name.strip_prefix("GE-Proton") {
            let major: Option<u32> = version_part
                .split('-')
                .next()
                .and_then(|s| s.parse().ok());
            return major.map(|v| v >= 10).unwrap_or(false);
        }
    }

    // Steam Proton: extract version from "Proton 10.0" or "Proton 9.0" format
    if name.starts_with("Proton ") {
        if let Some(version_part) = name.strip_prefix("Proton ") {
            let major: Option<u32> = version_part
                .split('.')
                .next()
                .and_then(|s| s.parse().ok());
            return major.map(|v| v >= 10).unwrap_or(false);
        }
    }

    // EM-Proton: "EM-10.0-33" format
    if name.starts_with("EM-") {
        if let Some(version_part) = name.strip_prefix("EM-") {
            let major: Option<u32> = version_part
                .split('.')
                .next()
                .and_then(|s| s.parse().ok());
            return major.map(|v| v >= 10).unwrap_or(false);
        }
    }

    // Unknown format - allow it (might be a custom build)
    true
}

/// Find Steam's built-in Proton versions
fn find_builtin_protons(steam_path: &std::path::Path) -> Vec<SteamProton> {
    let mut found = Vec::new();
    let common_dir = steam_path.join("steamapps/common");

    let Ok(entries) = fs::read_dir(&common_dir) else {
        return found;
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }

        let name = entry.file_name().to_string_lossy().to_string();

        // Check for valid Proton directory (must have 'proton' script)
        if name.starts_with("Proton") && path.join("proton").exists() {
            let is_experimental = name.contains("Experimental");

            // Config name is lowercase with underscores
            let config_name = if is_experimental {
                "proton_experimental".to_string()
            } else {
                // "Proton 9" -> "proton_9", "Proton 8.0" -> "proton_8"
                let version = name.replace("Proton ", "");
                let major = version.split('.').next().unwrap_or(&version);
                format!("proton_{}", major)
            };

            found.push(SteamProton {
                name: name.clone(),
                config_name,
                path,
                is_steam_proton: true,
                is_experimental,
            });
        }
    }

    found
}

/// Find custom Protons in compatibilitytools.d
fn find_custom_protons(steam_path: &std::path::Path) -> Vec<SteamProton> {
    let mut found = Vec::new();
    let compat_dir = steam_path.join("compatibilitytools.d");

    let Ok(entries) = fs::read_dir(&compat_dir) else {
        return found;
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }

        let name = entry.file_name().to_string_lossy().to_string();

        // Check for valid Proton (has proton script or compatibilitytool.vdf)
        let has_proton = path.join("proton").exists();
        let has_vdf = path.join("compatibilitytool.vdf").exists();

        if has_proton || has_vdf {
            // For custom Protons, config_name is usually the folder name
            found.push(SteamProton {
                name: name.clone(),
                config_name: name.clone(),
                path,
                is_steam_proton: false,
                is_experimental: false,
            });
        }
    }

    found
}

/// Find system-level Protons in /usr/share/steam/compatibilitytools.d/
/// These are typically installed via system packages (e.g., proton-cachyos, proton-ge)
fn find_system_protons() -> Vec<SteamProton> {
    let mut found = Vec::new();
    let system_compat_dir = PathBuf::from("/usr/share/steam/compatibilitytools.d");

    let Ok(entries) = fs::read_dir(&system_compat_dir) else {
        return found;
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }

        let name = entry.file_name().to_string_lossy().to_string();

        // Check for valid Proton (has proton script or compatibilitytool.vdf)
        let has_proton = path.join("proton").exists();
        let has_vdf = path.join("compatibilitytool.vdf").exists();

        if has_proton || has_vdf {
            // For system Protons, config_name is the folder name
            found.push(SteamProton {
                name: name.clone(),
                config_name: name.clone(),
                path,
                is_steam_proton: false,
                is_experimental: false,
            });
        }
    }

    found
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_find_protons() {
        // This test will only work on a system with Steam installed
        let protons = find_steam_protons();
        println!("Found {} Protons:", protons.len());
        for p in &protons {
            println!("  {} (config: {}, steam: {})", p.name, p.config_name, p.is_steam_proton);
        }
    }
}
