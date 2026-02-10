//! NaK - Linux Mod Manager Tool
//!
//! Library crate for NaK core functionality, shared between GUI and CLI.
//!
//! # Features
//!
//! - `core` (always available): game detection, Proton detection, Steam paths,
//!   config management, logging
//! - `full` (default): adds installers, deps, marketplace, updater, nxm,
//!   networking, archive handling, and all heavy dependencies

// Core modules - always available
pub mod config;
pub mod game_finder;
pub mod logging;
pub mod steam;
#[cfg(any(feature = "installer", feature = "full"))]
pub mod runtime_wrap;

// Installer modules - available with "installer" or "full" feature
// Provides prefix setup, winetricks, .NET installation, registry settings
#[cfg(any(feature = "installer", feature = "full"))]
pub mod deps;
#[cfg(any(feature = "installer", feature = "full"))]
pub mod installers;

// Full modules - only available with the "full" feature
#[cfg(feature = "full")]
pub mod github;
#[cfg(feature = "full")]
pub mod marketplace;
#[cfg(feature = "full")]
pub mod nxm;
#[cfg(feature = "full")]
pub mod updater;
#[cfg(feature = "full")]
pub mod utils;
