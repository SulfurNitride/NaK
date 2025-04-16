#!/bin/bash

# --- Dependency Resolution Function ---

# Find system binary or download/prepare portable binaries
resolve_dependencies() {
    echo "Resolving dependencies (sqlite3, texconv, magick, hoolamike, pwsh)..."

    # Ensure portable directory exists
    mkdir -p "$PORTABLE_DIR"
    echo "Using portable binaries directory: $PORTABLE_DIR"

    # --- Resolve SQLite ---
    SQLITE_CMD=$(command -v sqlite3)
    if [ -n "$SQLITE_CMD" ] && [ -x "$SQLITE_CMD" ]; then
        echo "Found system sqlite3: $SQLITE_CMD"
    else
        echo "System sqlite3 not found or not executable. Checking for portable version..."
        SQLITE_CMD="$PORTABLE_SQLITE_BIN"
        if [ ! -f "$SQLITE_CMD" ]; then
            echo "Portable SQLite binary not found. Downloading..."
            if command -v wget &>/dev/null; then
                wget -q "$SQLITE_URL" -O "$TEMP_DIR/$SQLITE_ZIP"
            elif command -v curl &>/dev/null; then
                curl -s "$SQLITE_URL" -o "$TEMP_DIR/$SQLITE_ZIP"
            else
                echo "ERROR: Neither wget nor curl found. Cannot download SQLite." | tee -a "$LOG_FILE"
                return 1
            fi

            if [ ! -f "$TEMP_DIR/$SQLITE_ZIP" ]; then
                 echo "ERROR: Failed to download SQLite zip file." | tee -a "$LOG_FILE"
                 return 1
            fi

            # Extract SQLite
            echo "Extracting SQLite binary..."
            mkdir -p "$TEMP_DIR/sqlite_extract"
            unzip -q "$TEMP_DIR/$SQLITE_ZIP" -d "$TEMP_DIR/sqlite_extract"
            # Find sqlite3 binary regardless of folder structure
            local SQLITE_EXTRACT=$(find "$TEMP_DIR/sqlite_extract" -name "sqlite3" -type f | head -n 1)
            if [ -n "$SQLITE_EXTRACT" ]; then
                cp "$SQLITE_EXTRACT" "$SQLITE_CMD"
                chmod +x "$SQLITE_CMD"
                echo "Portable SQLite binary extracted to $SQLITE_CMD"
            else
                echo "ERROR: Failed to find sqlite3 binary in the downloaded archive." | tee -a "$LOG_FILE"
                rm -rf "$TEMP_DIR/sqlite_extract" "$TEMP_DIR/$SQLITE_ZIP"
                return 1
            fi
            rm -rf "$TEMP_DIR/sqlite_extract" "$TEMP_DIR/$SQLITE_ZIP"
        else
             echo "Found portable SQLite binary: $SQLITE_CMD"
        fi

        # Verify portable executable status
        if [ ! -x "$SQLITE_CMD" ]; then
            echo "Making portable SQLite binary executable..."
            chmod +x "$SQLITE_CMD"
            if [ ! -x "$SQLITE_CMD" ]; then
                echo "ERROR: Could not make portable SQLite binary executable: $SQLITE_CMD" | tee -a "$LOG_FILE"
                return 1
            fi
        fi
    fi

    # --- Resolve Texconv (PRIMARY texture analysis tool) ---
    TEXCONV_CMD=$(command -v texconv)
    if [ -n "$TEXCONV_CMD" ] && [ -x "$TEXCONV_CMD" ]; then
        echo "Found system texconv: $TEXCONV_CMD"
    else
        echo "System texconv not found or not executable. Checking for portable version..."
        TEXCONV_CMD="$PORTABLE_TEXCONV_BIN"
        if [ ! -f "$TEXCONV_CMD" ]; then
            echo "Portable texconv binary not found. Downloading from $TEXCONV_URL..."

            # Make sure TEMP_DIR exists and is writable
            if [ ! -d "$TEMP_DIR" ]; then
                mkdir -p "$TEMP_DIR"
                echo "Created temporary directory: $TEMP_DIR"
            fi

            if ! [ -w "$TEMP_DIR" ]; then
                echo "WARNING: Temporary directory $TEMP_DIR is not writable!"
                # Try using user's home directory as a fallback
                TEMP_DIR="$HOME/.vramr_temp"
                mkdir -p "$TEMP_DIR"
                echo "Using alternate temporary directory: $TEMP_DIR"
            fi

            if command -v wget &>/dev/null; then
                wget -q "$TEXCONV_URL" -O "$TEMP_DIR/$TEXCONV_ARCHIVE"
            elif command -v curl &>/dev/null; then
                # curl needs -L to follow redirects, -s for silent, -o for output file
                curl -s -L "$TEXCONV_URL" -o "$TEMP_DIR/$TEXCONV_ARCHIVE"
            else
                echo "ERROR: Neither wget nor curl found. Cannot download texconv." | tee -a "$LOG_FILE"
                return 1
            fi

            if [ ! -f "$TEMP_DIR/$TEXCONV_ARCHIVE" ]; then
                 echo "ERROR: Failed to download texconv archive file: $TEXCONV_ARCHIVE" | tee -a "$LOG_FILE"
                 return 1
            fi

            # Extract Texconv
            echo "Extracting texconv binary from $TEXCONV_ARCHIVE..."
            local EXTRACT_DIR=$(mktemp -d --tmpdir="$TEMP_DIR" texconv_extract.XXXXXX)
            # Extract to temp dir, assuming texconv is directly inside or in a known subdir
            if tar -xjf "$TEMP_DIR/$TEXCONV_ARCHIVE" -C "$EXTRACT_DIR"; then
                # Find the texconv executable within the extracted files
                local TEXCONV_EXTRACT=$(find "$EXTRACT_DIR" -name "texconv" -type f -executable | head -n 1)
                if [ -n "$TEXCONV_EXTRACT" ]; then
                    cp "$TEXCONV_EXTRACT" "$TEXCONV_CMD"
                    chmod +x "$TEXCONV_CMD"
                    echo "Portable texconv binary extracted to $TEXCONV_CMD"

                    # Also try to find and copy libtexconv.so
                    local TEXCONV_LIB_EXTRACT=$(find "$EXTRACT_DIR" -name "libtexconv.so" -type f | head -n 1)
                    if [ -n "$TEXCONV_LIB_EXTRACT" ]; then
                        cp "$TEXCONV_LIB_EXTRACT" "$PORTABLE_DIR/libtexconv.so"
                        echo "Found and copied libtexconv.so to $PORTABLE_DIR"
                    else
                        echo "Note: libtexconv.so not found in the archive." # Informational
                    fi
                else
                    echo "ERROR: Failed to find texconv executable in the downloaded archive." | tee -a "$LOG_FILE"
                    rm -rf "$EXTRACT_DIR" "$TEMP_DIR/$TEXCONV_ARCHIVE"
                    return 1
                fi
            else
                echo "ERROR: Failed to extract texconv archive $TEMP_DIR/$TEXCONV_ARCHIVE" | tee -a "$LOG_FILE"
                rm -rf "$EXTRACT_DIR" # Clean up extract dir even on tar failure
                return 1
            fi
            # Clean up temporary extraction directory and archive
            rm -rf "$EXTRACT_DIR" "$TEMP_DIR/$TEXCONV_ARCHIVE"
        else
             echo "Found portable texconv binary: $TEXCONV_CMD"
        fi

        # Verify portable executable status
        if [ ! -x "$TEXCONV_CMD" ]; then
            echo "Making portable texconv binary executable..."
            chmod +x "$TEXCONV_CMD"
            if [ ! -x "$TEXCONV_CMD" ]; then
                echo "ERROR: Could not make portable texconv binary executable: $TEXCONV_CMD" | tee -a "$LOG_FILE"
                return 1
            fi
        fi
    fi

    # --- Resolve ImageMagick (Fallback/Optional) ---
    MAGICK_CMD=$(command -v magick || command -v convert) # Prefer magick, fallback to convert
    if [ -n "$MAGICK_CMD" ] && [ -x "$MAGICK_CMD" ]; then
        echo "Found system ImageMagick: $MAGICK_CMD (Fallback tool)"
    else
        echo "System ImageMagick (magick/convert) not found or not executable. Checking for portable version..."
        MAGICK_CMD="$PORTABLE_MAGICK_BIN"
        if [ ! -f "$MAGICK_CMD" ]; then
            echo "Portable ImageMagick binary not found. Downloading (for potential fallback use)..."
            if command -v wget &>/dev/null; then
                wget -q "$MAGICK_URL" -O "$MAGICK_CMD"
            elif command -v curl &>/dev/null; then
                curl -s "$MAGICK_URL" -o "$MAGICK_CMD"
            else
                echo "WARNING: Neither wget nor curl found. Cannot download ImageMagick. Will proceed without fallback tool." | tee -a "$LOG_FILE"
                MAGICK_CMD=""  # Clear the command as it's not available
            fi

            if [ -n "$MAGICK_CMD" ] && [ ! -f "$MAGICK_CMD" ]; then
                echo "WARNING: Failed to download ImageMagick binary. Will proceed without fallback tool." | tee -a "$LOG_FILE"
                MAGICK_CMD=""  # Clear the command as it's not available
            elif [ -n "$MAGICK_CMD" ]; then
                chmod +x "$MAGICK_CMD"
                echo "Portable ImageMagick binary downloaded to $MAGICK_CMD (Fallback tool)"
            fi
        else
             echo "Found portable ImageMagick binary: $MAGICK_CMD (Fallback tool)"
        fi

        # Verify portable executable status if MAGICK_CMD is set
        if [ -n "$MAGICK_CMD" ] && [ ! -x "$MAGICK_CMD" ]; then
            echo "Making portable ImageMagick binary executable..."
            chmod +x "$MAGICK_CMD"
            if [ ! -x "$MAGICK_CMD" ]; then
                echo "WARNING: Could not make portable ImageMagick binary executable: $MAGICK_CMD. Will proceed without fallback tool." | tee -a "$LOG_FILE"
                MAGICK_CMD=""  # Clear the command as it's not executable
            fi
        fi
    fi

    # --- Resolve Hoolamike (BSA Extraction Tool) ---
    echo "Prioritizing portable hoolamike binary."
    HOOLAMIKE_CMD="$PORTABLE_HOOLAMIKE_BIN"
    if [ ! -f "$HOOLAMIKE_CMD" ]; then
        echo "Portable hoolamike binary not found. Downloading from $HOOLAMIKE_URL..."
        if command -v wget &>/dev/null; then
            wget -q "$HOOLAMIKE_URL" -O "$TEMP_DIR/$HOOLAMIKE_ARCHIVE"
        elif command -v curl &>/dev/null; then
            curl -s -L "$HOOLAMIKE_URL" -o "$TEMP_DIR/$HOOLAMIKE_ARCHIVE"
        else
            echo "ERROR: Neither wget nor curl found. Cannot download hoolamike." | tee -a "$LOG_FILE"
            return 1
        fi

        if [ ! -f "$TEMP_DIR/$HOOLAMIKE_ARCHIVE" ]; then
             echo "ERROR: Failed to download hoolamike archive file: $HOOLAMIKE_ARCHIVE" | tee -a "$LOG_FILE"
             return 1
        fi

        # Extract Hoolamike
        echo "Extracting hoolamike binary from $HOOLAMIKE_ARCHIVE..."
        local EXTRACT_DIR=$(mktemp -d --tmpdir="$TEMP_DIR" hoolamike_extract.XXXXXX)
        # Extract to temp dir
        if tar -xzf "$TEMP_DIR/$HOOLAMIKE_ARCHIVE" -C "$EXTRACT_DIR"; then
            # Find the hoolamike executable within the extracted files
            local HOOLAMIKE_EXTRACT=$(find "$EXTRACT_DIR" -name "hoolamike" -type f | head -n 1)
            if [ -n "$HOOLAMIKE_EXTRACT" ]; then
                cp "$HOOLAMIKE_EXTRACT" "$HOOLAMIKE_CMD"
                chmod +x "$HOOLAMIKE_CMD"
                echo "Portable hoolamike binary extracted to $HOOLAMIKE_CMD"

                # Also try to find and copy any .d files
                find "$EXTRACT_DIR" -name "*.d" -type f -exec cp {} "$PORTABLE_DIR/" \;
                echo "Copied any hoolamike .d files to $PORTABLE_DIR"
            else
                echo "ERROR: Failed to find hoolamike executable in the downloaded archive." | tee -a "$LOG_FILE"
                rm -rf "$EXTRACT_DIR" "$TEMP_DIR/$HOOLAMIKE_ARCHIVE"
                return 1
            fi
        else
            echo "ERROR: Failed to extract hoolamike archive $TEMP_DIR/$HOOLAMIKE_ARCHIVE" | tee -a "$LOG_FILE"
            rm -rf "$EXTRACT_DIR" # Clean up extract dir even on tar failure
            return 1
        fi
        # Clean up temporary extraction directory and archive
        rm -rf "$EXTRACT_DIR" "$TEMP_DIR/$HOOLAMIKE_ARCHIVE"
    else
         echo "Found portable hoolamike binary: $HOOLAMIKE_CMD"
    fi

    # Verify portable executable status (still necessary)
    if [ ! -x "$HOOLAMIKE_CMD" ]; then
        echo "Making portable hoolamike binary executable..."
        chmod +x "$HOOLAMIKE_CMD"
        if [ ! -x "$HOOLAMIKE_CMD" ]; then
            echo "ERROR: Could not make portable hoolamike binary executable: $HOOLAMIKE_CMD" | tee -a "$LOG_FILE"
            return 1
        fi
    fi

    # --- Resolve PowerShell (for mod list generation) ---
    PWSH_CMD=$(command -v pwsh)
    if [ -n "$PWSH_CMD" ] && [ -x "$PWSH_CMD" ]; then
        echo "Found system PowerShell: $PWSH_CMD"
    else
        echo "System PowerShell (pwsh) not found or not executable. Checking for portable version..."
        # Check for the executable within the designated portable directory
        if [ -f "$PORTABLE_PWSH_BIN" ] && [ -x "$PORTABLE_PWSH_BIN" ]; then
            PWSH_CMD="$PORTABLE_PWSH_BIN"
            echo "Found portable PowerShell binary: $PWSH_CMD"
        else
            # Portable executable doesn't exist or isn't executable, try downloading
            if [ -f "$PORTABLE_PWSH_BIN" ]; then
                 echo "Found portable PowerShell directory, but pwsh is missing or not executable."
            else
                 echo "Portable PowerShell directory not found ($PWSH_PORTABLE_DIR)."
            fi
            echo "Attempting to download PowerShell from $PWSH_URL..."

            # Download
            if command -v wget &>/dev/null; then
                wget -q "$PWSH_URL" -O "$TEMP_DIR/$PWSH_ARCHIVE"
            elif command -v curl &>/dev/null; then
                curl -s -L "$PWSH_URL" -o "$TEMP_DIR/$PWSH_ARCHIVE"
            else
                echo "ERROR: Neither wget nor curl found. Cannot download PowerShell. Mod list generation might fail." | tee -a "$LOG_FILE"
                PWSH_CMD="" # Clear the command as we couldn't download it
                # Continue without failing the whole script, but PWSH_CMD will be empty
            fi

            # Check if download succeeded before extracting
            if [ -f "$TEMP_DIR/$PWSH_ARCHIVE" ]; then
                # Extract PowerShell to a temporary location first
                echo "Extracting PowerShell archive $PWSH_ARCHIVE..."
                local EXTRACT_DIR=$(mktemp -d --tmpdir="$TEMP_DIR" pwsh_extract.XXXXXX)

                if tar -xzf "$TEMP_DIR/$PWSH_ARCHIVE" -C "$EXTRACT_DIR"; then
                    # DEBUG: List contents of extraction directory
                    echo "DEBUG: Contents of PowerShell extraction directory ($EXTRACT_DIR):"
                    ls -la "$EXTRACT_DIR"

                    # Find the pwsh executable within the extracted files
                    # Find the file first, ignoring executable status initially, maxdepth 1
                    local PWSH_EXTRACT_BIN=$(find "$EXTRACT_DIR" -maxdepth 1 -name "pwsh" -type f | head -n 1)

                    if [ -n "$PWSH_EXTRACT_BIN" ]; then
                        echo "Found pwsh executable in archive at: $PWSH_EXTRACT_BIN"

                        # Explicitly make it executable before moving
                        echo "Attempting to make extracted pwsh executable..."
                        chmod +x "$PWSH_EXTRACT_BIN"
                        if [ ! -x "$PWSH_EXTRACT_BIN" ]; then
                             echo "ERROR: Failed to make extracted pwsh executable at $PWSH_EXTRACT_BIN. Mod list generation will fail." | tee -a "$LOG_FILE"
                             rm -rf "$EXTRACT_DIR" # Clean up
                             PWSH_CMD=""
                             # Skip the rest of the 'if PWSH_EXTRACT_BIN found' block
                        else
                            echo "Successfully made extracted pwsh executable."

                            # Remove existing portable directory if it exists
                            if [ -d "$PWSH_PORTABLE_DIR" ]; then
                                echo "Removing existing portable PowerShell directory: $PWSH_PORTABLE_DIR"
                                rm -rf "$PWSH_PORTABLE_DIR"
                            fi

                            # Move the *contents* of the extraction directory to the portable location
                            # This handles cases where the archive might have a top-level folder
                            echo "Moving extracted PowerShell contents from $EXTRACT_DIR/* to $PWSH_PORTABLE_DIR"
                            mkdir -p "$PWSH_PORTABLE_DIR" # Ensure target exists
                            if mv "$EXTRACT_DIR"/* "$PWSH_PORTABLE_DIR"/; then
                                # Set the command path relative to the new portable directory
                                PWSH_CMD="$PORTABLE_PWSH_BIN" # Use the predefined path

                                # Double-check the final executable path
                                if [ -x "$PWSH_CMD" ]; then
                                    echo "Portable PowerShell is ready at: $PWSH_CMD"
                                else
                                    echo "ERROR: Moved PowerShell is not executable at $PWSH_CMD. Mod list generation might fail." | tee -a "$LOG_FILE"
                                    PWSH_CMD="" # Clear command if not executable
                                fi
                            else
                                 echo "ERROR: Failed to move extracted PowerShell contents to $PWSH_PORTABLE_DIR. Mod list generation might fail." | tee -a "$LOG_FILE"
                                 # EXTRACT_DIR might still contain files if move failed partially
                                 PWSH_CMD=""
                            fi
                            # Clean up the now potentially empty extraction dir
                            rm -rf "$EXTRACT_DIR"
                        fi # End of inner chmod success check
                    else
                        echo "ERROR: Failed to find pwsh executable (pwsh) within the extracted files in $EXTRACT_DIR. Mod list generation will fail." | tee -a "$LOG_FILE"
                        rm -rf "$EXTRACT_DIR" # Clean up extract dir if pwsh not found
                        PWSH_CMD="" # Clear the command
                    fi
                else
                    echo "ERROR: Failed to extract PowerShell archive $TEMP_DIR/$PWSH_ARCHIVE. Mod list generation might fail." | tee -a "$LOG_FILE"
                    rm -rf "$EXTRACT_DIR" # Clean up extract dir even on tar failure
                    PWSH_CMD="" # Clear the command
                fi
                # Clean up archive (don't clean EXTRACT_DIR if move was successful)
                rm -f "$TEMP_DIR/$PWSH_ARCHIVE"
            else
                 echo "ERROR: Failed to download PowerShell archive file: $PWSH_ARCHIVE. Mod list generation might fail." | tee -a "$LOG_FILE"
                 PWSH_CMD="" # Clear the command
            fi
        fi
    fi

    # Final check on the command path viability
    if [ -z "$PWSH_CMD" ]; then
         echo "ERROR: PowerShell command could not be resolved (system or portable). This is required for prioritized texture copy." | tee -a "$LOG_FILE"
         echo "Please ensure PowerShell is installed system-wide OR allow the script to download the portable version." | tee -a "$LOG_FILE"
         exit 1 # Exit script because PowerShell is mandatory
    elif [ ! -x "$PWSH_CMD" ]; then
        echo "ERROR: Final check failed - PowerShell command is set ($PWSH_CMD) but not executable. Mod list generation will fail." | tee -a "$LOG_FILE"
        PWSH_CMD=""
        exit 1 # Exit script because PowerShell is mandatory but broken
    fi

    # --- Resolve fd (Optional Find Alternative) ---
    FD_CMD=$(command -v fdfind || command -v fd) # Check both common names
    if [ -n "$FD_CMD" ] && [ -x "$FD_CMD" ]; then
        echo "Found system fd (find alternative): $FD_CMD"
    else
        FD_CMD=""
        echo "System fd/fdfind not found. Checking for portable version..."
        if [ -f "$PORTABLE_FD_BIN" ]; then
            if [ -x "$PORTABLE_FD_BIN" ]; then
                FD_CMD="$PORTABLE_FD_BIN"
                echo "Found portable fd binary: $FD_CMD"
            else
                echo "Found portable fd binary, but it's not executable: $PORTABLE_FD_BIN. Attempting to make executable..."
                chmod +x "$PORTABLE_FD_BIN"
                if [ -x "$PORTABLE_FD_BIN" ]; then
                    FD_CMD="$PORTABLE_FD_BIN"
                    echo "Portable fd binary is now executable: $FD_CMD"
                else
                    echo "Warning: Could not make portable fd binary executable. Falling back to 'find'." | tee -a "$LOG_FILE"
                fi
            fi
        else
             echo "Portable fd binary not found at $PORTABLE_FD_BIN. Falling back to 'find'."
        fi
    fi

    # Final verification - CRITICAL TOOLS
    if [ -z "$SQLITE_CMD" ] || [ ! -x "$SQLITE_CMD" ]; then
        echo "ERROR: Could not resolve a working sqlite3 command." | tee -a "$LOG_FILE"
        return 1
    fi

    if [ -z "$MAGICK_CMD" ] || [ ! -x "$MAGICK_CMD" ]; then
        echo "ERROR: Could not resolve a working ImageMagick command (primary texture analysis tool)." | tee -a "$LOG_FILE"
        return 1
    fi

    if [ -z "$HOOLAMIKE_CMD" ] || [ ! -x "$HOOLAMIKE_CMD" ]; then
        echo "ERROR: Could not resolve a working hoolamike command (required for BSA extraction)." | tee -a "$LOG_FILE"
        return 1
    fi

    echo "Using SQLite command: $SQLITE_CMD"
    echo "Using ImageMagick command: $MAGICK_CMD (PRIMARY texture analysis tool)"
    echo "Using hoolamike command: $HOOLAMIKE_CMD (BSA extraction tool)"

    if [ -n "$TEXCONV_CMD" ] && [ -x "$TEXCONV_CMD" ]; then
        echo "Using Texconv command: $TEXCONV_CMD (FALLBACK tool, only used if ImageMagick fails)"
    else
        echo "No texconv fallback available. Will rely exclusively on ImageMagick."
    fi

    if [ -n "$PWSH_CMD" ] && [ -x "$PWSH_CMD" ]; then
        echo "Using PowerShell command: $PWSH_CMD (for mod list generation)"
    else
        echo "WARNING: No working PowerShell command found (system or portable). Mod list generation will be skipped." | tee -a "$LOG_FILE"
    fi

    return 0
}
