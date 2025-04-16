#!/bin/bash

# --- Configuration Variables ---
# Initialize Variables
SCRIPT_DIR="$(realpath "$(dirname "$0")")"
LIBS_DIR="$(dirname "$SCRIPT_DIR")"  # Parent directory of the script directory

# Create portable binaries directory
PORTABLE_DIR="$LIBS_DIR/portable"
mkdir -p "$PORTABLE_DIR"

# Use a temporary directory within the user-specified output path
TEMP_DIR=""
GPU_TO_USE="0" # Retained for potential use in optimisation step
PROGRESS=0
VERBOSE=0 # Set to 1 for more detailed output

# Portable binary paths
SQLITE_ZIP="sqlite-tools-linux-x64-3490100.zip"
SQLITE_URL="https://sqlite.org/2025/sqlite-tools-linux-x64-3490100.zip"
MAGICK_URL="https://imagemagick.org/archive/binaries/magick"
PORTABLE_SQLITE_BIN="$PORTABLE_DIR/sqlite3"
PORTABLE_MAGICK_BIN="$PORTABLE_DIR/magick"
# Texconv paths (Using no-deps version)
TEXCONV_URL="https://github.com/matyalatte/Texconv-Custom-DLL/releases/download/v0.4.1/TexconvCustomDLL-v0.4.1-Linux-no-deps.tar.bz2"
TEXCONV_ARCHIVE="TexconvCustomDLL-v0.4.1-Linux-no-deps.tar.bz2"
PORTABLE_TEXCONV_BIN="$PORTABLE_DIR/texconv"
# Hoolamike paths
HOOLAMIKE_URL="https://github.com/Niedzwiedzw/hoolamike/releases/download/v0.15.5/hoolamike-x86_64-unknown-linux-gnu.tar.gz"
HOOLAMIKE_ARCHIVE="hoolamike-x86_64-unknown-linux-gnu.tar.gz"
PORTABLE_HOOLAMIKE_BIN="$PORTABLE_DIR/hoolamike"
# PowerShell paths
PWSH_URL="https://github.com/PowerShell/PowerShell/releases/download/v7.5.0/powershell-7.5.0-linux-x64.tar.gz"
PWSH_ARCHIVE="powershell-7.5.0-linux-x64.tar.gz"
PWSH_PORTABLE_DIR="$PORTABLE_DIR/powershell_portable" # NEW: Define portable dir
PORTABLE_PWSH_BIN="$PWSH_PORTABLE_DIR/pwsh" # NEW: Define path within portable dir

# Command paths to be used (resolved later)
SQLITE_CMD=""
MAGICK_CMD="" # Primary tool for texture analysis
PORTABLE_FD_BIN="$PORTABLE_DIR/fd"
FD_CMD=""
TEXCONV_CMD="" # Fallback tool for texture analysis
HOOLAMIKE_CMD="" # BSA extraction tool
PWSH_CMD="" # PowerShell command (system or portable)

# --- Default Thread Count ---
# Get the number of processing units available
DEFAULT_THREADS=$(nproc 2>/dev/null || echo 4) # Default to 4 if nproc fails
THREAD_COUNT=$DEFAULT_THREADS

# --- Preset Values ---
DIFFUSE=2048
NORMAL=1024
PARALLAX=512
MATERIAL=512
PRESET="Optimum" # Placeholder

# --- Argument Parsing ---
parse_arguments() {
  while [[ $# -gt 0 ]]; do
      key="$1"
      case $key in
          -t|--threads)
          if [[ "$2" =~ ^[1-9][0-9]*$ ]]; then
              THREAD_COUNT="$2"
              shift # past argument
              shift # past value
          else
              echo "Error: --threads requires a positive integer argument." >&2
              exit 1
          fi
          ;;
          -v|--verbose)
          VERBOSE=1
          shift # past argument
          ;;
          # Additional arguments
          --game-dir)
          GAME_DIR="$2"; shift; shift ;;
          --mods-dir)
          MODS_DIR="$2"; shift; shift ;;
          --output-dir)
          VRAMR_TEMP="$2"; shift; shift ;;
          -h|--help)
          echo "Usage: $0 [options]"
          echo "Options:"
          echo "  -t, --threads NUM       Set number of parallel threads (default: $DEFAULT_THREADS)"
          echo "  -v, --verbose           Enable verbose output"
          echo "  --game-dir PATH         Set Skyrim Data directory"
          echo "  --mods-dir PATH         Set mods directory"
          echo "  --output-dir PATH       Set output directory"
          echo "  -h, --help              Show this help message"
          exit 0
          ;;
          *)
          # unknown option
          echo "Unknown option: $1" >&2
          echo "Use --help for usage information"
          exit 1
          ;;
      esac
  done
}

# Function to get input paths from user if not specified as arguments
get_user_paths() {
  if [ -z "$GAME_DIR" ]; then
      read -e -p "Enter path to Skyrim Data directory (e.g., /path/to/steamapps/common/Skyrim Special Edition/Data): " GAME_DIR
  fi

  if [ ! -d "$GAME_DIR" ]; then
      echo "ERROR: Skyrim Data directory not found: $GAME_DIR"
      exit 1
  fi
  # Ensure GAME_DIR is absolute
  GAME_DIR=$(realpath "$GAME_DIR")

  if [ -z "$MODS_DIR" ]; then
      read -e -p "Enter path to Mods directory (e.g., /path/to/MO2/mods or /path/to/Vortex/mods): " MODS_DIR
  fi

  if [ ! -d "$MODS_DIR" ]; then
      echo "Warning: Mods directory not found: $MODS_DIR. Proceeding without mod textures."
  fi
  # Ensure MODS_DIR is absolute if provided
  if [ -d "$MODS_DIR" ]; then
      MODS_DIR=$(realpath "$MODS_DIR")
  fi

  if [ -z "$VRAMR_TEMP" ]; then
      read -e -p "Enter path for VRAMr output directory (will be created if needed, e.g., ~/VRAMr_Output): " VRAMR_TEMP
  fi

  # Expand tilde
  VRAMR_TEMP="${VRAMR_TEMP/#\~/$HOME}"
  if [ -z "$VRAMR_TEMP" ]; then
      echo "ERROR: Output directory cannot be empty."
      exit 1
  fi

  # Ensure VRAMR_TEMP is absolute
  VRAMR_PARENT=$(dirname "$VRAMR_TEMP")
  VRAMR_PARENT=$(realpath -m "$VRAMR_PARENT")
  VRAMR_TEMP="$VRAMR_PARENT/$(basename "$VRAMR_TEMP")"

  # Define and create the main script temporary directory *after* VRAMR_TEMP is resolved
  TEMP_DIR="$VRAMR_TEMP/temp_script_files_$$" # Add PID for uniqueness

  # Create directories
  echo "Creating temporary script directory: $TEMP_DIR"
  mkdir -p "$TEMP_DIR"
  # Set TMPDIR environment variable to guide temporary file creation for child processes
  export TMPDIR="$TEMP_DIR"
  echo "INFO: Set TMPDIR environment variable to $TMPDIR"

  echo "Creating output directory structure in: $VRAMR_TEMP"
  mkdir -p "$VRAMR_TEMP" # Create base directory first
  if [ $? -ne 0 ]; then
      echo "ERROR: Could not create output directory: $VRAMR_TEMP"
      exit 1
  fi
  mkdir -p "$VRAMR_TEMP/logfiles"
  mkdir -p "$VRAMR_TEMP/Output/textures"

  # --- Logging Setup ---
  LOG_FILE="$VRAMR_TEMP/logfiles/VRAMr_Native.log"
  {
      echo "VRAMr Native Script Started: $(date)"
      echo "Output Folder: $VRAMR_TEMP"
      echo "Game Directory: $GAME_DIR"
      echo "Mods Directory: $MODS_DIR"
      echo "Threads: $THREAD_COUNT"
      echo "Preset: $PRESET (D:$DIFFUSE N:$NORMAL P:$PARALLAX M:$MATERIAL)"
  } > "$LOG_FILE"
}

# Initialize script by parsing arguments and getting paths
initialize_script() {
  parse_arguments "$@"

  echo "Using $THREAD_COUNT threads for parallel operations (Detected: $DEFAULT_THREADS)"
  if [ "$VERBOSE" -eq 1 ]; then
      echo "Verbose mode enabled."
  fi

  get_user_paths
}
