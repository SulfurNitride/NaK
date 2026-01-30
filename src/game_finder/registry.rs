//! Wine registry parsing utilities
//!
//! Parses Wine registry files (system.reg, user.reg) to find game install paths.

use std::fs;
use std::path::{Path, PathBuf};

use crate::logging::log_warning;

/// Read a registry value from a Wine prefix registry file
///
/// # Arguments
/// * `prefix_path` - Path to the Wine prefix (containing system.reg, user.reg)
/// * `key_path` - Registry key path (e.g., "Software\\Bethesda Softworks\\Skyrim")
/// * `value_name` - Name of the value to read (e.g., "Installed Path")
///
/// Returns the value as a string, or None if not found
pub fn read_registry_value(
    prefix_path: &Path,
    key_path: &str,
    value_name: &str,
) -> Option<String> {
    // Try system.reg first (HKEY_LOCAL_MACHINE)
    let system_reg = prefix_path.join("system.reg");
    if let Some(value) = read_value_from_reg_file(&system_reg, key_path, value_name) {
        return Some(value);
    }

    // Try user.reg (HKEY_CURRENT_USER)
    let user_reg = prefix_path.join("user.reg");
    if let Some(value) = read_value_from_reg_file(&user_reg, key_path, value_name) {
        return Some(value);
    }

    None
}

/// Read a value from a specific .reg file
fn read_value_from_reg_file(reg_file: &Path, key_path: &str, value_name: &str) -> Option<String> {
    let content = fs::read_to_string(reg_file).ok()?;

    // Convert the key path to Wine's format
    // Wine uses lowercase keys with escaped backslashes
    // e.g., [Software\\Bethesda Softworks\\Skyrim] becomes [software\\\\bethesda softworks\\\\skyrim]
    let wine_key = format!(
        "[{}]",
        key_path.to_lowercase().replace('\\', "\\\\")
    );

    // Also try with the Wow6432Node variant for 32-bit apps on 64-bit Wine
    let wine_key_wow64 = format!(
        "[software\\\\wow6432node\\\\{}]",
        key_path
            .strip_prefix("Software\\")
            .unwrap_or(key_path)
            .to_lowercase()
            .replace('\\', "\\\\")
    );

    // Find the key section and extract the value
    for key_to_find in [&wine_key, &wine_key_wow64] {
        if let Some(value) = find_value_in_content(&content, key_to_find, value_name) {
            return Some(value);
        }
    }

    None
}

/// Find a value within registry file content
fn find_value_in_content(content: &str, key: &str, value_name: &str) -> Option<String> {
    let mut in_target_key = false;
    let value_name_lower = value_name.to_lowercase();

    for line in content.lines() {
        let trimmed = line.trim();

        // Check for key header
        if trimmed.starts_with('[') && trimmed.ends_with(']') {
            in_target_key = trimmed.to_lowercase() == key.to_lowercase();
            continue;
        }

        // If we're in the target key, look for the value
        if in_target_key {
            // Empty line or new section means we've left the key
            if trimmed.is_empty() {
                continue;
            }
            if trimmed.starts_with('[') {
                break;
            }

            // Parse value line: "ValueName"="value" or @="default value"
            if let Some((name, value)) = parse_reg_value_line(trimmed) {
                if name.to_lowercase() == value_name_lower {
                    return Some(value);
                }
            }
        }
    }

    None
}

/// Parse a registry value line like "ValueName"="value"
fn parse_reg_value_line(line: &str) -> Option<(String, String)> {
    // Format: "name"="value" or "name"=dword:00000000 or @="default"
    let line = line.trim();

    // Find the = separator
    let eq_pos = line.find('=')?;
    let (name_part, value_part) = line.split_at(eq_pos);
    let value_part = &value_part[1..]; // Skip the '='

    // Extract name (remove quotes)
    let name = if name_part == "@" {
        "@".to_string()
    } else {
        name_part.trim().trim_matches('"').to_string()
    };

    // Extract value
    let value = if value_part.starts_with('"') {
        // String value - need to handle escapes
        parse_quoted_reg_value(value_part)?
    } else if value_part.starts_with("dword:") {
        // DWORD value - convert to decimal string
        let hex = value_part.strip_prefix("dword:")?;
        let num = u32::from_str_radix(hex, 16).ok()?;
        num.to_string()
    } else {
        // Other types - return as-is
        value_part.to_string()
    };

    Some((name, value))
}

/// Parse a quoted registry value, handling Wine's escape sequences
fn parse_quoted_reg_value(s: &str) -> Option<String> {
    let s = s.trim();
    if !s.starts_with('"') {
        return None;
    }

    let mut result = String::new();
    let chars = s[1..].chars();
    let mut prev_was_backslash = false;

    for c in chars {
        if prev_was_backslash {
            match c {
                'n' => result.push('\n'),
                'r' => result.push('\r'),
                't' => result.push('\t'),
                '\\' => result.push('\\'),
                '"' => result.push('"'),
                _ => {
                    result.push('\\');
                    result.push(c);
                }
            }
            prev_was_backslash = false;
        } else if c == '\\' {
            prev_was_backslash = true;
        } else if c == '"' {
            break; // End of string
        } else {
            result.push(c);
        }
    }

    Some(result)
}

/// Convert a Wine path (Z:\path\to\file) to a Linux path
pub fn wine_path_to_linux(wine_path: &str) -> Option<PathBuf> {
    let path = wine_path.trim();

    // Handle Z: drive (maps to /)
    if path.starts_with("Z:") || path.starts_with("z:") {
        let linux_path = path[2..].replace('\\', "/");
        return Some(PathBuf::from(linux_path));
    }

    // Handle C: drive (maps to prefix/drive_c)
    // Note: This requires knowing the prefix path, so we can't convert it here
    // For now, we'll just return None for C: paths
    if path.starts_with("C:") || path.starts_with("c:") {
        log_warning(&format!(
            "Cannot convert C: drive path without prefix: {}",
            path
        ));
        return None;
    }

    None
}

/// Check if a Wine prefix contains a specific game by registry key
pub fn has_game_registry(
    prefix_path: &Path,
    registry_path: &str,
    registry_value: &str,
) -> bool {
    read_registry_value(prefix_path, registry_path, registry_value).is_some()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_reg_value_line() {
        let (name, value) =
            parse_reg_value_line(r#""Installed Path"="Z:\\mnt\\games\\Skyrim""#).unwrap();
        assert_eq!(name, "Installed Path");
        assert_eq!(value, r"Z:\mnt\games\Skyrim");
    }

    #[test]
    fn test_wine_path_to_linux() {
        let linux = wine_path_to_linux(r"Z:\mnt\games\Skyrim").unwrap();
        assert_eq!(linux, PathBuf::from("/mnt/games/Skyrim"));
    }
}
