//! Hand-rolled VDF (Valve Data Format) parser
//!
//! Parses VDF files like appmanifest_*.acf and libraryfolders.vdf
//! without external dependencies.

use std::collections::HashMap;

/// A VDF value - either a string or a nested object
#[derive(Debug, Clone)]
pub enum VdfValue {
    String(String),
    Object(HashMap<String, VdfValue>),
}

impl VdfValue {
    /// Get as string reference
    pub fn as_str(&self) -> Option<&str> {
        match self {
            VdfValue::String(s) => Some(s),
            VdfValue::Object(_) => None,
        }
    }

    /// Get as object reference
    pub fn as_object(&self) -> Option<&HashMap<String, VdfValue>> {
        match self {
            VdfValue::String(_) => None,
            VdfValue::Object(o) => Some(o),
        }
    }

    /// Get a nested value by key
    pub fn get(&self, key: &str) -> Option<&VdfValue> {
        self.as_object()?.get(key)
    }

    /// Get a string value by key
    pub fn get_str(&self, key: &str) -> Option<&str> {
        self.get(key)?.as_str()
    }
}

/// Parse a VDF file content into a root object
pub fn parse_vdf(content: &str) -> Option<VdfValue> {
    let mut chars = content.chars().peekable();
    parse_object(&mut chars)
}

/// Parse an object (including the root level)
fn parse_object<I: Iterator<Item = char>>(chars: &mut std::iter::Peekable<I>) -> Option<VdfValue> {
    let mut map = HashMap::new();

    loop {
        skip_whitespace_and_comments(chars);

        match chars.peek() {
            None => break,
            Some('}') => {
                chars.next();
                break;
            }
            Some('"') => {
                // Parse key
                let key = parse_quoted_string(chars)?;
                skip_whitespace_and_comments(chars);

                // Check what follows - string value or object
                match chars.peek() {
                    Some('"') => {
                        // String value
                        let value = parse_quoted_string(chars)?;
                        map.insert(key, VdfValue::String(value));
                    }
                    Some('{') => {
                        // Object value
                        chars.next(); // consume '{'
                        let value = parse_object(chars)?;
                        map.insert(key, value);
                    }
                    _ => return None, // Unexpected token
                }
            }
            _ => {
                // Skip unexpected characters
                chars.next();
            }
        }
    }

    Some(VdfValue::Object(map))
}

/// Parse a quoted string "..."
fn parse_quoted_string<I: Iterator<Item = char>>(
    chars: &mut std::iter::Peekable<I>,
) -> Option<String> {
    // Expect opening quote
    if chars.next() != Some('"') {
        return None;
    }

    let mut result = String::new();

    loop {
        match chars.next() {
            None => return None, // Unterminated string
            Some('"') => break,
            Some('\\') => {
                // Handle escape sequences
                match chars.next() {
                    Some('n') => result.push('\n'),
                    Some('t') => result.push('\t'),
                    Some('\\') => result.push('\\'),
                    Some('"') => result.push('"'),
                    Some(c) => {
                        result.push('\\');
                        result.push(c);
                    }
                    None => return None,
                }
            }
            Some(c) => result.push(c),
        }
    }

    Some(result)
}

/// Skip whitespace and // comments
fn skip_whitespace_and_comments<I: Iterator<Item = char>>(chars: &mut std::iter::Peekable<I>) {
    loop {
        // Skip whitespace
        while chars.peek().is_some_and(|c| c.is_whitespace()) {
            chars.next();
        }

        // Check for // comment
        // Need to peek ahead without cloning - consume first / and check second
        if chars.peek() == Some(&'/') {
            // Consume first /
            chars.next();
            if chars.peek() == Some(&'/') {
                // It's a comment - skip to end of line
                chars.next();
                while chars.peek().is_some_and(|c| *c != '\n') {
                    chars.next();
                }
                continue;
            }
            // Not a comment, but we consumed a '/' - this shouldn't happen in valid VDF
            // Just continue processing
        }

        break;
    }
}

/// Parse an appmanifest_*.acf file and extract app info
#[derive(Debug, Clone)]
pub struct AppManifest {
    pub app_id: String,
    pub name: String,
    pub install_dir: String,
    pub state_flags: u32,
}

impl AppManifest {
    /// Parse from VDF content
    pub fn from_vdf(content: &str) -> Option<Self> {
        let root = parse_vdf(content)?;
        let app_state = root.get("AppState")?;

        Some(Self {
            app_id: app_state.get_str("appid")?.to_string(),
            name: app_state.get_str("name")?.to_string(),
            install_dir: app_state.get_str("installdir")?.to_string(),
            state_flags: app_state.get_str("StateFlags")?.parse().unwrap_or(0),
        })
    }

    /// Check if the game is fully installed (StateFlags == 4)
    pub fn is_installed(&self) -> bool {
        self.state_flags == 4
    }
}

/// Parse libraryfolders.vdf and extract library paths
pub fn parse_library_folders(content: &str) -> Vec<String> {
    let mut paths = Vec::new();

    let Some(root) = parse_vdf(content) else {
        return paths;
    };

    let Some(library_folders) = root.get("libraryfolders").and_then(|v| v.as_object()) else {
        return paths;
    };

    // Library folders are keyed by index: "0", "1", "2", etc.
    for value in library_folders.values() {
        if let Some(path) = value.get_str("path") {
            paths.push(path.to_string());
        }
    }

    paths
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_appmanifest() {
        let content = r#"
"AppState"
{
    "appid"         "489830"
    "Universe"      "1"
    "name"          "Skyrim Special Edition"
    "StateFlags"    "4"
    "installdir"    "Skyrim Special Edition"
}
"#;
        let manifest = AppManifest::from_vdf(content).unwrap();
        assert_eq!(manifest.app_id, "489830");
        assert_eq!(manifest.name, "Skyrim Special Edition");
        assert_eq!(manifest.install_dir, "Skyrim Special Edition");
        assert!(manifest.is_installed());
    }

    #[test]
    fn test_parse_library_folders() {
        let content = r#"
"libraryfolders"
{
    "0"
    {
        "path"      "/home/user/.local/share/Steam"
        "label"     ""
    }
    "1"
    {
        "path"      "/mnt/games/SteamLibrary"
        "label"     "Games"
    }
}
"#;
        let paths = parse_library_folders(content);
        assert_eq!(paths.len(), 2);
        assert!(paths.contains(&"/home/user/.local/share/Steam".to_string()));
        assert!(paths.contains(&"/mnt/games/SteamLibrary".to_string()));
    }
}
