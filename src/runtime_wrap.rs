use std::env;
use std::ffi::OsStr;
use std::path::{Path, PathBuf};
use std::process::Command;

fn env_flag(name: &str) -> bool {
    matches!(
        env::var(name)
            .unwrap_or_default()
            .trim()
            .to_ascii_lowercase()
            .as_str(),
        "1" | "true" | "yes" | "on"
    )
}

pub fn use_steam_run() -> bool {
    env_flag("NAK_USE_STEAM_RUN")
}

pub fn use_umu_for_prefix() -> bool {
    env_flag("NAK_USE_UMU_FOR_PREFIX")
}

pub fn prefer_system_umu() -> bool {
    env_flag("NAK_PREFER_SYSTEM_UMU")
}

fn find_in_path(binary: &str) -> Option<PathBuf> {
    let path = env::var_os("PATH")?;
    env::split_paths(&path)
        .map(|entry| entry.join(binary))
        .find(|candidate| candidate.exists())
}

pub fn resolve_umu_run() -> Option<PathBuf> {
    // In Flatpak, umu-run must run on the host (it needs the Steam Runtime's
    // linker and 32-bit libs).  Return the bare name so command_for() wraps it
    // as `flatpak-spawn --host umu-run` and the host's PATH resolves it.
    if is_flatpak() {
        return Some(PathBuf::from("umu-run"));
    }

    let bundled = env::var("NAK_BUNDLED_UMU_RUN")
        .ok()
        .map(PathBuf::from)
        .filter(|p| p.exists());
    let system = find_in_path("umu-run");

    if prefer_system_umu() {
        system.or(bundled)
    } else {
        bundled.or(system)
    }
}

pub fn is_flatpak() -> bool {
    Path::new("/.flatpak-info").exists()
}

pub fn command_for(exe: impl AsRef<OsStr>) -> Command {
    if use_steam_run() {
        let mut cmd = Command::new("steam-run");
        cmd.arg(exe);
        return cmd;
    }
    // Inside a Flatpak sandbox, Proton's Wine binaries are linked against
    // the Steam Runtime's linker and can't execute directly.  Spawn them
    // on the host via the Flatpak portal instead.
    if is_flatpak() {
        let mut cmd = Command::new("flatpak-spawn");
        cmd.arg("--host").arg(exe);
        return cmd;
    }
    Command::new(exe)
}

pub fn bundled_umu_path_from_appdir(appdir: &Path) -> Option<PathBuf> {
    let path = appdir.join("umu-run");
    if path.exists() {
        Some(path)
    } else {
        None
    }
}
