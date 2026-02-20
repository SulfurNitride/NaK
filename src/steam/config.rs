//! Steam config.vdf manipulation
//!
//! Handles setting Proton compatibility tools for non-Steam games.

use std::fs;
use std::path::Path;

use super::find_steam_path;

/// Set a Proton version as the compatibility tool for a non-Steam game
///
/// # Arguments
/// * `app_id` - The calculated AppID of the non-Steam game shortcut
/// * `proton_name` - The internal name of the Proton version (e.g., "proton_experimental", "proton_9", "GE-Proton9-20")
///
/// # Notes
/// Steam must be restarted for changes to take effect.
pub fn set_compat_tool(app_id: u32, proton_name: &str) -> Result<(), Box<dyn std::error::Error>> {
    // Validate proton_name to prevent VDF injection
    if proton_name.is_empty() || proton_name.contains('"') || proton_name.contains('\n') || proton_name.contains('\r') {
        return Err(format!("Invalid Proton name: {:?}", proton_name).into());
    }

    let steam_path = find_steam_path()
        .ok_or("Steam not found")?;

    let config_path = steam_path.join("config/config.vdf");

    if !config_path.exists() {
        return Err("Steam config.vdf not found".into());
    }

    let content = fs::read_to_string(&config_path)?;
    let app_id_str = app_id.to_string();

    // Check if app already has compat entry in CompatToolMapping section
    let already_in_compat = if let Some(compat_start) = content.find("\"CompatToolMapping\"") {
        let section = &content[compat_start..];
        if let Some(section_content) = find_section_content(section) {
            section_content.contains(&format!("\"{}\"", app_id_str))
        } else {
            false
        }
    } else {
        false
    };

    if already_in_compat {
        // Update existing entry
        return update_existing_compat_entry(&config_path, &content, &app_id_str, proton_name);
    }

    // Format matches actual config.vdf indentation
    let compat_entry = format!(
        "\t\t\t\t\t\"{}\"\n\t\t\t\t\t{{\n\t\t\t\t\t\t\"name\"\t\t\"{}\"\n\t\t\t\t\t\t\"config\"\t\t\"\"\n\t\t\t\t\t\t\"priority\"\t\t\"250\"\n\t\t\t\t\t}}",
        app_id_str, proton_name
    );

    // Find CompatToolMapping section and add entry
    let new_content = if content.contains("\"CompatToolMapping\"") {
        // Add to existing CompatToolMapping
        content.replace(
            "\"CompatToolMapping\"\n\t\t\t\t{",
            &format!("\"CompatToolMapping\"\n\t\t\t\t{{\n{}", compat_entry)
        )
    } else {
        // Need to add CompatToolMapping section
        let compat_section = format!(
            "\t\t\t\t\"CompatToolMapping\"\n\t\t\t\t{{\n{}\n\t\t\t\t}}",
            compat_entry
        );

        // Try to find "Software" > "Valve" > "Steam" section and add after its opening brace
        if let Some(pos) = content.find("\"Steam\"\n\t\t\t{") {
            let insert_pos = content[pos..].find('\n').map(|p| pos + p + 1);
            if let Some(insert_pos) = insert_pos {
                let (before, after) = content.split_at(insert_pos);
                format!("{}\n{}\n{}", before, compat_section, after)
            } else {
                return Err("Could not find insertion point in config.vdf".into());
            }
        } else {
            return Err("Could not find Steam section in config.vdf".into());
        }
    };

    // Check if anything changed
    if new_content == content {
        return Err("Failed to modify config.vdf - format mismatch".into());
    }

    // Backup original
    let backup_path = steam_path.join("config/config.vdf.nak.bak");
    fs::copy(&config_path, &backup_path)?;

    // Write new config
    fs::write(&config_path, &new_content)?;

    Ok(())
}

/// Find the content of a VDF section (between { and matching })
fn find_section_content(section: &str) -> Option<&str> {
    let start = section.find('{')?;
    let mut depth = 0;
    let mut end = start;

    // Use char_indices() so `i` is a byte offset, not a char count.
    // Using chars().enumerate() would give char counts, which break slicing on non-ASCII.
    for (i, c) in section[start..].char_indices() {
        match c {
            '{' => depth += 1,
            '}' => {
                depth -= 1;
                if depth == 0 {
                    end = start + i;
                    break;
                }
            }
            _ => {}
        }
    }

    if depth != 0 {
        return None; // unmatched braces
    }

    Some(&section[start..=end])
}

/// Update an existing compat tool entry
fn update_existing_compat_entry(
    config_path: &Path,
    content: &str,
    app_id_str: &str,
    proton_name: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    // Find the entry and update the "name" field
    let pattern = format!("\t\t\t\t\t\"{}\"\n\t\t\t\t\t{{\n", app_id_str);

    if let Some(start) = content.find(&pattern) {
        let after_start = &content[start..];

        // Find the "name" line and replace it
        if let Some(name_offset) = after_start.find("\"name\"") {
            let name_line_start = start + name_offset;
            let after_name = &content[name_line_start..];

            if let Some(line_end) = after_name.find('\n') {
                let old_line = &content[name_line_start..name_line_start + line_end];
                let new_line = format!("\"name\"\t\t\"{}\"", proton_name);

                let new_content = content.replace(old_line, &new_line);

                // Backup and write
                let steam_path = find_steam_path().ok_or("Steam not found")?;
                let backup_path = steam_path.join("config/config.vdf.nak.bak");
                fs::copy(config_path, &backup_path)?;
                fs::write(config_path, &new_content)?;

                return Ok(());
            }
        }
    }

    Err("Could not find entry to update".into())
}
