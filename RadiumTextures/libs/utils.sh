#!/bin/bash

# --- Utility Functions ---

# Set open file limit to avoid "too many open files" errors
set_file_limits() {
    echo "Setting file descriptor limits to avoid 'too many open files' errors..."
    # Try to increase the file descriptor limit
    if ! ulimit -n 100000 2>/dev/null; then
        echo "Warning: Failed to set ulimit -n to 100000. Current limit: $(ulimit -n)"
        echo "This may cause 'too many open files' errors during extraction."
        echo "You might need to run with sudo or adjust system limits in /etc/security/limits.conf"
    else
        echo "Successfully set file descriptor limit to $(ulimit -n)"
    fi
}

# Improved Progress Bar Function
better_progress_bar() {
    local current=$1
    local total=$2
    local width=50
    local title="${3:-Progress}"

    # Calculate percentage and filled width
    local pct=0
    if [ "$total" -gt 0 ]; then
        pct=$((current * 100 / total))
    fi
    local filled=0
    if [ "$total" -gt 0 ]; then
        filled=$((width * current / total))
    fi

    # Create the bar
    local bar=""
    if [ "$filled" -gt 0 ]; then
        bar=$(printf '=%.0s' $(seq 1 $filled))
    fi
    local space=""
    if [ "$width" -gt "$filled" ]; then
        space=$(printf ' %.0s' $(seq 1 $((width - filled))))
    fi

    # Print the bar with a clean format and clear the line first
    printf "\\033[K%-15s [%s%s] %3d%% (%d/%d)\\r" "$title:" "$bar" "$space" "$pct" "$current" "$total"
}

# Update progress function
update_progress() {
    local CURRENT="${1:-0}"
    local TOTAL="${2:-100}"

    # Ensure variables are integers
    CURRENT=$(($CURRENT + 0))
    TOTAL=$(($TOTAL + 0))

    # Prevent division by zero
    if [ "$TOTAL" -le 0 ]; then
        TOTAL=100
    fi

    # Calculate percentage
    local PERCENT=0
    if [ "$CURRENT" -ge 0 ] && [ "$TOTAL" -gt 0 ]; then
        PERCENT=$((CURRENT * 100 / TOTAL))
    fi

    # Sanity check on percentage
    if [ "$PERCENT" -lt 0 ]; then
        PERCENT=0
    fi
    if [ "$PERCENT" -gt 100 ]; then
        PERCENT=100
    fi

    better_progress_bar "$PERCENT" 100 "VRAMr Progress"
    PROGRESS="$PERCENT"
}

# Flush Function - Forces disk writes to complete
flush() {
    sync
    sleep 1
}

# Create atomic increment function - thread-safe counter
atomic_increment() {
    local lockfile="$1.lock"
    local increment_val="${2:-1}"

    (
        flock -x 200
        current=$(cat "$1" 2>/dev/null || echo 0)
        echo $((current + increment_val)) > "$1"
    ) 200>"$lockfile"
}

# Function to generate mod order CSV using PowerShell
generate_mod_order_csv() {
    if [ ! -f "$VRAMR_TEMP/ActiveModListOrder.csv" ]; then
        echo "No mod order CSV found. Checking for PowerShell script generation capability..."

        # Check if we have a working PowerShell command
        if [ -n "$PWSH_CMD" ] && [ -x "$PWSH_CMD" ]; then
            echo "Running external PowerShell script to generate mod load order CSV..."

            # --- Determine MO2 Profile Path ---
            # Assuming standard MO2 structure: /path/to/ModlistName/mods
            MO2_BASE_PATH=""
            PROFILE_NAME=""
            PROFILE_PATH=""
            MODLIST_FILE=""
            can_determine_profile=0

            if [ -n "$MODS_DIR" ] && [[ "$MODS_DIR" == *"/mods" ]]; then
                MO2_BASE_PATH=$(dirname "$MODS_DIR")
                PROFILE_NAME=$(basename "$MO2_BASE_PATH")
                PROFILE_PATH="$MO2_BASE_PATH/profiles/$PROFILE_NAME"
                MODLIST_FILE="$PROFILE_PATH/modlist.txt"
                if [ -d "$PROFILE_PATH" ] && [ -f "$MODLIST_FILE" ]; then
                    echo "DEBUG: Determined Profile Path: $PROFILE_PATH"
                    echo "DEBUG: Found Modlist File: $MODLIST_FILE"
                    can_determine_profile=1
                else
                    echo "WARNING: Could not find profile directory or modlist.txt at expected path: $PROFILE_PATH" | tee -a "$LOG_FILE"
                fi
            else
                echo "WARNING: MODS_DIR ('$MODS_DIR') does not seem to be a standard MO2 mods directory. Cannot automatically determine profile path." | tee -a "$LOG_FILE"
            fi
            # --- End Profile Path Determination ---

            if [ $can_determine_profile -eq 1 ]; then
                # Define arguments for PowerShell
                MODS_DIR_ARG="$MODS_DIR"
                PROFILE_PATH_ARG="$PROFILE_PATH"
                OUTPUT_CSV_ARG="$VRAMR_TEMP/ActiveModListOrder.csv"

                # --- Create Temporary PowerShell Script ---
                TEMP_PS1_FILE=$(mktemp --tmpdir="$TEMP_DIR" generate_modlist_XXXXXX.ps1)
                cat > "$TEMP_PS1_FILE" << 'EOF_PWSH'
# PowerShell script to generate mod load order CSV
# Arguments are accessed via $args array

# --- Assign arguments from $args ---
if ($args.Count -lt 3) {
    Write-Error "Insufficient arguments provided to PowerShell script. Expected 3, got $($args.Count)."
    exit 1
}
$modsPath = $args[0]      # Passed from MODS_DIR_ARG
$profilePath = $args[1]   # Passed from PROFILE_PATH_ARG
$outputCsvPath = $args[2]  # Passed from OUTPUT_CSV_ARG

# --- Paths derived from arguments ---
$modListFile = Join-Path $profilePath "modlist.txt"

# --- Read Mod Activation Order (modlist.txt) ---
Write-Host "Reading active mod order from $modListFile (bottom-to-top priority)..."
$activeModsData = [System.Collections.Generic.List[PSCustomObject]]::new()

if (Test-Path $modListFile) {
    $modListContent = Get-Content $modListFile
    # Reverse the order of lines to process from bottom to top for priority
    [array]::Reverse($modListContent)

    $currentIndex = 0
    $actualModsFound = 0
    foreach ($line in $modListContent) {
        # Process only ACTIVE mods (start with '+'), ignore inactive ('-') and separators
        if ($line.StartsWith("+")) {
            $modName = $line.Substring(1) # Remove the '+'

            # Ensure a directory for this mod name exists
            $potentialModPath = Join-Path $modsPath $modName
            if (Test-Path $potentialModPath -PathType Container) {
                # Store mod info directly
                $modData = [PSCustomObject]@{
                    ModActivationIndex = $currentIndex
                    ModName            = $modName
                    IsModActive        = $true
                    ModPath            = $potentialModPath # Use the confirmed path
                }
                $activeModsData.Add($modData)

                $currentIndex++
                $actualModsFound++ # Count only actual mod directories found
            } else {
                Write-Host "  - Skipping '+$($modName)' from modlist.txt: Directory not found at '$($potentialModPath)'" -ForegroundColor Gray
            }
        }
    }
    Write-Host "Found $($actualModsFound) active mod directories matching entries in modlist.txt."
} else {
    Write-Warning "Modlist file not found at '$modListFile'. Cannot determine mod activation status or order."
}
# --- End Mod Activation Order ---

# --- Sort and Export Results ---
Write-Host "Sorting results by activation index (0 = highest priority)..."
# Sort directly by the ModActivationIndex (which is already bottom-up)
$sortedResults = $activeModsData | Sort-Object ModActivationIndex

Write-Host "Exporting $($sortedResults.Count) results to $outputCsvPath..."
if ($sortedResults.Count -gt 0) {
    # Select only the desired columns for the final output
    $sortedResults | Select-Object ModActivationIndex, ModName, IsModActive, ModPath | Export-Csv -Path $outputCsvPath -NoTypeInformation
    Write-Host "Export complete."
} else {
    Write-Host "No active mods found or processed. CSV not created."
}
EOF_PWSH
                # --- End Temporary PowerShell Script ---

                # Execute the temporary PowerShell script using -File
                echo "Executing temporary PowerShell script: $TEMP_PS1_FILE"
                "$PWSH_CMD" -NoProfile -File "$TEMP_PS1_FILE" "$MODS_DIR_ARG" "$PROFILE_PATH_ARG" "$OUTPUT_CSV_ARG"
                PWSH_EXIT_CODE=$?

                if [ $PWSH_EXIT_CODE -ne 0 ]; then
                    echo "ERROR: PowerShell script execution failed with exit code $PWSH_EXIT_CODE." | tee -a "$LOG_FILE"
                    # Decide if this is fatal or just a warning
                fi
            else
                echo "WARNING: Unable to determine profile path. Mod load order CSV generation skipped." | tee -a "$LOG_FILE"
            fi
        else
            echo "WARNING: No working PowerShell command found. Cannot generate mod load order CSV." | tee -a "$LOG_FILE"
        fi
    else
        echo "Found existing mod order CSV at $VRAMR_TEMP/ActiveModListOrder.csv"
    fi

    # Debug: Check CSV status before copy choice
    echo "DEBUG: Checking for CSV at '$VRAMR_TEMP/ActiveModListOrder.csv'"
    if [ -f "$VRAMR_TEMP/ActiveModListOrder.csv" ]; then
        echo "DEBUG: CSV Found. Will attempt prioritized copy."
    else
        echo "DEBUG: CSV NOT Found. Will use simple parallel copy."
    fi
    echo "DEBUG: Value of VRAMR_TEMP is '$VRAMR_TEMP'"
    echo "DEBUG: Value of PWSH_CMD is '$PWSH_CMD'"
}
