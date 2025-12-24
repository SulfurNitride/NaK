use std::error::Error;
use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

pub struct NxmHandler;

impl NxmHandler {
    pub fn setup() -> Result<(), Box<dyn Error>> {
        let home = std::env::var("HOME")?;
        let script_path = nak_path!("nxm_handler.sh");
        let applications_dir = PathBuf::from(format!("{}/.local/share/applications", home));
        let desktop_path = applications_dir.join("nak-nxm-handler.desktop");

        // Ensure directories exist
        fs::create_dir_all(nak_path!())?;
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
        // Supports both MO2 (via nxmhandler.exe) and Vortex mod managers.
        let script_content = format!(
            r#"#!/bin/bash
# NaK Global NXM Handler
# Forwards nxm:// links to the active mod manager instance (MO2 or Vortex)

ACTIVE_LINK="{}/active_nxm_game"

if [ ! -L "$ACTIVE_LINK" ]; then
    zenity --error --text="No active mod manager instance selected in NaK!" --title="NaK Error"
    exit 1
fi

# Resolve the link to find the game directory
GAME_DIR=$(readlink -f "$ACTIVE_LINK")

# Detect mod manager type by looking for the actual executables
# Then find the appropriate launch script

if [ -f "$GAME_DIR/nxmhandler.exe" ]; then
    # MO2 installation detected
    if [ -f "$GAME_DIR/Handle NXM" ]; then
        # New setup with dedicated NXM handler script
        LAUNCHER="$GAME_DIR/Handle NXM"
    elif [ -f "$GAME_DIR/Launch MO2" ]; then
        # Fallback for older installations - MO2 can handle NXM args
        LAUNCHER="$GAME_DIR/Launch MO2"
    else
        zenity --error --text="Found nxmhandler.exe but no launch script in: $GAME_DIR" --title="NaK Error"
        exit 1
    fi
elif [ -f "$GAME_DIR/Vortex.exe" ]; then
    # Vortex installation detected
    if [ -f "$GAME_DIR/Launch Vortex" ]; then
        LAUNCHER="$GAME_DIR/Launch Vortex"
    else
        zenity --error --text="Found Vortex.exe but no launch script in: $GAME_DIR" --title="NaK Error"
        exit 1
    fi
else
    zenity --error --text="Could not find nxmhandler.exe (MO2) or Vortex.exe in: $GAME_DIR" --title="NaK Error"
    exit 1
fi

# Run the mod manager with the NXM link
"$LAUNCHER" "$1"
"#,
            nak_path!().display()
        );

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

    pub fn set_active_instance(install_dir: &Path) -> Result<(), Box<dyn Error>> {
        let link_path = nak_path!("active_nxm_game");

        if link_path.exists() || fs::symlink_metadata(&link_path).is_ok() {
            let _ = fs::remove_file(&link_path);
        }

        std::os::unix::fs::symlink(install_dir, &link_path)?;
        println!("Set active NXM instance to {:?}", install_dir);
        Ok(())
    }
}
