//! Wine prefix management

use std::path::PathBuf;
use std::fs;

#[derive(Clone)]
#[allow(dead_code)]
pub struct NakPrefix {
    pub name: String,
    pub path: PathBuf,
    pub is_orphaned: bool,
}

#[allow(dead_code)]
pub struct PrefixManager {
    prefixes_root: PathBuf,
}

#[allow(dead_code)]
impl PrefixManager {
    pub fn new() -> Self {
        let home = std::env::var("HOME").expect("Failed to get HOME");
        Self {
            prefixes_root: PathBuf::from(format!("{}/NaK/Prefixes", home)),
        }
    }

    /// Scans for NaK prefixes in ~/NaK/Prefixes
    pub fn scan_prefixes(&self) -> Vec<NakPrefix> {
        let mut prefixes = Vec::new();

        if !self.prefixes_root.exists() {
            return prefixes;
        }

        if let Ok(entries) = fs::read_dir(&self.prefixes_root) {
            for entry in entries.flatten() {
                let path = entry.path();
                if !path.is_dir() { continue; }

                let name = entry.file_name().to_string_lossy().to_string();

                // Check for orphan status
                let link = path.join("manager_link");
                let mut is_orphaned = false;
                if link.is_symlink() {
                    if !link.exists() { // link.exists() follows the link; false if broken
                        is_orphaned = true;
                    }
                }

                prefixes.push(NakPrefix {
                    name,
                    path: path.join("pfx"), // Points to the pfx inside
                    is_orphaned,
                });
            }
        }

        // Sort by name
        prefixes.sort_by(|a, b| a.name.cmp(&b.name));
        prefixes
    }

    pub fn delete_prefix(&self, name: &str) -> std::io::Result<()> {
        let path = self.prefixes_root.join(name);
        if path.exists() {
            fs::remove_dir_all(path)?;
        }
        Ok(())
    }

    pub fn get_unique_prefix_name(&self, base_name: &str) -> String {
        if !self.prefixes_root.exists() {
            return base_name.to_string();
        }

        let mut name = base_name.to_string();
        let mut counter = 2;

        while self.prefixes_root.join(&name).exists() {
            name = format!("{}_{}", base_name, counter);
            counter += 1;
        }
        name
    }
}
