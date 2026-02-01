//! NaK - Linux Mod Manager Tool
//!
//! A tool to help manage modding tools (MO2) on Linux via Proton/Wine.
//! Supports both GUI mode (default) and CLI mode for automation.

use std::path::PathBuf;
use std::sync::atomic::AtomicBool;
use std::sync::Arc;

use clap::{Parser, Subcommand};
use eframe::egui;

mod app;
mod ui;

use app::MyApp;
use nak_rust::installers::{setup_existing_mo2, TaskContext};
use nak_rust::logging::{init_logger, log_info};
use nak_rust::steam::{find_steam_protons, SteamProton};

/// NaK - Linux Mod Manager Tool
///
/// Run without arguments to launch the GUI.
/// Use subcommands for CLI automation.
#[derive(Parser)]
#[command(name = "nak")]
#[command(author = "NaK Team")]
#[command(version)]
#[command(about = "Linux mod manager setup tool - GUI and CLI")]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand)]
enum Commands {
    /// Set up an existing MO2 installation with Steam/Proton integration
    SetupMo2 {
        /// Path to the existing MO2 installation (directory containing ModOrganizer.exe)
        #[arg(short, long)]
        path: PathBuf,

        /// Name for the Steam shortcut (default: "Mod Organizer 2")
        #[arg(short, long, default_value = "Mod Organizer 2")]
        name: String,

        /// Proton version to use (name or index from --list-protons)
        #[arg(long)]
        proton: Option<String>,
    },

    /// List available Proton versions
    ListProtons,

    /// Check if Steam is properly detected
    CheckSteam,
}

fn main() -> eframe::Result<()> {
    // Initialize logging
    init_logger();

    // Parse CLI arguments
    let cli = Cli::parse();

    // If a subcommand was provided, run in CLI mode
    if let Some(command) = cli.command {
        log_info("NaK CLI mode starting...");

        match command {
            Commands::SetupMo2 { path, name, proton } => {
                setup_mo2_cli(path, name, proton);
            }
            Commands::ListProtons => {
                list_protons();
            }
            Commands::CheckSteam => {
                check_steam();
            }
        }

        // Return Ok for CLI mode (no GUI)
        return Ok(());
    }

    // No subcommand - run GUI mode
    log_info("NaK GUI starting...");

    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([720.0, 720.0])
            .with_min_inner_size([720.0, 720.0])
            .with_title("NaK"),
        ..Default::default()
    };

    eframe::run_native(
        "NaK",
        options,
        Box::new(|cc| {
            egui_extras::install_image_loaders(&cc.egui_ctx);
            Ok(Box::new(MyApp::default()))
        }),
    )
}

// ============================================================================
// CLI Functions
// ============================================================================

fn setup_mo2_cli(path: PathBuf, name: String, proton_arg: Option<String>) {
    println!("Setting up MO2 at: {}", path.display());
    println!("Steam shortcut name: {}", name);

    // Verify path exists
    if !path.exists() {
        eprintln!("Error: Path does not exist: {}", path.display());
        std::process::exit(1);
    }

    // Verify ModOrganizer.exe exists
    let mo2_exe = path.join("ModOrganizer.exe");
    if !mo2_exe.exists() {
        eprintln!("Error: ModOrganizer.exe not found at: {}", path.display());
        eprintln!("Please provide the path to an existing MO2 installation.");
        std::process::exit(1);
    }

    // Find available Protons
    let protons = find_steam_protons();
    if protons.is_empty() {
        eprintln!("Error: No compatible Proton versions found.");
        eprintln!("NaK requires Proton 10 or newer (GE-Proton10+, Proton Experimental, etc.)");
        std::process::exit(1);
    }

    // Select Proton
    let selected_proton: SteamProton = match proton_arg {
        Some(arg) => {
            // Try to find by name first
            if let Some(p) = protons.iter().find(|p| p.name.eq_ignore_ascii_case(&arg)) {
                p.clone()
            }
            // Try to parse as index
            else if let Ok(idx) = arg.parse::<usize>() {
                if idx < protons.len() {
                    protons[idx].clone()
                } else {
                    eprintln!("Error: Invalid Proton index: {}. Use 'nak list-protons' to see available options.", idx);
                    std::process::exit(1);
                }
            } else {
                eprintln!("Error: Proton '{}' not found. Use 'nak list-protons' to see available options.", arg);
                std::process::exit(1);
            }
        }
        None => {
            // Default to first (usually Proton Experimental or newest GE)
            println!("No Proton specified, using: {}", protons[0].name);
            protons[0].clone()
        }
    };

    println!("Using Proton: {}", selected_proton.name);
    println!();

    // Create a simple CLI task context
    let cancel_flag = Arc::new(AtomicBool::new(false));
    let ctx = TaskContext::new(
        |status| println!("[STATUS] {}", status),
        |log| println!("[LOG] {}", log),
        |progress| {
            let percent = (progress * 100.0) as u32;
            print!("\r[PROGRESS] {}%", percent);
            if percent >= 100 {
                println!();
            }
            use std::io::Write;
            let _ = std::io::stdout().flush();
        },
        cancel_flag.clone(),
    );

    // Handle Ctrl+C
    let cancel_flag_ctrlc = cancel_flag.clone();
    std::thread::spawn(move || {
        // Simple signal handling - in production use ctrlc crate
        let _ = cancel_flag_ctrlc;
    });

    // Run the setup
    match setup_existing_mo2(&name, path, &selected_proton, ctx) {
        Ok(result) => {
            println!();
            println!("Success! MO2 has been set up with Steam integration.");
            println!();
            println!("Steam AppID: {}", result.app_id);
            println!("Prefix path: {}", result.prefix_path.display());
            println!();
            println!("Please RESTART Steam to see the new shortcut in your library.");
        }
        Err(e) => {
            eprintln!();
            eprintln!("Error: {}", e);
            std::process::exit(1);
        }
    }
}

fn list_protons() {
    let protons = find_steam_protons();

    if protons.is_empty() {
        println!("No compatible Proton versions found.");
        println!("NaK requires Proton 10 or newer.");
        return;
    }

    println!("Available Proton versions:");
    println!();
    for (i, p) in protons.iter().enumerate() {
        let marker = if p.is_experimental { " [Experimental]" } else { "" };
        let source = if p.is_steam_proton { "Steam" } else { "Custom" };
        println!("  {:>2}. {} ({}){}",i, p.name, source, marker);
    }
    println!();
    println!("Use --proton <name> or --proton <index> to select a version.");
}

fn check_steam() {
    use nak_rust::steam;

    println!("Checking Steam installation...");
    println!();

    match steam::find_steam_path() {
        Some(path) => {
            println!("Steam found at: {}", path.display());

            // Check for Flatpak
            if path.to_string_lossy().contains(".var/app/com.valvesoftware.Steam") {
                println!("Steam type: Flatpak");
            } else {
                println!("Steam type: Native");
            }

            // List Protons
            let protons = find_steam_protons();
            println!("Compatible Protons: {}", protons.len());

            if protons.is_empty() {
                println!();
                println!("Warning: No Proton 10+ versions found.");
                println!("Install Proton Experimental or GE-Proton10+ to use NaK.");
            }
        }
        None => {
            println!("Steam not found!");
            println!();
            println!("NaK requires Steam to be installed.");
        }
    }
}
