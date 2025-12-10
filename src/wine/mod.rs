//! Wine/Proton related functionality

mod deps;
mod prefixes;
mod proton;

pub use deps::{check_command_available, ensure_cabextract, ensure_winetricks, DependencyManager};
pub use prefixes::{NakPrefix, PrefixManager};
pub use proton::{delete_cachyos_proton, download_cachyos_proton, fetch_cachyos_releases};
pub use proton::{delete_ge_proton, download_ge_proton, fetch_ge_releases};
pub use proton::{set_active_proton, GithubRelease, ProtonFinder, ProtonInfo};
