#!/bin/bash
# -------------------------------------------------------------------
# vdf.sh
# Steam VDF file manipulation for MO2 Helper
# Automated version for programmatic use
# -------------------------------------------------------------------

# Include portable Python setup
source "$SCRIPT_DIR/lib/portablepython.sh"

# Function to install the vdf Python package
install_vdf_package() {
    log_info "Installing vdf Python package"

    # Get the portable Python binary
    local python_bin=$(get_portable_python)
    if [ $? -ne 0 ]; then
        handle_error "Failed to set up portable Python" false
        return 1
    fi

    # Create the pip directory if it doesn't exist
    local pip_dir="$PORTABLE_PYTHON_EXTRACT_DIR/bin"
    if [ ! -f "$pip_dir/pip" ]; then
        log_warning "Pip not found in expected location, installing pip"
        $python_bin -m ensurepip --upgrade
    fi

    # Install vdf package
    log_info "Installing vdf Python package..."
    if ! $python_bin -m pip install vdf; then
        handle_error "Failed to install vdf Python package" false
        return 1
    fi

    log_info "vdf Python package installed successfully"
    return 0
}

# Function to check if vdf package is installed
check_vdf_installed() {
    log_info "Checking if vdf Python package is installed"

    # Get the portable Python binary
    local python_bin=$(get_portable_python)
    if [ $? -ne 0 ]; then
        handle_error "Failed to set up portable Python" false
        return 1
    fi

    # Check if the vdf package is installed
    if ! $python_bin -c "import vdf" 2>/dev/null; then
        log_warning "vdf Python package is not installed"
        return 1
    fi

    log_info "vdf Python package is already installed"
    return 0
}

# Function to add a non-Steam game to Steam
# Usage: add_game_to_steam "Game Name" "/path/to/exe" "/path/to/start_dir" ["/path/to/icon"]
add_game_to_steam() {
    local game_name="$1"
    local exe_path="$2"
    local start_dir="$3"
    local icon_path="${4:-}"

    # Validate input parameters
    if [ -z "$game_name" ] || [ -z "$exe_path" ]; then
        log_error "Missing required parameters for add_game_to_steam"
        return 1
    fi

    # Set default start directory if not provided
    if [ -z "$start_dir" ]; then
        start_dir=$(dirname "$exe_path")
    fi

    log_info "Adding non-Steam game to Steam: $game_name ($exe_path)"

    # Check if vdf is installed, install if needed
    if ! check_vdf_installed; then
        if ! install_vdf_package; then
            return 1
        fi
    fi

    # Get the Python binary
    local python_bin=$(get_portable_python)
    if [ $? -ne 0 ]; then
        handle_error "Failed to set up portable Python" false
        return 1
    fi

    # Get Steam root
    local steam_root=$(get_steam_root)
    if [ -z "$steam_root" ]; then
        handle_error "Could not find Steam root directory" false
        return 1
    fi

    # Create a temporary Python script to add the game
    local temp_script=$(mktemp)
    TEMP_FILES+=("$temp_script")

    cat > "$temp_script" << 'EOF'
import sys
import os
import vdf
import time

# Command line arguments
steam_root = sys.argv[1]
game_name = sys.argv[2]
exe_path = sys.argv[3]
start_dir = sys.argv[4]
icon_path = sys.argv[5] if len(sys.argv) > 5 else ""

# Define the path to the shortcuts.vdf file
shortcuts_path = os.path.join(steam_root, "userdata")

# Check if userdata directory exists
if not os.path.exists(shortcuts_path):
    print(f"Error: userdata directory not found at {shortcuts_path}")
    sys.exit(1)

# Find user directories
user_dirs = [d for d in os.listdir(shortcuts_path) if os.path.isdir(os.path.join(shortcuts_path, d))]
if not user_dirs:
    print(f"Error: No user directories found in {shortcuts_path}")
    sys.exit(1)

# Generate a unique app ID for the game (this is a simple hash function)
def generate_app_id(name, exe):
    return abs(hash(name + exe)) % 1000000000

app_id = generate_app_id(game_name, exe_path)

# Flag to track if we modified any files
modified = False

# Process each user directory
for user_dir in user_dirs:
    shortcuts_file = os.path.join(shortcuts_path, user_dir, "config", "shortcuts.vdf")

    # Check if shortcuts.vdf exists, create directories if needed
    if not os.path.exists(os.path.dirname(shortcuts_file)):
        os.makedirs(os.path.dirname(shortcuts_file), exist_ok=True)

    # Try to load existing shortcuts.vdf if it exists
    data = {"shortcuts": {}}
    if os.path.exists(shortcuts_file):
        try:
            with open(shortcuts_file, 'rb') as f:
                data = vdf.binary_load(f)
                if data is None:
                    data = {"shortcuts": {}}
                elif "shortcuts" not in data:
                    data["shortcuts"] = {}
        except Exception as e:
            print(f"Warning: Could not read {shortcuts_file}: {e}")
            # Create a new file if we can't read the existing one
            data = {"shortcuts": {}}

    # Check if the game is already in the shortcuts
    game_already_added = False
    for idx, shortcut in data["shortcuts"].items():
        if "AppName" in shortcut and shortcut["AppName"] == game_name:
            print(f"Game '{game_name}' is already in shortcuts.vdf for user {user_dir}")
            game_already_added = True
            break

    if game_already_added:
        continue

    # Add the new game
    shortcut_index = len(data["shortcuts"])

    # Create the new shortcut entry
    data["shortcuts"][str(shortcut_index)] = {
        "appid": app_id,
        "AppName": game_name,
        "Exe": f'"{exe_path}"',
        "StartDir": f'"{start_dir}"',
        "icon": icon_path,
        "ShortcutPath": "",
        "LaunchOptions": "",
        "IsHidden": 0,
        "AllowDesktopConfig": 1,
        "AllowOverlay": 1,
        "OpenVR": 0,
        "LastPlayTime": int(time.time())
    }

    # Write the updated shortcuts.vdf file
    try:
        with open(shortcuts_file, 'wb') as f:
            vdf.binary_dump(data, f)
        print(f"Added '{game_name}' to shortcuts.vdf for user {user_dir}")
        modified = True
    except Exception as e:
        print(f"Error writing to {shortcuts_file}: {e}")
        continue

if modified:
    print(f"Game '{game_name}' added to Steam with AppID {app_id}")
    print(f"APPID:{app_id}")  # Print in a format that can be easily extracted
    sys.exit(0)
else:
    print("No changes were made to any shortcuts.vdf files")
    sys.exit(1)
EOF

    # Run the Python script
    log_info "Running VDF editor script to add game to Steam"
    local output
    if ! output=$($python_bin "$temp_script" "$steam_root" "$game_name" "$exe_path" "$start_dir" "$icon_path"); then
        handle_error "Failed to add game to Steam" false
        return 1
    fi

    # Extract the appid from the output
    local appid
    appid=$(echo "$output" | grep "APPID:" | cut -d':' -f2)

    if [ -n "$appid" ]; then
        log_info "Game was added to Steam with AppID: $appid"
        echo "$appid"  # Return the AppID for programmatic use
    else
        log_warning "Game was added but couldn't determine AppID"
    fi

    return 0
}

# Import games from a CSV file
# Usage: import_games_from_csv "/path/to/csv"
import_games_from_csv() {
    local csv_path="$1"

    if [ -z "$csv_path" ]; then
        log_error "No CSV file path provided"
        return 1
    fi

    if [ ! -f "$csv_path" ]; then
        log_error "CSV file not found: $csv_path"
        return 1
    fi

    log_info "Importing games from CSV file: $csv_path"

    # Check if vdf is installed, install if needed
    if ! check_vdf_installed; then
        if ! install_vdf_package; then
            return 1
        fi
    fi

    # Get the Python binary
    local python_bin=$(get_portable_python)
    if [ $? -ne 0 ]; then
        handle_error "Failed to set up portable Python" false
        return 1
    fi

    # Get Steam root
    local steam_root=$(get_steam_root)
    if [ -z "$steam_root" ]; then
        handle_error "Could not find Steam root directory" false
        return 1
    fi

    # Create a temporary Python script to import the games
    local temp_script=$(mktemp)
    TEMP_FILES+=("$temp_script")

    cat > "$temp_script" << 'EOF'
import sys
import os
import csv
import vdf
import time

# Command line arguments
steam_root = sys.argv[1]
csv_path = sys.argv[2]

# Define the path to the shortcuts.vdf file
shortcuts_path = os.path.join(steam_root, "userdata")

# Check if userdata directory exists
if not os.path.exists(shortcuts_path):
    print(f"Error: userdata directory not found at {shortcuts_path}")
    sys.exit(1)

# Find user directories
user_dirs = [d for d in os.listdir(shortcuts_path) if os.path.isdir(os.path.join(shortcuts_path, d))]
if not user_dirs:
    print(f"Error: No user directories found in {shortcuts_path}")
    sys.exit(1)

# Read games from CSV file
games = []
try:
    with open(csv_path, 'r', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            game = {
                'name': row.get('name', '').strip(),
                'exe': row.get('exe', '').strip(),
                'start_dir': row.get('start_dir', os.path.dirname(row.get('exe', ''))).strip(),
                'icon': row.get('icon', '').strip()
            }
            if game['name'] and game['exe']:  # Only add if name and exe are provided
                games.append(game)
except Exception as e:
    print(f"Error reading CSV file: {e}")
    sys.exit(1)

if not games:
    print("No valid games found in the CSV file")
    sys.exit(1)

print(f"Found {len(games)} games in the CSV file")

# Generate app IDs for the games
app_ids = {}
for game in games:
    app_id = abs(hash(game['name'] + game['exe'])) % 1000000000
    game['appid'] = app_id
    app_ids[game['name']] = app_id

# Process each user directory
for user_dir in user_dirs:
    shortcuts_file = os.path.join(shortcuts_path, user_dir, "config", "shortcuts.vdf")

    # Check if shortcuts.vdf exists, create directories if needed
    if not os.path.exists(os.path.dirname(shortcuts_file)):
        os.makedirs(os.path.dirname(shortcuts_file), exist_ok=True)

    # Try to load existing shortcuts.vdf if it exists
    data = {"shortcuts": {}}
    if os.path.exists(shortcuts_file):
        try:
            with open(shortcuts_file, 'rb') as f:
                data = vdf.binary_load(f)
                if data is None:
                    data = {"shortcuts": {}}
                elif "shortcuts" not in data:
                    data["shortcuts"] = {}
        except Exception as e:
            print(f"Warning: Could not read {shortcuts_file}: {e}")
            # Create a new file if we can't read the existing one
            data = {"shortcuts": {}}

    # Start with the highest existing index
    next_index = 0
    if data["shortcuts"]:
        next_index = max(int(idx) for idx in data["shortcuts"].keys()) + 1

    # Add each game
    games_added = 0
    for game in games:
        # Check if the game is already in shortcuts
        game_already_added = False
        for shortcut in data["shortcuts"].values():
            if "AppName" in shortcut and shortcut["AppName"] == game['name']:
                print(f"Game '{game['name']}' is already in shortcuts.vdf for user {user_dir}")
                game_already_added = True
                break

        if game_already_added:
            continue

        # Add the new game
        data["shortcuts"][str(next_index)] = {
            "appid": game['appid'],
            "AppName": game['name'],
            "Exe": f'"{game["exe"]}"',
            "StartDir": f'"{game["start_dir"]}"',
            "icon": game['icon'],
            "ShortcutPath": "",
            "LaunchOptions": "",
            "IsHidden": 0,
            "AllowDesktopConfig": 1,
            "AllowOverlay": 1,
            "OpenVR": 0,
            "LastPlayTime": int(time.time())
        }
        next_index += 1
        games_added += 1

    # Write the updated shortcuts.vdf file if we added any games
    if games_added > 0:
        try:
            with open(shortcuts_file, 'wb') as f:
                vdf.binary_dump(data, f)
            print(f"Added {games_added} games to shortcuts.vdf for user {user_dir}")
        except Exception as e:
            print(f"Error writing to {shortcuts_file}: {e}")
            continue

# Print app IDs in a format that can be easily parsed
for name, app_id in app_ids.items():
    print(f"APPID:{name}:{app_id}")

print("Import completed!")
sys.exit(0)
EOF

    # Run the Python script
    log_info "Running VDF editor script to import games from CSV"
    local output
    if ! output=$($python_bin "$temp_script" "$steam_root" "$csv_path"); then
        handle_error "Failed to import games from CSV" false
        return 1
    fi

    # Extract app IDs from the output
    local app_ids=()
    while read -r line; do
        if [[ "$line" =~ ^APPID: ]]; then
            app_ids+=("$line")
        fi
    done <<< "$output"

    log_info "Imported games from CSV with ${#app_ids[@]} app IDs"

    # Return the app IDs (for programmatic use)
    for id in "${app_ids[@]}"; do
        echo "$id"
    done

    return 0
}

# Create a sample CSV file for game import
# Usage: create_sample_csv "/path/to/output.csv"
create_sample_csv() {
    local csv_path="$1"

    if [ -z "$csv_path" ]; then
        csv_path="$HOME/mo2helper_games.csv"
    fi

    log_info "Creating sample CSV file at: $csv_path"

    # Create the CSV file
    cat > "$csv_path" << 'EOF'
name,exe,start_dir,icon
"Mod Organizer 2","/path/to/ModOrganizer.exe","/path/to/MO2/directory","/path/to/icon.ico"
"Example Game","/path/to/game.exe","/path/to/game/directory",""
EOF

    log_info "Sample CSV created at: $csv_path"

    return 0
}

# Export all current non-Steam games to CSV
# Usage: export_games_to_csv "/path/to/output.csv"
export_games_to_csv() {
    local csv_path="$1"

    if [ -z "$csv_path" ]; then
        csv_path="$HOME/exported_steam_games.csv"
    fi

    log_info "Exporting current non-Steam games to CSV: $csv_path"

    # Check if vdf is installed, install if needed
    if ! check_vdf_installed; then
        if ! install_vdf_package; then
            return 1
        fi
    fi

    # Get the Python binary
    local python_bin=$(get_portable_python)
    if [ $? -ne 0 ]; then
        handle_error "Failed to set up portable Python" false
        return 1
    fi

    # Get Steam root
    local steam_root=$(get_steam_root)
    if [ -z "$steam_root" ]; then
        handle_error "Could not find Steam root directory" false
        return 1
    fi

    # Create a temporary Python script to export the games
    local temp_script=$(mktemp)
    TEMP_FILES+=("$temp_script")

    cat > "$temp_script" << 'EOF'
import sys
import os
import csv
import vdf

# Command line arguments
steam_root = sys.argv[1]
csv_path = sys.argv[2]

# Define the path to the shortcuts.vdf file
shortcuts_path = os.path.join(steam_root, "userdata")

# Check if userdata directory exists
if not os.path.exists(shortcuts_path):
    print(f"Error: userdata directory not found at {shortcuts_path}")
    sys.exit(1)

# Find user directories
user_dirs = [d for d in os.listdir(shortcuts_path) if os.path.isdir(os.path.join(shortcuts_path, d))]
if not user_dirs:
    print(f"Error: No user directories found in {shortcuts_path}")
    sys.exit(1)

# Collect all games
all_games = []
unique_games = set()  # To track unique game names

for user_dir in user_dirs:
    shortcuts_file = os.path.join(shortcuts_path, user_dir, "config", "shortcuts.vdf")

    if not os.path.exists(shortcuts_file):
        continue

    try:
        with open(shortcuts_file, 'rb') as f:
            data = vdf.binary_load(f)
            if data is None or "shortcuts" not in data:
                continue

            for shortcut in data["shortcuts"].values():
                if "AppName" in shortcut and shortcut["AppName"] not in unique_games:
                    # Clean up the path strings (remove quotes)
                    exe = shortcut.get("Exe", "").strip('"')
                    start_dir = shortcut.get("StartDir", "").strip('"')

                    game = {
                        'name': shortcut["AppName"],
                        'exe': exe,
                        'start_dir': start_dir,
                        'icon': shortcut.get("icon", ""),
                        'app_id': shortcut.get("appid", "")
                    }
                    all_games.append(game)
                    unique_games.add(shortcut["AppName"])
    except Exception as e:
        print(f"Warning: Could not read {shortcuts_file}: {e}")
        continue

if not all_games:
    print("No games found in shortcuts.vdf files")
    sys.exit(1)

print(f"Found {len(all_games)} unique games")

# Write the games to a CSV file
try:
    with open(csv_path, 'w', newline='') as csvfile:
        fieldnames = ['name', 'exe', 'start_dir', 'icon', 'app_id']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for game in all_games:
            writer.writerow(game)

    print(f"Successfully exported {len(all_games)} games to {csv_path}")
    sys.exit(0)
except Exception as e:
    print(f"Error writing to CSV file: {e}")
    sys.exit(1)
EOF

    # Run the Python script
    log_info "Running VDF editor script to export games to CSV"
    if ! $python_bin "$temp_script" "$steam_root" "$csv_path"; then
        handle_error "Failed to export games to CSV" false
        return 1
    fi

    log_info "Games were exported to: $csv_path"

    return 0
}

# Get the AppID for a non-Steam game by name
# Usage: get_game_appid "Game Name"
get_game_appid() {
    local game_name="$1"

    if [ -z "$game_name" ]; then
        log_error "No game name provided"
        return 1
    fi

    log_info "Looking up AppID for game: $game_name"

    # Check if vdf is installed, install if needed
    if ! check_vdf_installed; then
        if ! install_vdf_package; then
            return 1
        fi
    fi

    # Get the Python binary
    local python_bin=$(get_portable_python)
    if [ $? -ne 0 ]; then
        handle_error "Failed to set up portable Python" false
        return 1
    fi

    # Get Steam root
    local steam_root=$(get_steam_root)
    if [ -z "$steam_root" ]; then
        handle_error "Could not find Steam root directory" false
        return 1
    fi

    # Create a temporary Python script to find the AppID
    local temp_script=$(mktemp)
    TEMP_FILES+=("$temp_script")

    cat > "$temp_script" << 'EOF'
import sys
import os
import vdf

# Command line arguments
steam_root = sys.argv[1]
game_name = sys.argv[2]

# Define the path to the shortcuts.vdf file
shortcuts_path = os.path.join(steam_root, "userdata")

# Check if userdata directory exists
if not os.path.exists(shortcuts_path):
    print(f"Error: userdata directory not found at {shortcuts_path}")
    sys.exit(1)

# Find user directories
user_dirs = [d for d in os.listdir(shortcuts_path) if os.path.isdir(os.path.join(shortcuts_path, d))]
if not user_dirs:
    print(f"Error: No user directories found in {shortcuts_path}")
    sys.exit(1)

# Look for the game in all user directories
found = False
for user_dir in user_dirs:
    shortcuts_file = os.path.join(shortcuts_path, user_dir, "config", "shortcuts.vdf")

    if not os.path.exists(shortcuts_file):
        continue

    try:
        with open(shortcuts_file, 'rb') as f:
            data = vdf.binary_load(f)
            if data is None or "shortcuts" not in data:
                continue

            for shortcut in data["shortcuts"].values():
                if "AppName" in shortcut and shortcut["AppName"] == game_name:
                    if "appid" in shortcut:
                        print(f"APPID:{shortcut['appid']}")
                        found = True
                        sys.exit(0)
    except Exception as e:
        print(f"Warning: Could not read {shortcuts_file}: {e}")
        continue

if not found:
    print(f"Game '{game_name}' not found in Steam")
    sys.exit(1)
EOF

    # Run the Python script
    log_info "Running VDF editor script to get game AppID"
    local output
    if ! output=$($python_bin "$temp_script" "$steam_root" "$game_name"); then
        log_warning "Game not found in Steam: $game_name"
        return 1
    fi

    # Extract AppID from the output
    local appid
    appid=$(echo "$output" | grep "APPID:" | cut -d':' -f2)

    if [ -n "$appid" ]; then
        log_info "Found AppID for game '$game_name': $appid"
        echo "$appid"
        return 0
    else
        log_warning "AppID not found for game: $game_name"
        return 1
    fi
}
