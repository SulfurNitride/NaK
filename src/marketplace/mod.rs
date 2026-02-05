//! NaK Marketplace - Plugin system for extending NaK functionality

use std::error::Error;
use serde::Deserialize;

/// GitHub raw URL base for the marketplace repo
const MARKETPLACE_RAW_URL: &str = "https://raw.githubusercontent.com/SulfurNitride/NaK-Marketplace/main";

// ============================================================================
// Plugin Types
// ============================================================================

/// Registry entry for a plugin (from registry.toml)
#[derive(Debug, Clone, Deserialize)]
pub struct RegistryEntry {
    pub id: String,
    pub name: String,
    pub description: String,
    pub folder: String,
}

/// The registry file containing all available plugins
#[derive(Debug, Clone, Deserialize)]
pub struct Registry {
    pub plugins: Vec<RegistryEntry>,
}

/// Plugin metadata (from plugin.toml [plugin] section)
#[derive(Debug, Clone, Deserialize)]
pub struct PluginMeta {
    pub id: String,
    pub name: String,
    pub description: String,
    pub author: String,
    pub min_nak_version: String,
}

/// Plugin source configuration (from plugin.toml [source] section)
#[derive(Debug, Clone, Deserialize)]
pub struct PluginSource {
    #[serde(rename = "type")]
    pub source_type: String,
    pub repo: Option<String>,
    pub asset_pattern: Option<String>,
    pub url: Option<String>,
}

/// Plugin install configuration (from plugin.toml [install] section)
#[derive(Debug, Clone, Deserialize)]
pub struct PluginInstall {
    #[serde(rename = "type")]
    pub install_type: String,
    pub exe_name: String,
    #[serde(default)]
    pub installer_args: Vec<String>,
}

/// Complete plugin manifest (plugin.toml)
#[derive(Debug, Clone, Deserialize)]
pub struct PluginManifest {
    pub plugin: PluginMeta,
    pub source: PluginSource,
    pub install: PluginInstall,
}
// ============================================================================
// Fetch Functions
// ============================================================================

/// Fetch the plugin registry from GitHub
pub fn fetch_registry() -> Result<Registry, Box<dyn Error>> {
    let url = format!("{}/registry.toml", MARKETPLACE_RAW_URL);

    let response = ureq::get(&url)
        .set("User-Agent", "NaK-Rust")
        .call()?;

    let content = response.into_string()?;
    let registry: Registry = toml::from_str(&content)?;

    Ok(registry)
}

/// Fetch a plugin's manifest from GitHub
pub fn fetch_plugin_manifest(folder: &str) -> Result<PluginManifest, Box<dyn Error>> {
    let url = format!("{}/{}/plugin.toml", MARKETPLACE_RAW_URL, folder);

    let response = ureq::get(&url)
        .set("User-Agent", "NaK-Rust")
        .call()?;

    let content = response.into_string()?;
    let manifest: PluginManifest = toml::from_str(&content)?;

    Ok(manifest)
}

/// Check if the current NaK version meets the plugin's minimum requirement
pub fn check_version_compatible(min_version: &str) -> bool {
    let current = env!("CARGO_PKG_VERSION");
    version_compare::compare_to(current, min_version, version_compare::Cmp::Ge).unwrap_or(false)
}

use crate::github::GithubRelease;

// ============================================================================
// Install Functions
// ============================================================================

/// Get the download URL for a plugin based on its manifest
/// Returns (download_url, version_tag) tuple
pub fn get_plugin_download_url(manifest: &PluginManifest) -> Result<(String, String), Box<dyn Error>> {
    match manifest.source.source_type.as_str() {
        "github-release" => {
            let repo = manifest.source.repo.as_ref()
                .ok_or("github-release source requires 'repo' field")?;
            let pattern = manifest.source.asset_pattern.as_ref()
                .ok_or("github-release source requires 'asset_pattern' field")?;

            // Fetch latest release from GitHub API
            let api_url = format!("https://api.github.com/repos/{}/releases/latest", repo);
            let response: GithubRelease = ureq::get(&api_url)
                .set("User-Agent", "NaK-Rust")
                .call()?
                .into_json()?;

            let version = response.tag_name.clone();

            // Find matching asset using glob pattern
            let pattern_lower = pattern.to_lowercase();
            let asset = response.assets.iter()
                .find(|a| {
                    let name_lower = a.name.to_lowercase();
                    // Simple glob matching: handle * as wildcard
                    if pattern_lower.contains('*') {
                        let parts: Vec<&str> = pattern_lower.split('*').collect();
                        let mut pos = 0;
                        for part in parts {
                            if part.is_empty() { continue; }
                            if let Some(found) = name_lower[pos..].find(part) {
                                pos += found + part.len();
                            } else {
                                return false;
                            }
                        }
                        true
                    } else {
                        name_lower == pattern_lower
                    }
                })
                .ok_or_else(|| format!("No asset matching pattern '{}' found in release", pattern))?;

            Ok((asset.browser_download_url.clone(), version))
        }
        "direct-url" => {
            let url = manifest.source.url.clone()
                .ok_or("direct-url source requires 'url' field")?;
            Ok((url, "latest".to_string()))
        }
        other => Err(format!("Unknown source type: {}", other).into()),
    }
}

/// Get the installer arguments with placeholders replaced
pub fn get_installer_args(manifest: &PluginManifest, install_path: &std::path::Path) -> Vec<String> {
    let win_path = format!("Z:{}", install_path.to_string_lossy().replace('/', "\\"));

    manifest.install.installer_args.iter()
        .map(|arg| arg.replace("{install_path}", &win_path))
        .collect()
}

/// Get plugin info for display
pub fn get_plugin_display_info(manifest: &PluginManifest) -> (String, String, String) {
    (
        manifest.plugin.name.clone(),
        manifest.plugin.description.clone(),
        manifest.plugin.author.clone(),
    )
}

/// Get the expected executable name for a plugin
pub fn get_plugin_exe_name(manifest: &PluginManifest) -> &str {
    &manifest.install.exe_name
}

/// Get the install type for a plugin
pub fn get_plugin_install_type(manifest: &PluginManifest) -> &str {
    &manifest.install.install_type
}
