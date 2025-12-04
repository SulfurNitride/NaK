//! Wine/Proton related functionality

mod proton;
mod prefixes;
mod deps;

pub use proton::{ProtonInfo, ProtonFinder, GithubRelease, set_active_proton};
pub use proton::{fetch_ge_releases, download_ge_proton, delete_ge_proton};
pub use proton::{fetch_cachyos_releases, download_cachyos_proton, delete_cachyos_proton};
pub use prefixes::{NakPrefix, PrefixManager};
pub use deps::{DependencyManager, ensure_winetricks, ensure_cabextract, check_command_available};
