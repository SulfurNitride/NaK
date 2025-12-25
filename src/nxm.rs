use std::error::Error;
use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

use crate::config::AppConfig;

pub struct NxmHandler;

impl NxmHandler {
    pub fn setup() -> Result<(), Box<dyn Error>> {
        let home = std::env::var("HOME")?;
        let config = AppConfig::load();
        let nak_dir = config.get_data_path();
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

        // 1. Create the Handler Script
        // Uses relative path from script location to find active_nxm_game symlink
        // active_nxm_game points to prefix directory (e.g., $DATA_PATH/Prefixes/mo2_xxx)
        // which contains nxm_handler.sh that runs nxmhandler.exe through proton
        let script_content = r#"#!/bin/bash
# NaK Global NXM Handler
# Forwards nxm:// links to the active prefix's nxm_handler.sh

# Derive paths relative to script location (portable after NaK folder moves)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ACTIVE_LINK="$SCRIPT_DIR/active_nxm_game"

if [ ! -L "$ACTIVE_LINK" ]; then
    zenity --error --text="No active mod manager instance selected in NaK!" --title="NaK Error"
    exit 1
fi

PREFIX_DIR=$(readlink -f "$ACTIVE_LINK")
NXM_SCRIPT="$PREFIX_DIR/nxm_handler.sh"

if [ ! -f "$NXM_SCRIPT" ]; then
    zenity --error --text="NXM handler script not found: $NXM_SCRIPT" --title="NaK Error"
    exit 1
fi

"$NXM_SCRIPT" "$1"
"#;

        let mut file = fs::File::create(&script_path)?;
        file.write_all(script_content.as_bytes())?;
        let mut perms = fs::metadata(&script_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&script_path, perms)?;

        // 2. Create Desktop Entry
        let desktop_content = format!(
            r#"[Desktop Entry]
Type=Application
Name=NaK NXM Handler
Comment=Handle Nexus Mods links via NaK
Exec="{}" %u
Icon=utilities-terminal
Terminal=false
Categories=Game;Utility;
MimeType=x-scheme-handler/nxm;
"#,
            script_path.to_string_lossy()
        );

        let mut dfile = fs::File::create(&desktop_path)?;
        dfile.write_all(desktop_content.as_bytes())?;

        // 3. Register Mime Type (xdg-mime)
        std::process::Command::new("xdg-mime")
            .arg("default")
            .arg("nak-nxm-handler.desktop")
            .arg("x-scheme-handler/nxm")
            .spawn()?;

        println!("NXM Handler registered.");
        Ok(())
    }

    /// Set active NXM instance - takes prefix base path (e.g., $DATA_PATH/Prefixes/mo2_xxx)
    pub fn set_active_instance(prefix_base: &Path) -> Result<(), Box<dyn Error>> {
        let config = AppConfig::load();
        let link_path = config.get_data_path().join("active_nxm_game");

        if link_path.exists() || fs::symlink_metadata(&link_path).is_ok() {
            let _ = fs::remove_file(&link_path);
        }

        std::os::unix::fs::symlink(prefix_base, &link_path)?;
        println!("Set active NXM instance to {:?}", prefix_base);
        Ok(())
    }
}
