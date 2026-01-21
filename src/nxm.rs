//! NXM URL Handler for Steam-native integration
//!
//! Registers NaK as the system's nxm:// URL handler and routes
//! NXM links to the active mod manager instance via direct Proton launch.
//! If the mod manager isn't running, it launches via Steam first.

use std::error::Error;
use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;

use crate::config::AppConfig;
use crate::logging::{log_install, log_warning};

pub struct NxmHandler;

impl NxmHandler {
    /// Get the path to config files
    fn config_dir() -> PathBuf {
        AppConfig::get_config_dir()
    }

    /// Set up the NXM handler system (desktop file and handler script)
    pub fn setup() -> Result<(), Box<dyn Error>> {
        let home = std::env::var("HOME")?;
        let nak_dir = Self::config_dir();
        let script_path = nak_dir.join("nxm_handler.sh");
        let applications_dir = PathBuf::from(format!("{}/.local/share/applications", home));
        let desktop_path = applications_dir.join("nak-nxm-handler.desktop");

        // Ensure directories exist
        fs::create_dir_all(&nak_dir)?;
        fs::create_dir_all(&applications_dir)?;

        // Clean up old NXM handler variations
        let old_handlers = [
            "nxm-handler.desktop",
            "nak_nxm_handler.desktop",
            "NaK-nxm-handler.desktop",
            "nak-nxm.desktop",
        ];
        for old in &old_handlers {
            let old_path = applications_dir.join(old);
            if old_path.exists() {
                let _ = fs::remove_file(&old_path);
            }
        }

        // Create the NXM handler script (Direct Proton launch version)
        let script_content = include_str!("scripts/nxm_handler.sh");

        let mut file = fs::File::create(&script_path)?;
        file.write_all(script_content.as_bytes())?;
        let mut perms = fs::metadata(&script_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&script_path, perms)?;

        // Create Desktop Entry
        // Note: According to XDG spec, Exec paths with special chars should be quoted,
        // but some implementations have issues with quotes. Since our path is in
        // ~/.config/nak/ (no spaces), we don't need quotes.
        let desktop_content = format!(
            r#"[Desktop Entry]
Type=Application
Version=1.1
Name=NaK NXM Handler
GenericName=Nexus Mods Link Handler
Comment=Handle Nexus Mods nxm:// links via NaK
Exec={} %u
Icon=applications-games
Terminal=false
Categories=Game;Utility;
MimeType=x-scheme-handler/nxm;
StartupNotify=false
NoDisplay=false
"#,
            script_path.to_string_lossy()
        );

        let mut dfile = fs::File::create(&desktop_path)?;
        dfile.write_all(desktop_content.as_bytes())?;

        // Update desktop database so the app appears in application pickers
        // This is required for new installations - without it, the app won't
        // show up when users try to select an application to handle nxm:// links
        let db_result = std::process::Command::new("update-desktop-database")
            .arg(&applications_dir)
            .status();

        if let Err(e) = db_result {
            log_warning(&format!("Failed to run update-desktop-database: {}", e));
        }

        // Register MIME type in user's mimeapps.list (XDG standard location)
        // This ensures the handler is set even if xdg-mime has issues
        let mimeapps_path = PathBuf::from(format!("{}/.config/mimeapps.list", home));
        Self::add_mime_association(&mimeapps_path, "x-scheme-handler/nxm", "nak-nxm-handler.desktop");

        // Also try the legacy location some systems still use
        let legacy_mimeapps = applications_dir.join("mimeapps.list");
        Self::add_mime_association(&legacy_mimeapps, "x-scheme-handler/nxm", "nak-nxm-handler.desktop");

        // Register with xdg-mime as well (belt and suspenders approach)
        let status = std::process::Command::new("xdg-mime")
            .arg("default")
            .arg("nak-nxm-handler.desktop")
            .arg("x-scheme-handler/nxm")
            .status();

        match status {
            Ok(s) if s.success() => {
                log_install("NXM Handler registered successfully (Direct Proton)");
            }
            Ok(_) => {
                // xdg-mime failed but we also wrote to mimeapps.list directly
                log_warning("xdg-mime returned error, but handler was registered via mimeapps.list");
            }
            Err(e) => {
                log_warning(&format!("xdg-mime not available ({}), handler registered via mimeapps.list", e));
            }
        }

        // Fix Flatpak browser permissions for NXM handler access
        Self::fix_flatpak_browsers();

        Ok(())
    }

    /// Add a MIME type association to a mimeapps.list file
    fn add_mime_association(path: &PathBuf, mime_type: &str, desktop_file: &str) {
        // Read existing content or start fresh
        let content = fs::read_to_string(path).unwrap_or_default();

        let entry = format!("{}={}", mime_type, desktop_file);
        let section_header = "[Default Applications]";

        // Check if already correctly set
        if content.contains(&entry) {
            return;
        }

        let new_content = if content.contains(section_header) {
            // Section exists - check if mime type is already there
            let mut lines: Vec<&str> = content.lines().collect();
            let mut found = false;
            let mut in_section = false;

            for line in &mut lines {
                if line.starts_with('[') {
                    in_section = *line == section_header;
                } else if in_section && line.starts_with(&format!("{}=", mime_type)) {
                    // Update existing entry - but we can't mutate through &str
                    found = true;
                    break;
                }
            }

            if found {
                // Replace the existing entry
                content
                    .lines()
                    .map(|line| {
                        if line.starts_with(&format!("{}=", mime_type)) {
                            entry.clone()
                        } else {
                            line.to_string()
                        }
                    })
                    .collect::<Vec<_>>()
                    .join("\n")
            } else {
                // Add entry after section header
                content.replace(section_header, &format!("{}\n{}", section_header, entry))
            }
        } else {
            // No section - add it
            if content.is_empty() {
                format!("{}\n{}\n", section_header, entry)
            } else {
                format!("{}\n\n{}\n{}\n", content.trim_end(), section_header, entry)
            }
        };

        // Ensure parent directory exists
        if let Some(parent) = path.parent() {
            let _ = fs::create_dir_all(parent);
        }

        let _ = fs::write(path, new_content);
    }

    /// Fix Flatpak browser permissions for NXM handling
    ///
    /// Flatpak browsers are sandboxed and can't launch external scripts or access
    /// removable media by default. This adds the necessary overrides.
    pub fn fix_flatpak_browsers() {
        const FLATPAK_BROWSERS: &[&str] = &[
            "com.brave.Browser",
            "com.google.Chrome",
            "org.chromium.Chromium",
            "com.github.nickvergessen.nickvergessen_chromium",
            "org.mozilla.firefox",
            "one.ablaze.floorp",
            "net.waterfox.waterfox",
            "app.zen_browser.zen",
        ];

        // Check if flatpak command exists
        let flatpak_check = std::process::Command::new("flatpak")
            .arg("--version")
            .output();

        if flatpak_check.is_err() {
            // Flatpak not installed, nothing to do
            return;
        }

        // Get list of installed flatpaks
        let installed = match std::process::Command::new("flatpak")
            .args(["list", "--app", "--columns=application"])
            .output()
        {
            Ok(output) => String::from_utf8_lossy(&output.stdout).to_string(),
            Err(_) => return,
        };

        let mut fixed_count = 0;

        for browser_id in FLATPAK_BROWSERS {
            if installed.contains(browser_id) {
                // Apply the necessary overrides
                let result = std::process::Command::new("flatpak")
                    .args([
                        "override",
                        "--user",
                        browser_id,
                        "--filesystem=home",
                        "--filesystem=/run/media/",
                        "--talk-name=org.freedesktop.portal.*",
                    ])
                    .status();

                if let Ok(status) = result {
                    if status.success() {
                        log_install(&format!("Fixed Flatpak permissions for {}", browser_id));
                        fixed_count += 1;
                    }
                }
            }
        }

        if fixed_count > 0 {
            log_install(&format!(
                "Applied Flatpak NXM handler permissions to {} browser(s)",
                fixed_count
            ));
        }
    }
}
