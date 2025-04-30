#!/bin/bash
# -------------------------------------------------------------------
# sky-tex-opti.sh
# Sky Texture Optimizer functions for NaK
# -------------------------------------------------------------------

# Download and install sky-tex-opti
download_sky_tex_opti() {
    log_info "Downloading sky-tex-opti"

    print_section "Download Sky Texture Optimizer"

    # Check for dependencies
    if ! check_download_dependencies; then
        handle_error "Required dependencies missing for download" false
        return 1
    fi

    # Create directory - use a "downloaded_tools" folder in the NaK directory
    local tools_dir="$SCRIPT_DIR/downloaded_tools"
    local sky_tex_dir="$tools_dir/sky-tex-opti"

    # Create the directory structure
    mkdir -p "$tools_dir"

    # Clean up previous installation if it exists
    if [ -d "$sky_tex_dir" ]; then
        echo -e "Removing previous installation..."
        rm -rf "$sky_tex_dir"
    fi

    mkdir -p "$sky_tex_dir"

    echo -e "Fetching latest release from GitHub..."
    log_info "Fetching latest release from GitHub"

    # Get latest release info
    local release_info
    if ! release_info=$(curl -s https://api.github.com/repos/BenHUET/sky-tex-opti/releases/latest); then
        handle_error "Failed to fetch release information from GitHub." false
        return 1
    fi

    # Extract download URL for the binary
    local download_url
    download_url=$(echo "$release_info" | jq -r '.assets[] | select(.name | test("sky-tex-opti_linux-x64.zip")) | .browser_download_url')

    if [ -z "$download_url" ]; then
        handle_error "No suitable Linux asset found in the latest release." false
        return 1
    fi

    local filename=$(basename "$download_url")
    local version=$(echo "$release_info" | jq -r .tag_name)

    echo -e "Found latest version: ${color_green}$version${color_reset}"
    echo -e "Downloading: ${color_blue}$filename${color_reset}"

    # Create a temporary directory for the download
    local temp_dir=$(mktemp -d)
    local temp_file="$temp_dir/$filename"

    # Download the file
    if ! curl -L -o "$temp_file" "$download_url"; then
        # Clean up temp dir if download fails
        rm -rf "$temp_dir"
        handle_error "Failed to download sky-tex-opti." false
        return 1
    fi

    # Extract the ZIP file
    echo -e "Extracting to $sky_tex_dir..."
    if ! unzip -o "$temp_file" -d "$temp_dir"; then
        # Clean up temp dir if extraction fails
        rm -rf "$temp_dir"
        handle_error "Failed to extract sky-tex-opti archive." false
        return 1
    fi

    # Based on the screenshot, the files are in a subfolder named sky-tex-opti_linux-x64
    # Copy all files from the extracted subfolder to our destination
    cp -r "$temp_dir/sky-tex-opti_linux-x64/"* "$sky_tex_dir/"

    # Make executable - use correct path to the binary
    if [ -f "$sky_tex_dir/sky-tex-opti" ]; then
        chmod +x "$sky_tex_dir/sky-tex-opti"
        echo -e "\n${color_green}Sky Texture Optimizer v$version has been successfully downloaded!${color_reset}"
        log_info "Successfully installed sky-tex-opti v$version to $sky_tex_dir"

        # Clean up temp directory immediately after successful installation
        echo -e "Cleaning up temporary files..."
        rm -rf "$temp_dir"

        return 0
    else
        # List extracted contents to help diagnose before cleaning up
        echo -e "Extracted contents:"
        ls -la "$temp_dir"
        if [ -d "$temp_dir/sky-tex-opti_linux-x64" ]; then
            ls -la "$temp_dir/sky-tex-opti_linux-x64"
        fi

        # Clean up temp dir if executable not found
        rm -rf "$temp_dir"
        handle_error "Could not find sky-tex-opti executable in the extracted files." false
        return 1
    fi
}

# Display information about sky-tex-opti
show_sky_tex_opti_info() {
    print_section "Sky Texture Optimizer Information"

    echo -e "${color_header}What is Sky Texture Optimizer?${color_reset}"
    echo -e "Sky Texture Optimizer (sky-tex-opti) is a tool that optimizes Skyrim textures"
    echo -e "to improve performance while maintaining visual quality."
    echo -e ""

    echo -e "${color_header}Features:${color_reset}"
    echo -e "• Reduces texture sizes to save VRAM and improve FPS"
    echo -e "• Works with Mod Organizer 2 profiles"
    echo -e "• Preserves texture quality where it matters most"
    echo -e "• Customizable optimization settings"
    echo -e ""

    echo -e "${color_header}Usage Instructions:${color_reset}"
    echo -e "1. You will be prompted for your MO2 profile path"
    echo -e "   This is the folder containing your modlist.txt file, typically located at:"
    echo -e "   ${color_blue}[MO2 Installation]/profiles/[Your Profile Name]${color_reset}"
    echo -e ""
    echo -e "2. You will then be asked for an output directory"
    echo -e "   This is where optimized textures will be saved"
    echo -e ""
    echo -e "3. The process may take a long time depending on how many texture mods you have"
    echo -e ""

    echo -e "${color_header}After Optimization:${color_reset}"
    echo -e "• Create a new mod in MO2 named something like 'Optimized Textures'"
    echo -e "• Copy the contents of the output directory into this mod"
    echo -e "• Place this mod at the bottom of your load order to override other textures"
    echo -e ""

    echo -e "${color_yellow}Note: This tool will download the latest version each time you run it${color_reset}"

    pause "Press any key to continue to the Sky Texture Optimizer..."
}

# Run sky-tex-opti with user-provided parameters
run_sky_tex_opti() {
    print_section "Run Sky Texture Optimizer"

    # Always download the latest version
    echo -e "${color_yellow}Downloading the latest version of Sky Texture Optimizer...${color_reset}"
    download_sky_tex_opti

    # Use downloaded_tools folder inside NaK directory
    local tools_dir="$SCRIPT_DIR/downloaded_tools"
    local sky_tex_dir="$tools_dir/sky-tex-opti"
    local sky_tex_bin="$sky_tex_dir/sky-tex-opti"

    # Check if download was successful
    if [ ! -f "$sky_tex_bin" ]; then
        handle_error "Failed to download Sky Texture Optimizer." false
        return 1
    fi

    # Get the MO2 profile path
    echo -e "${color_header}MO2 Profile Path${color_reset}"
    echo -e "Enter the path to your Mod Organizer 2 profile directory."
    echo -e "Example: ${color_blue}$HOME/ModOrganizer2/profiles/My Skyrim Profile${color_reset}"
    read_with_tab_completion "MO2 profile path" "" "mo2_profile_path"

    if [ -z "$mo2_profile_path" ]; then
        handle_error "No profile path specified." false
        return 1
    fi

    # Get the output path
    echo -e "\n${color_header}Output Path${color_reset}"
    echo -e "Enter the path where optimized textures will be saved."
    echo -e "Example: ${color_blue}$HOME/SkyrimOptimizedTextures${color_reset}"
    read_with_tab_completion "Output path" "$HOME/SkyrimOptimizedTextures" "output_path"

    if [ -z "$output_path" ]; then
        handle_error "No output path specified." false
        return 1
    fi

    # Create the output directory if it doesn't exist
    if [ ! -d "$output_path" ]; then
        echo -e "Output directory doesn't exist. Creating it..."
        if ! mkdir -p "$output_path"; then
            handle_error "Failed to create output directory: $output_path" false
            return 1
        fi
    fi

    # Run sky-tex-opti
    echo -e "\n${color_header}Running Sky Texture Optimizer${color_reset}"
    echo -e "${color_yellow}This process may take a long time depending on the number of mods and textures.${color_reset}\n"

    cd "$sky_tex_dir" || {
        handle_error "Failed to change to sky-tex-opti directory." false
        return 1
    }

    # Run the tool with the provided parameters
    ./sky-tex-opti --profile "$mo2_profile_path" --output "$output_path" --settings default.json
    local result=$?

    if [ $result -eq 0 ]; then
        echo -e "\n${color_green}Texture optimization completed successfully!${color_reset}"
        echo -e "Optimized textures are available at: ${color_blue}$output_path${color_reset}"
        echo -e "Just drag the folder mods folder of MO2. Make sure it's the parent folder of textures not just the folder called textures."
        return 0
    else
        handle_error "Sky Texture Optimizer failed with status $result." false
        return 1
    fi
}

# Add to main menu function
sky_tex_opti_main() {
    # Show information about sky-tex-opti first
    show_sky_tex_opti_info

    # Then run the tool
    run_sky_tex_opti
}
