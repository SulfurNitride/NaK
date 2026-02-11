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
    if is_flatpak() {
        // In Flatpak, umu-run must run on the host via flatpak-spawn --host.
        // Paths like /app/lib/... only exist inside the sandbox, so we need
        // the host-accessible copy that the wrapper script places in
        // ~/.local/share/fluorine/umu-run.
        let host_copy = env::var("XDG_DATA_HOME")
            .ok()
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                let home = env::var("HOME").unwrap_or_else(|_| "/tmp".to_string());
                PathBuf::from(home).join(".local/share")
            })
            .join("fluorine/umu-run");
        if host_copy.exists() {
            return Some(host_copy);
        }
        // Fall back to bare name for host PATH resolution.
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

/// Build a command to run `exe` with the given environment variables.
///
/// In Flatpak mode, `flatpak-spawn --host` is used and env vars are passed as
/// `--env=KEY=VALUE` flags (the host process does NOT inherit the sandbox env).
/// In steam-run mode, the command is wrapped with `steam-run`.
/// Otherwise the command runs directly.
pub fn build_command<S: AsRef<OsStr>>(
    exe: impl AsRef<OsStr>,
    envs: &[(&str, S)],
) -> Command {
    if use_steam_run() {
        let mut cmd = Command::new("steam-run");
        cmd.arg(exe.as_ref());
        for (key, value) in envs {
            cmd.env(key, value.as_ref());
        }
        return cmd;
    }
    if is_flatpak() {
        let mut cmd = Command::new("flatpak-spawn");
        cmd.arg("--host");
        for (key, value) in envs {
            cmd.arg(format!(
                "--env={}={}",
                key,
                value.as_ref().to_string_lossy()
            ));
        }
        cmd.arg(exe.as_ref());
        return cmd;
    }
    let mut cmd = Command::new(exe);
    for (key, value) in envs {
        cmd.env(key, value.as_ref());
    }
    cmd
}

/// Build a command with no extra environment variables.
///
/// Equivalent to `build_command(exe, &[] as &[(&str, &str)])`.
pub fn command_for(exe: impl AsRef<OsStr>) -> Command {
    build_command::<&str>(exe, &[])
}

pub fn bundled_umu_path_from_appdir(appdir: &Path) -> Option<PathBuf> {
    let path = appdir.join("umu-run");
    if path.exists() {
        Some(path)
    } else {
        None
    }
}
