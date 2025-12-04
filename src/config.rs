use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

#[derive(Serialize, Deserialize, Default, Clone)]
pub struct AppConfig {
    pub selected_proton: Option<String>,
    pub active_nxm_prefix: Option<String>,
}

impl AppConfig {
    fn get_path() -> PathBuf {
        let home = std::env::var("HOME").expect("Failed to get HOME");
        PathBuf::from(format!("{}/NaK/config.json", home))
    }

    pub fn load() -> Self {
        let path = Self::get_path();
        if path.exists() {
            if let Ok(content) = fs::read_to_string(&path) {
                if let Ok(config) = serde_json::from_str(&content) {
                    return config;
                }
            }
        }
        Self::default()
    }

    pub fn save(&self) {
        let path = Self::get_path();
        // Ensure parent dir exists
        if let Some(parent) = path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        if let Ok(json) = serde_json::to_string_pretty(self) {
            let _ = fs::write(path, json);
        }
    }
}
