//! NaK - Linux Mod Manager Tool
//!
//! Library crate for NaK core functionality, shared between GUI and CLI.
//! Note: UI module is only available in the GUI binary, not here.

pub mod config;
pub mod deps;
pub mod github;
pub mod game_finder;
pub mod installers;
pub mod logging;
pub mod marketplace;
pub mod nxm;
pub mod steam;
pub mod updater;
pub mod utils;
