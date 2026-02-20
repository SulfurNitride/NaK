//! Known games configuration
//!
//! Contains metadata for games that NaK supports, including:
//! - Steam App ID
//! - GOG App ID
//! - Epic Games Store App Name (Legendary/Heroic internal identifier)
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
    /// GOG App ID (if available on GOG)
    pub gog_app_id: Option<&'static str>,
    /// Epic Games Store AppName / Legendary internal ID (if available on Epic)
    pub epic_app_id: Option<&'static str>,
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
        gog_app_id: Some("1708684988"), // Enderal: Forgotten Stories on GOG
        epic_app_id: None,
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
        gog_app_id: None, // Not on GOG (only original Enderal)
        epic_app_id: None,
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
        epic_app_id: Some("adeae8bbfc94427db57c7dfecce3f1d4"),
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
        gog_app_id: Some("1998527297"), // Fallout 4 GOTY on GOG
        epic_app_id: Some("61d52ce4d09d41e48800c22784d13ae8"),
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
        epic_app_id: None,
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
        epic_app_id: Some("5daeb974a22a435988892319b3a4f476"),
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
        epic_app_id: None, // On Epic but internal AppName not yet known
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
        epic_app_id: None, // On Epic but internal AppName not yet known
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
        gog_app_id: None, // Not on GOG (only SE/AE)
        epic_app_id: None, // Not on Epic (only SE/AE)
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
        gog_app_id: Some("1711230643"), // Skyrim SE on GOG
        epic_app_id: Some("ac82db5035584c7f8a2c548d98c86b2c"),
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
        epic_app_id: None,
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
        gog_app_id: None, // Xbox/Steam exclusive
        epic_app_id: None,
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
        epic_app_id: None,
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
        epic_app_id: None,
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
        epic_app_id: None,
        my_games_folder: None,
        appdata_local_folder: Some("Larian Studios/Baldur's Gate 3"),
        appdata_roaming_folder: None,
        registry_path: r"Software\Larian Studios\Baldur's Gate 3",
        registry_value: "InstallDir",
        steam_folder: "Baldurs Gate 3",
    },
];

/// Alternative GOG App IDs that should map to the same game.
/// Some games have multiple GOG product IDs (e.g. different editions).
const GOG_ID_ALIASES: &[(&str, &str)] = &[
    // Morrowind: Vortex uses 1435828767, NaK primary is 1440163901
    ("1435828767", "1440163901"),
    // Skyrim Anniversary Edition is a separate GOG product but same game as SE
    ("1801825368", "1711230643"),
];

/// Find a known game by Steam App ID
pub fn find_by_steam_id(app_id: &str) -> Option<&'static KnownGame> {
    let normalized_id = normalize_steam_id(app_id);
    KNOWN_GAMES.iter().find(|g| g.steam_app_id == normalized_id)
}

/// Find a known game by GOG App ID
pub fn find_by_gog_id(app_id: &str) -> Option<&'static KnownGame> {
    // Direct match first
    if let Some(game) = KNOWN_GAMES.iter().find(|g| g.gog_app_id == Some(app_id)) {
        return Some(game);
    }
    // Check aliases: resolve alternate GOG ID to primary, then look up
    for &(alias, primary) in GOG_ID_ALIASES {
        if app_id == alias {
            return KNOWN_GAMES.iter().find(|g| g.gog_app_id == Some(primary));
        }
    }
    None
}

/// Find a known game by Epic Games Store AppName (Legendary/Heroic internal ID)
pub fn find_by_epic_id(app_id: &str) -> Option<&'static KnownGame> {
    KNOWN_GAMES
        .iter()
        .find(|g| g.epic_app_id == Some(app_id))
}

/// Strip punctuation and collapse whitespace for fuzzy title matching.
fn normalize_for_matching(s: &str) -> String {
    s.chars()
        .map(|c| if c.is_alphanumeric() || c == ' ' { c } else { ' ' })
        .collect::<String>()
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

/// Find a known game by title, using fuzzy matching.
/// Strips common suffixes like "Game of the Year Edition" for comparison.
pub fn find_by_title(title: &str) -> Option<&'static KnownGame> {
    let title_lower = title.to_lowercase();

    // Exact match first
    if let Some(game) = KNOWN_GAMES.iter().find(|g| g.name.to_lowercase() == title_lower) {
        return Some(game);
    }

    // Check if the title starts with or contains a known game name
    // Sort by name length descending so "Skyrim Special Edition" matches before "Skyrim"
    let mut games_by_name_len: Vec<&KnownGame> = KNOWN_GAMES.iter().collect();
    games_by_name_len.sort_by(|a, b| b.name.len().cmp(&a.name.len()));

    // Normalize both title and game names: strip colons and extra whitespace for comparison
    let title_normalized = normalize_for_matching(&title_lower);

    for game in games_by_name_len {
        let game_lower = game.name.to_lowercase();
        let game_normalized = normalize_for_matching(&game_lower);

        // Direct containment (e.g. "Fallout 3: Game of the Year Edition" contains "Fallout 3")
        if title_lower.contains(&game_lower) {
            return Some(game);
        }

        // Normalized containment (e.g. "Fallout: New Vegas" normalized to "fallout new vegas"
        // matches game name "Fallout New Vegas" normalized to "fallout new vegas")
        if title_normalized.contains(&game_normalized) {
            return Some(game);
        }

        // After-colon match: "The Elder Scrolls III: Morrowind" -> check "Morrowind"
        if let Some(after_colon) = title_lower.split(':').nth(1) {
            let after_colon = after_colon.trim();
            if after_colon.starts_with(&game_lower) {
                return Some(game);
            }
        }
    }

    None
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
    use super::*;

    #[test]
    fn fallout_3_goty_alias_maps_to_fallout_3() {
        let game = find_by_steam_id("22370").expect("22370 should map to Fallout 3");
        assert_eq!(game.name, "Fallout 3");
        assert_eq!(game.steam_app_id, "22300");
    }

    #[test]
    fn find_by_epic_id_works() {
        let game = find_by_epic_id("ac82db5035584c7f8a2c548d98c86b2c")
            .expect("Should find Skyrim SE by Epic ID");
        assert_eq!(game.name, "Skyrim Special Edition");
    }

    #[test]
    fn gog_alias_maps_correctly() {
        // Skyrim Anniversary Edition GOG ID maps to Skyrim SE
        let game = find_by_gog_id("1801825368")
            .expect("Skyrim AE GOG ID should map to Skyrim SE");
        assert_eq!(game.name, "Skyrim Special Edition");
    }

    #[test]
    fn find_by_title_matches_full_titles() {
        let game = find_by_title("The Elder Scrolls III: Morrowind Game of the Year Edition")
            .expect("Should find Morrowind by full Epic title");
        assert_eq!(game.name, "Morrowind");
    }

    #[test]
    fn find_by_title_matches_colon_titles() {
        let game = find_by_title("The Elder Scrolls IV: Oblivion Game of the Year Edition")
            .expect("Should find Oblivion by full title");
        assert_eq!(game.name, "Oblivion");
    }

    #[test]
    fn find_by_title_prefers_longer_match() {
        let game = find_by_title("Skyrim Special Edition")
            .expect("Should find Skyrim SE, not Skyrim");
        assert_eq!(game.name, "Skyrim Special Edition");
    }

    #[test]
    fn find_by_title_fallout_nv() {
        let game = find_by_title("Fallout: New Vegas Ultimate Edition")
            .expect("Should find Fallout NV");
        assert_eq!(game.name, "Fallout New Vegas");
    }
}
