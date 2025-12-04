use std::path::{Path, PathBuf};
use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::error::Error;

pub struct NxmHandler;

impl NxmHandler {
    pub fn setup() -> Result<(), Box<dyn Error>> {
        let home = std::env::var("HOME")?;
        let nak_dir = PathBuf::from(format!("{}/NaK", home));
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
        // This script finds the 'active_nxm_game' symlink and passes the argument to it.
        // We assume 'active_nxm_game' points to the installation directory (where 'Launch MO2' is).
        let script_content = format!(r#"#!/bin/bash
# NaK Global NXM Handler
# Forwards nxm:// links to the active Mod Organizer 2 instance

ACTIVE_LINK="{}/NaK/active_nxm_game"

if [ ! -L "$ACTIVE_LINK" ]; then
    zenity --error --text="No active MO2 instance selected in NaK!" --title="NaK Error"
    exit 1
fi

# Resolve the link to find the game directory
GAME_DIR=$(readlink -f "$ACTIVE_LINK")
LAUNCHER="$GAME_DIR/Launch MO2"

if [ ! -f "$LAUNCHER" ]; then
    zenity --error --text="Could not find 'Launch MO2' in active instance." --title="NaK Error"
    exit 1
fi

# Run MO2 with the NXM link
"$LAUNCHER" "$1"
"#, home);

        let mut file = fs::File::create(&script_path)?;
        file.write_all(script_content.as_bytes())?;
        let mut perms = fs::metadata(&script_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&script_path, perms)?;

        // 2. Create Desktop Entry
        let desktop_content = format!(r#"[Desktop Entry]
Type=Application
Name=NaK NXM Handler
Comment=Handle Nexus Mods links via NaK
Exec="{}" %u
Icon=utilities-terminal
Terminal=false
Categories=Game;Utility;
MimeType=x-scheme-handler/nxm;
"#, script_path.to_string_lossy());

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

    pub fn set_active_instance(install_dir: &Path) -> Result<(), Box<dyn Error>> {
        let home = std::env::var("HOME")?;
        let link_path = PathBuf::from(format!("{}/NaK/active_nxm_game", home));

        if link_path.exists() || fs::symlink_metadata(&link_path).is_ok() {
            let _ = fs::remove_file(&link_path);
        }

        std::os::unix::fs::symlink(install_dir, &link_path)?;
        println!("Set active NXM instance to {:?}", install_dir);
        Ok(())
    }
}
