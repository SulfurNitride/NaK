//! Known games configuration
//!
//! Contains metadata for games that NaK supports, including:
//! - Steam App ID
//! - My Games folder name (Documents/My Games/*)
//! - AppData/Local folder name
//! - Registry path for game detection

/// Configuration for a known game
#[derive(Debug, Clone)]
pub struct KnownGame {
    /// Display name
    pub name: &'static str,
    /// Steam App ID
    pub steam_app_id: &'static str,
    /// GOG App ID (if available)
    pub gog_app_id: Option<&'static str>,
    /// Folder name in Documents/My Games (if applicable)
    pub my_games_folder: Option<&'static str>,
    /// Folder name in AppData/Local (if applicable)
    pub appdata_local_folder: Option<&'static str>,
    /// Folder name in AppData/Roaming (if applicable)
    pub appdata_roaming_folder: Option<&'static str>,
    /// Registry path under HKLM\Software\ (for game detection)
    pub registry_path: &'static str,
    /// Registry value name for install path
    pub registry_value: &'static str,
    /// Expected folder name in steamapps/common/
    pub steam_folder: &'static str,
}

/// All known games that NaK supports
pub const KNOWN_GAMES: &[KnownGame] = &[
    // Bethesda Games
    KnownGame {
        name: "Enderal",
        steam_app_id: "933480",
        gog_app_id: None,
        my_games_folder: Some("Enderal"),
        appdata_local_folder: None,
        appdata_roaming_folder: None,
        registry_path: r"Software\SureAI\Enderal",
        registry_value: "Install_Path",
        steam_folder: "Enderal",
    },
    KnownGame {
        name: "Enderal Special Edition",
        steam_app_id: "976620",
        gog_app_id: None,
        my_games_folder: Some("Enderal Special Edition"),
        appdata_local_folder: None,
        appdata_roaming_folder: None,
        registry_path: r"Software\SureAI\Enderal SE",
        registry_value: "installed path",
        steam_folder: "Enderal Special Edition",
    },
    KnownGame {
        name: "Fallout 3",
        steam_app_id: "22300",
        gog_app_id: Some("1454315831"), // Fallout 3 GOTY
        my_games_folder: Some("Fallout3"),
        appdata_local_folder: Some("Fallout3"),
        appdata_roaming_folder: None,
        registry_path: r"Software\Bethesda Softworks\Fallout3",
        registry_value: "Installed Path",
        steam_folder: "Fallout 3",
    },
    KnownGame {
        name: "Fallout 4",
        steam_app_id: "377160",
        gog_app_id: None,
        my_games_folder: Some("Fallout4"),
        appdata_local_folder: Some("Fallout4"),
        appdata_roaming_folder: None,
        registry_path: r"Software\Bethesda Softworks\Fallout4",
        registry_value: "Installed Path",
        steam_folder: "Fallout 4",
    },
    KnownGame {
        name: "Fallout 4 VR",
        steam_app_id: "611660",
        gog_app_id: None,
        my_games_folder: Some("Fallout4VR"),
        appdata_local_folder: None,
        appdata_roaming_folder: None,
        registry_path: r"Software\Bethesda Softworks\Fallout 4 VR",
        registry_value: "Installed Path",
        steam_folder: "Fallout 4 VR",
    },
    KnownGame {
        name: "Fallout New Vegas",
        steam_app_id: "22380",
        gog_app_id: Some("1454587428"), // Fallout NV Ultimate
        my_games_folder: Some("FalloutNV"),
        appdata_local_folder: Some("FalloutNV"),
        appdata_roaming_folder: None,
        registry_path: r"Software\Bethesda Softworks\FalloutNV",
        registry_value: "Installed Path",
        steam_folder: "Fallout New Vegas",
    },
    KnownGame {
        name: "Morrowind",
        steam_app_id: "22320",
        gog_app_id: Some("1440163901"), // Morrowind GOTY
        my_games_folder: Some("Morrowind"),
        appdata_local_folder: None,
        appdata_roaming_folder: None,
        registry_path: r"Software\Bethesda Softworks\Morrowind",
        registry_value: "Installed Path",
        steam_folder: "Morrowind",
    },
    KnownGame {
        name: "Oblivion",
        steam_app_id: "22330",
        gog_app_id: Some("1458058109"), // Oblivion GOTY Deluxe
        my_games_folder: Some("Oblivion"),
        appdata_local_folder: Some("Oblivion"),
        appdata_roaming_folder: None,
        registry_path: r"Software\Bethesda Softworks\Oblivion",
        registry_value: "Installed Path",
        steam_folder: "Oblivion",
    },
    KnownGame {
        name: "Skyrim",
        steam_app_id: "72850",
        gog_app_id: None, // Not on GOG
        my_games_folder: Some("Skyrim"),
        appdata_local_folder: Some("Skyrim"),
        appdata_roaming_folder: None,
        registry_path: r"Software\Bethesda Softworks\Skyrim",
        registry_value: "Installed Path",
        steam_folder: "Skyrim",
    },
    KnownGame {
        name: "Skyrim Special Edition",
        steam_app_id: "489830",
        gog_app_id: Some("1711230643"), // Skyrim SE Anniversary Edition
        my_games_folder: Some("Skyrim Special Edition"),
        appdata_local_folder: Some("Skyrim Special Edition"),
        appdata_roaming_folder: None,
        registry_path: r"Software\Bethesda Softworks\Skyrim Special Edition",
        registry_value: "Installed Path",
        steam_folder: "Skyrim Special Edition",
    },
    KnownGame {
        name: "Skyrim VR",
        steam_app_id: "611670",
        gog_app_id: None,
        my_games_folder: Some("Skyrim VR"),
        appdata_local_folder: None,
        appdata_roaming_folder: None,
        registry_path: r"Software\Bethesda Softworks\Skyrim VR",
        registry_value: "Installed Path",
        steam_folder: "Skyrim VR",
    },
    KnownGame {
        name: "Starfield",
        steam_app_id: "1716740",
        gog_app_id: None,
        my_games_folder: Some("Starfield"),
        appdata_local_folder: None,
        appdata_roaming_folder: None,
        registry_path: r"Software\Bethesda Softworks\Starfield",
        registry_value: "Installed Path",
        steam_folder: "Starfield",
    },
    // CD Projekt RED Games
    KnownGame {
        name: "The Witcher 3",
        steam_app_id: "292030",
        gog_app_id: Some("1495134320"), // Witcher 3 GOTY
        my_games_folder: Some("The Witcher 3"),
        appdata_local_folder: None,
        appdata_roaming_folder: None,
        registry_path: r"Software\CD Projekt Red\The Witcher 3",
        registry_value: "InstallFolder",
        steam_folder: "The Witcher 3 Wild Hunt",
    },
    KnownGame {
        name: "Cyberpunk 2077",
        steam_app_id: "1091500",
        gog_app_id: Some("1423049311"),
        my_games_folder: None,
        appdata_local_folder: Some("CD Projekt Red/Cyberpunk 2077"),
        appdata_roaming_folder: None,
        registry_path: r"Software\CD Projekt Red\Cyberpunk 2077",
        registry_value: "InstallFolder",
        steam_folder: "Cyberpunk 2077",
    },
    // Other popular moddable games
    KnownGame {
        name: "Baldur's Gate 3",
        steam_app_id: "1086940",
        gog_app_id: Some("1456460669"),
        my_games_folder: None,
        appdata_local_folder: Some("Larian Studios/Baldur's Gate 3"),
        appdata_roaming_folder: None,
        registry_path: r"Software\Larian Studios\Baldur's Gate 3",
        registry_value: "InstallDir",
        steam_folder: "Baldurs Gate 3",
    },
];

/// Find a known game by Steam App ID
pub fn find_by_steam_id(app_id: &str) -> Option<&'static KnownGame> {
    let normalized_id = normalize_steam_id(app_id);
    KNOWN_GAMES.iter().find(|g| g.steam_app_id == normalized_id)
}

/// Find a known game by GOG App ID
pub fn find_by_gog_id(app_id: &str) -> Option<&'static KnownGame> {
    KNOWN_GAMES
        .iter()
        .find(|g| g.gog_app_id == Some(app_id))
}

/// Find a known game by name (case-insensitive)
pub fn find_by_name(name: &str) -> Option<&'static KnownGame> {
    let name_lower = name.to_lowercase();
    KNOWN_GAMES
        .iter()
        .find(|g| g.name.to_lowercase() == name_lower)
}

/// Normalize Steam App IDs that have equivalent variants.
fn normalize_steam_id(app_id: &str) -> &str {
    match app_id {
        // Fallout 3 often appears as GOTY App ID 22370.
        // We treat it as Fallout 3 for shared metadata/registry mapping.
        "22370" => "22300",
        _ => app_id,
    }
}

#[cfg(test)]
mod tests {
    use super::find_by_steam_id;

    #[test]
    fn fallout_3_goty_alias_maps_to_fallout_3() {
        let game = find_by_steam_id("22370").expect("22370 should map to Fallout 3");
        assert_eq!(game.name, "Fallout 3");
        assert_eq!(game.steam_app_id, "22300");
    }
}
