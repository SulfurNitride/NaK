//! Steam shortcuts.vdf binary format parser and writer
//!
//! Handles reading and writing non-Steam game shortcuts.

use std::collections::HashSet;
use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

use rand::Rng;

use super::find_userdata_path;

/// Generate a random AppID for a non-Steam game shortcut
/// High bit (0x80000000) is set to mark as non-Steam game
pub fn generate_random_app_id() -> u32 {
    let mut rng = rand::rng();
    // Generate random u32 and set high bit for non-Steam game
    rng.random::<u32>() | 0x80000000
}

/// Get path to shortcuts.vdf for the current user
pub fn get_shortcuts_vdf_path() -> Option<PathBuf> {
    let userdata = find_userdata_path()?;
    Some(userdata.join("config/shortcuts.vdf"))
}


/// A Steam non-Steam game shortcut
#[derive(Clone, Debug)]
pub struct Shortcut {
    pub appid: u32,
    pub app_name: String,
    pub exe: String,
    pub start_dir: String,
    pub icon: String,
    pub shortcut_path: String,
    pub launch_options: String,
    pub is_hidden: bool,
    pub allow_desktop_config: bool,
    pub allow_overlay: bool,
    pub openvr: bool,
    pub devkit: bool,
    pub devkit_game_id: String,
    pub devkit_override_app_id: u32,
    pub last_play_time: u32,
    pub flatpak_app_id: String,
    pub tags: Vec<String>,
}

impl Default for Shortcut {
    fn default() -> Self {
        Shortcut {
            appid: 0,
            app_name: String::new(),
            exe: String::new(),
            start_dir: String::new(),
            icon: String::new(),
            shortcut_path: String::new(),
            launch_options: String::new(),
            is_hidden: false,
            allow_desktop_config: true,
            allow_overlay: true,
            openvr: false,
            devkit: false,
            devkit_game_id: String::new(),
            devkit_override_app_id: 0,
            last_play_time: 0,
            flatpak_app_id: String::new(),
            tags: Vec::new(),
        }
    }
}

impl Shortcut {
    /// Create a new shortcut with the given name and exe path
    /// AppID is generated randomly (collision check happens in add_shortcut)
    pub fn new(app_name: &str, exe_path: &str, start_dir: &str) -> Self {
        let appid = generate_random_app_id();
        Shortcut {
            appid,
            app_name: app_name.to_string(),
            exe: format!("\"{}\"", exe_path),
            start_dir: format!("\"{}\"", start_dir),
            ..Default::default()
        }
    }

    /// Add a tag to the shortcut (e.g., "NaK" for filtering)
    pub fn with_tag(mut self, tag: &str) -> Self {
        self.tags.push(tag.to_string());
        self
    }

    /// Set launch options (e.g., "STEAM_COMPAT_MOUNTS=/mnt:/media %command%")
    pub fn with_launch_options(mut self, options: &str) -> Self {
        self.launch_options = options.to_string();
        self
    }

}

/// Binary VDF shortcuts.vdf parser/writer
pub struct ShortcutsVdf {
    pub shortcuts: Vec<Shortcut>,
}

impl ShortcutsVdf {
    /// Create new empty shortcuts
    pub fn new() -> Self {
        ShortcutsVdf { shortcuts: Vec::new() }
    }

    /// Load shortcuts from the default Steam location
    pub fn load() -> Result<Self, Box<dyn std::error::Error>> {
        let path = get_shortcuts_vdf_path()
            .ok_or("Could not find Steam userdata path")?;
        Self::parse(&path)
    }

    /// Parse shortcuts.vdf binary format
    pub fn parse(path: &Path) -> Result<Self, Box<dyn std::error::Error>> {
        if !path.exists() {
            return Ok(ShortcutsVdf::new());
        }

        let mut file = fs::File::open(path)?;
        let mut data = Vec::new();
        file.read_to_end(&mut data)?;

        let mut shortcuts = Vec::new();
        let mut pos = 0;

        // Skip header: 0x00 "shortcuts" 0x00
        if data.len() < 11 {
            return Ok(ShortcutsVdf::new());
        }

        // Find start of shortcuts section
        while pos < data.len() && data[pos] != 0x00 {
            pos += 1;
        }
        if pos < data.len() { pos += 1; } // skip 0x00

        // Skip "shortcuts"
        while pos < data.len() && data[pos] != 0x00 {
            pos += 1;
        }
        if pos < data.len() { pos += 1; } // skip 0x00

        // Parse each shortcut
        while pos < data.len() {
            if data[pos] == 0x08 {
                // End of shortcuts section
                break;
            }

            if data[pos] != 0x00 {
                pos += 1;
                continue;
            }
            pos += 1; // skip type byte

            // Skip index string
            while pos < data.len() && data[pos] != 0x00 {
                pos += 1;
            }
            if pos < data.len() { pos += 1; } // skip 0x00

            let mut shortcut = Shortcut::default();

            // Parse key-value pairs until 0x08 (end of section)
            while pos < data.len() && data[pos] != 0x08 {
                let value_type = data[pos];
                pos += 1;

                // Read key name
                let key_start = pos;
                while pos < data.len() && data[pos] != 0x00 {
                    pos += 1;
                }
                let key = String::from_utf8_lossy(&data[key_start..pos]).to_string();
                if pos < data.len() { pos += 1; } // skip null terminator

                match value_type {
                    0x01 => {
                        // String value
                        let val_start = pos;
                        while pos < data.len() && data[pos] != 0x00 {
                            pos += 1;
                        }
                        let value = String::from_utf8_lossy(&data[val_start..pos]).to_string();
                        if pos < data.len() { pos += 1; } // skip null terminator

                        match key.to_lowercase().as_str() {
                            "appname" => shortcut.app_name = value,
                            "exe" => shortcut.exe = value,
                            "startdir" => shortcut.start_dir = value,
                            "icon" => shortcut.icon = value,
                            "shortcutpath" => shortcut.shortcut_path = value,
                            "launchoptions" => shortcut.launch_options = value,
                            "devkitgameid" => shortcut.devkit_game_id = value,
                            "flatpakappid" => shortcut.flatpak_app_id = value,
                            _ => {}
                        }
                    }
                    0x02 => {
                        // 32-bit integer
                        if pos + 4 <= data.len() {
                            let value = u32::from_le_bytes([
                                data[pos], data[pos+1], data[pos+2], data[pos+3]
                            ]);
                            pos += 4;

                            match key.to_lowercase().as_str() {
                                "appid" => shortcut.appid = value,
                                "ishidden" => shortcut.is_hidden = value != 0,
                                "allowdesktopconfig" => shortcut.allow_desktop_config = value != 0,
                                "allowoverlay" => shortcut.allow_overlay = value != 0,
                                "openvr" => shortcut.openvr = value != 0,
                                "devkit" => shortcut.devkit = value != 0,
                                "devkitoverrideappid" => shortcut.devkit_override_app_id = value,
                                "lastplaytime" => shortcut.last_play_time = value,
                                _ => {}
                            }
                        }
                    }
                    0x00 => {
                        // Subsection (tags)
                        if key.to_lowercase() == "tags" {
                            while pos < data.len() && data[pos] != 0x08 {
                                if data[pos] == 0x01 {
                                    pos += 1;
                                    // Skip tag index
                                    while pos < data.len() && data[pos] != 0x00 {
                                        pos += 1;
                                    }
                                    if pos < data.len() { pos += 1; } // skip null
                                    // Read tag value
                                    let tag_start = pos;
                                    while pos < data.len() && data[pos] != 0x00 {
                                        pos += 1;
                                    }
                                    let tag = String::from_utf8_lossy(&data[tag_start..pos]).to_string();
                                    shortcut.tags.push(tag);
                                    if pos < data.len() { pos += 1; } // skip null
                                } else {
                                    pos += 1;
                                }
                            }
                            if pos < data.len() { pos += 1; } // skip 0x08
                        }
                    }
                    _ => {
                        // Unknown type, try to skip
                        pos += 1;
                    }
                }
            }
            if pos < data.len() { pos += 1; } // skip 0x08 end-of-shortcut marker

            if !shortcut.app_name.is_empty() {
                shortcuts.push(shortcut);
            }
        }

        Ok(ShortcutsVdf { shortcuts })
    }

    /// Save shortcuts to the default Steam location
    pub fn save(&self) -> Result<(), Box<dyn std::error::Error>> {
        let path = get_shortcuts_vdf_path()
            .ok_or("Could not find Steam userdata path")?;
        self.write(&path)
    }

    /// Write shortcuts.vdf binary format
    pub fn write(&self, path: &Path) -> Result<(), Box<dyn std::error::Error>> {
        let mut data = Vec::new();

        // Header
        data.push(0x00);
        data.extend_from_slice(b"shortcuts");
        data.push(0x00);

        for (idx, shortcut) in self.shortcuts.iter().enumerate() {
            // Shortcut section start
            data.push(0x00);
            data.extend_from_slice(idx.to_string().as_bytes());
            data.push(0x00);

            // AppID - REQUIRED by Steam (must come first)
            Self::write_int(&mut data, "appid", shortcut.appid);

            // String fields
            Self::write_string(&mut data, "AppName", &shortcut.app_name);
            Self::write_string(&mut data, "Exe", &shortcut.exe);
            Self::write_string(&mut data, "StartDir", &shortcut.start_dir);
            Self::write_string(&mut data, "icon", &shortcut.icon);
            Self::write_string(&mut data, "ShortcutPath", &shortcut.shortcut_path);
            Self::write_string(&mut data, "LaunchOptions", &shortcut.launch_options);

            // Integer fields
            Self::write_int(&mut data, "IsHidden", shortcut.is_hidden as u32);
            Self::write_int(&mut data, "AllowDesktopConfig", shortcut.allow_desktop_config as u32);
            Self::write_int(&mut data, "AllowOverlay", shortcut.allow_overlay as u32);
            Self::write_int(&mut data, "OpenVR", shortcut.openvr as u32);
            Self::write_int(&mut data, "Devkit", shortcut.devkit as u32);
            Self::write_string(&mut data, "DevkitGameID", &shortcut.devkit_game_id);
            Self::write_int(&mut data, "DevkitOverrideAppID", shortcut.devkit_override_app_id);
            Self::write_int(&mut data, "LastPlayTime", shortcut.last_play_time);
            Self::write_string(&mut data, "FlatpakAppID", &shortcut.flatpak_app_id);

            // Tags subsection
            data.push(0x00);
            data.extend_from_slice(b"tags");
            data.push(0x00);
            for (tag_idx, tag) in shortcut.tags.iter().enumerate() {
                Self::write_string(&mut data, &tag_idx.to_string(), tag);
            }
            data.push(0x08); // End tags

            data.push(0x08); // End shortcut
        }

        data.push(0x08); // End shortcuts section
        data.push(0x08); // End root map (required!)

        // Ensure parent directory exists
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }

        let mut file = fs::File::create(path)?;
        file.write_all(&data)?;

        Ok(())
    }

    fn write_string(data: &mut Vec<u8>, key: &str, value: &str) {
        data.push(0x01);
        data.extend_from_slice(key.as_bytes());
        data.push(0x00);
        data.extend_from_slice(value.as_bytes());
        data.push(0x00);
    }

    fn write_int(data: &mut Vec<u8>, key: &str, value: u32) {
        data.push(0x02);
        data.extend_from_slice(key.as_bytes());
        data.push(0x00);
        data.extend_from_slice(&value.to_le_bytes());
    }

    /// Remove a shortcut by AppID. Returns true if found and removed.
    pub fn remove_shortcut_by_app_id(&mut self, app_id: u32) -> bool {
        let before = self.shortcuts.len();
        self.shortcuts.retain(|s| s.appid != app_id);
        self.shortcuts.len() < before
    }

    /// Add a shortcut with collision-checked random AppID
    /// Removes any existing shortcut with the same name
    pub fn add_shortcut(&mut self, mut shortcut: Shortcut) -> u32 {
        // Remove existing shortcut with same name
        self.shortcuts.retain(|s| s.app_name != shortcut.app_name);

        // Collect existing AppIDs to check for collisions
        let existing_ids: HashSet<u32> = self.shortcuts.iter().map(|s| s.appid).collect();

        // Regenerate AppID if collision detected (extremely rare but possible)
        while existing_ids.contains(&shortcut.appid) {
            shortcut.appid = generate_random_app_id();
        }

        let app_id = shortcut.appid;
        self.shortcuts.push(shortcut);
        app_id
    }

}

impl Default for ShortcutsVdf {
    fn default() -> Self {
        Self::new()
    }
}
