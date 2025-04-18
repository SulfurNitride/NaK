#!/bin/bash

# --- Texture Processing Functions ---

# Process exclusions using native Linux tools
linux_native_exclusions() {
    echo "$(date) Processing Exclusions with Native Linux Tools..." >> "$LOG_FILE"
    echo "Processing exclusion patterns with native Linux tools..."
    update_progress 55

    # Define Exclusion Patterns
    shopt -s extglob nocaseglob

    # File pattern exclusions
    local file_exclusions=(
        '*_color.dds' '*_emissive.dds' '*_normal.dds' '*_opengl.dds' 'icewall*.dds'
        '*drj*.dds' '*envmask.dds' '*_g.dds' '*_s.dds' '*_sk.dds' '*_b.dds'
        '*_a.dds' '*_e.dds' '*_h.dds'
        'pot_n.dds' 'tg_field_rocks.dds' 'tg_field_rocks_n.dds' 'tg_snow_pebbles.dds'
        'tg_snow_pebbles_n.dds' 'clgorehowl*.dds' 'woodcut.dds' 'woodcut_n.dds'
        'dummy.dds' '*lod*_p.dds' 'default_n.dds' 'basket01.dds'
    )

    # Directory exclusions - fixed to use substring matches without trailing slashes
    local dir_exclusions=(
        "/!_Rudy_Misc" "/!SR" "/!!SR" "/interface" "/effects03/newmiller/jewels2"
        "/littlebaron" "/luxonbeacon" "/landscape/mountains" "/landscape/rocks"
        "/terrain" "/lod" "/DynDOLOD" "/LODGen"
    )

    local EXCLUSIONS_LOG="$VRAMR_TEMP/logfiles/exclusions.log"
    > "$EXCLUSIONS_LOG"
    local OUTPUT_TEXTURES_DIR="$VRAMR_TEMP/Output/textures"

    # Find all DDS files in output
    echo "Scanning for files to exclude in $OUTPUT_TEXTURES_DIR..."
    local ALL_FILES_LIST=$(mktemp --tmpdir="$TEMP_DIR" exclude_files.XXXXXX)
    find "$OUTPUT_TEXTURES_DIR" -type f -iname "*.dds" -print0 > "$ALL_FILES_LIST"
    local TOTAL_FILES=$(tr -d -c '\0' < "$ALL_FILES_LIST" | wc -c)
    echo "Found $TOTAL_FILES DDS files to process for exclusions"

    if [ "$TOTAL_FILES" -eq 0 ]; then
        echo "No DDS files found in output to exclude."
        echo "$(date) No DDS files found in output to exclude." >> "$LOG_FILE"
        rm -f "$ALL_FILES_LIST"
        update_progress 60
        return
    fi

    # Progress tracking
    local PROGRESS_FILE=$(mktemp --tmpdir="$TEMP_DIR" exclude_progress.XXXXXX)
    echo "0" > "$PROGRESS_FILE"
    touch "$PROGRESS_FILE.lock"

    local EXCLUDED_COUNT_FILE=$(mktemp --tmpdir="$TEMP_DIR" exclude_count.XXXXXX)
    echo "0" > "$EXCLUDED_COUNT_FILE"
    touch "$EXCLUDED_COUNT_FILE.lock"

    # Progress monitor
    monitor_exclusion_progress() {
        local total=$1
        local progress_file=$2
        while true; do
            sleep 1
            local current_processed=$(cat "$progress_file" 2>/dev/null || echo 0)
            # Ensure current_processed has a value
            current_processed=${current_processed:-0}
            if [ "$current_processed" -ge "$total" ]; then
                better_progress_bar "$current_processed" "$total" "Exclusions"
                break
            fi
            if ! ps -p $$ > /dev/null; then break; fi
            better_progress_bar "$current_processed" "$total" "Exclusions"
        done
        local final_processed=$(cat "$progress_file" 2>/dev/null || echo "$total")
        # Ensure final_processed has a value
        final_processed=${final_processed:-$total}
        better_progress_bar "$final_processed" "$total" "Exclusions"
        echo ""
    }

    monitor_exclusion_progress "$TOTAL_FILES" "$PROGRESS_FILE" &
    local MONITOR_PID=$!

    # Create a simple exclusion script
    local EXCLUSION_SCRIPT=$(mktemp --tmpdir="$TEMP_DIR" exclusion_script.XXXXXX)

    # Write the file pattern exclusions to a file
    local FILE_PATTERNS_FILE=$(mktemp --tmpdir="$TEMP_DIR" file_patterns.XXXXXX)
    for pattern in "${file_exclusions[@]}"; do
        echo "$pattern" >> "$FILE_PATTERNS_FILE"
    done

    # Write the directory pattern exclusions to a file
    local DIR_PATTERNS_FILE=$(mktemp --tmpdir="$TEMP_DIR" dir_patterns.XXXXXX)
    for pattern in "${dir_exclusions[@]}"; do
        echo "$pattern" >> "$DIR_PATTERNS_FILE"
    done

    # Write the exclusion script
    cat > "$EXCLUSION_SCRIPT" << 'EOF'
#!/bin/bash
# Simple exclusion script

file="$1"
progress_file="$2"
excluded_count_file="$3"
exclusions_log="$4"
output_dir="$5"
file_patterns_file="$6"
dir_patterns_file="$7"
log_file="$8"

filename=$(basename "$file")
rel_path="${file#$output_dir/}"
excluded=0

# Check file patterns
while IFS= read -r pattern; do
    if [[ "$filename" == $pattern ]]; then
        excluded=1
        break
    fi
done < "$file_patterns_file"

# Check directory patterns if not already excluded
if [ "$excluded" -eq 0 ]; then
    while IFS= read -r pattern; do
        if [[ "/$rel_path" == *"$pattern"* ]]; then
            excluded=1
            break
        fi
    done < "$dir_patterns_file"
fi

# Remove if excluded
if [ "$excluded" -eq 1 ]; then
    if rm -f "$file" 2>/dev/null; then
        echo "Excluded: $rel_path" >> "$exclusions_log"
        # Increment excluded count
        (
            flock -x 201
            current=$(cat "$excluded_count_file" 2>/dev/null || echo 0)
            echo $((current + 1)) > "$excluded_count_file"
        ) 201>"$excluded_count_file.lock"
    else
        echo "Error removing excluded file: $file" >> "$log_file"
    fi
fi

# Update progress
(
    flock -x 200
    current=$(cat "$progress_file" 2>/dev/null || echo 0)
    echo $((current + 1)) > "$progress_file"
) 200>"$progress_file.lock"
EOF

    # Make script executable
    chmod +x "$EXCLUSION_SCRIPT"

    # Process files using either parallel or xargs
    if command -v parallel &> /dev/null; then
        echo "Using GNU parallel for exclusion processing..."
        tr '\0' '\n' < "$ALL_FILES_LIST" | \
        parallel -j "$THREAD_COUNT" "$EXCLUSION_SCRIPT" {} "$PROGRESS_FILE" "$EXCLUDED_COUNT_FILE" "$EXCLUSIONS_LOG" "$OUTPUT_TEXTURES_DIR" "$FILE_PATTERNS_FILE" "$DIR_PATTERNS_FILE" "$LOG_FILE"
    else
        echo "GNU parallel not found, using xargs..."
        xargs -0 -n 1 -P "$THREAD_COUNT" "$EXCLUSION_SCRIPT" < "$ALL_FILES_LIST" "$PROGRESS_FILE" "$EXCLUDED_COUNT_FILE" "$EXCLUSIONS_LOG" "$OUTPUT_TEXTURES_DIR" "$FILE_PATTERNS_FILE" "$DIR_PATTERNS_FILE" "$LOG_FILE"
    fi

    # Wait for all exclusion operations to complete
    wait

    # Wait for monitor
    wait $MONITOR_PID 2>/dev/null || true

    # Final counts
    local EXCLUDED_COUNT=$(cat "$EXCLUDED_COUNT_FILE")
    local PROCESSED_COUNT=$(cat "$PROGRESS_FILE")

    # Ensure final progress bar is 100%
    if [ "$PROCESSED_COUNT" -ge "$TOTAL_FILES" ]; then
        better_progress_bar "$TOTAL_FILES" "$TOTAL_FILES" "Exclusions"
        echo ""
    fi

    shopt -u extglob nocaseglob

    echo "Exclusion processing complete!"
    echo "Total files processed: $PROCESSED_COUNT"
    echo "Files excluded: $EXCLUDED_COUNT"
    echo "$(date) Exclusion processing complete. $EXCLUDED_COUNT files excluded." >> "$LOG_FILE"

    # Cleanup
    rm -f "$ALL_FILES_LIST" "$PROGRESS_FILE" "$PROGRESS_FILE.lock" "$EXCLUDED_COUNT_FILE" "$EXCLUDED_COUNT_FILE.lock"
    rm -f "$EXCLUSION_SCRIPT" "$FILE_PATTERNS_FILE" "$DIR_PATTERNS_FILE"

    # Remove empty directories
    find "$OUTPUT_TEXTURES_DIR" -type d -empty -delete 2>/dev/null || true

    update_progress 60
}

# Linux-native texture analysis function (using ImageMagick with texconv fallback)
linux_native_analyze() {
    echo "$(date) Analyzing textures with Linux-native tools (primarily ImageMagick)..." >> "$LOG_FILE"
    echo "Starting Linux-native texture analysis (primarily using ImageMagick)..."
    update_progress 60

    local DB_FILE="$VRAMR_TEMP/Output/VRAMr.db"
    local OUTPUT_TEXTURES_DIR="$VRAMR_TEMP/Output/textures"
    echo "Creating texture database at $DB_FILE"

    # Check critical dependencies
    if [ -z "$SQLITE_CMD" ] || [ ! -x "$SQLITE_CMD" ]; then
        echo "ERROR: SQLite command not found or not executable: $SQLITE_CMD" | tee -a "$LOG_FILE"
        return 1
    fi

    # Check if ImageMagick is available (primary tool)
    if [ -z "$MAGICK_CMD" ] || [ ! -x "$MAGICK_CMD" ]; then
        echo "ERROR: ImageMagick command not found or not executable: $MAGICK_CMD" | tee -a "$LOG_FILE"

        # Check if texconv is available as fallback
        if [ -n "$TEXCONV_CMD" ] && [ -x "$TEXCONV_CMD" ]; then
            echo "WARNING: Falling back to texconv for texture analysis." | tee -a "$LOG_FILE"
            echo "This fallback functionality is not yet implemented in this version." | tee -a "$LOG_FILE"
            return 1
        else
            echo "ERROR: Neither ImageMagick nor texconv available. Cannot perform texture analysis." | tee -a "$LOG_FILE"
            return 1
        fi
    fi

    # Initialize SQLite database with performance optimizations
    rm -f "$DB_FILE" "$DB_FILE-journal" "$DB_FILE-wal" "$DB_FILE-shm"

    "$SQLITE_CMD" "$DB_FILE" <<EOL
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA cache_size = 10000;
PRAGMA page_size = 4096;
CREATE TABLE textures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    width INTEGER,
    height INTEGER,
    format TEXT,
    category TEXT,
    type TEXT,
    processed INTEGER DEFAULT 0,
    optimize_target_format TEXT,
    optimize_target_size INTEGER
);
CREATE INDEX idx_textures_path ON textures(path);
CREATE INDEX idx_textures_filename ON textures(filename);
CREATE INDEX idx_textures_type ON textures(type);
CREATE INDEX idx_textures_category ON textures(category);
CREATE INDEX idx_textures_processed ON textures(processed);
EOL

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to initialize SQLite database $DB_FILE" | tee -a "$LOG_FILE"
        return 1
    fi

    # Find texture files
    echo "Finding all DDS files in output directory for analysis..."
    local TEXTURE_FILES_LIST=$(mktemp --tmpdir="$TEMP_DIR" analyze_files.XXXXXX)
    find "$OUTPUT_TEXTURES_DIR" -type f -iname "*.dds" -print0 > "$TEXTURE_FILES_LIST"
    local TOTAL_FILES=$(tr -d -c '\0' < "$TEXTURE_FILES_LIST" | wc -c)
    echo "Found $TOTAL_FILES DDS files to analyze"

    if [ "$TOTAL_FILES" -eq 0 ]; then
        echo "No texture files found to analyze!"
        echo "$(date) No texture files found in output to analyze." >> "$LOG_FILE"
        rm -f "$TEXTURE_FILES_LIST"
        update_progress 69
        return 0
    fi

    # Progress tracking
    local PROGRESS_FILE=$(mktemp --tmpdir="$TEMP_DIR" analyze_progress.XXXXXX)
    echo "0" > "$PROGRESS_FILE"
    touch "$PROGRESS_FILE.lock"

    # Temporary SQL file
    local SQL_FILE=$(mktemp --tmpdir="$TEMP_DIR" analysis_sql.XXXXXX)
    echo "BEGIN TRANSACTION;" > "$SQL_FILE"
    touch "$SQL_FILE.lock"

    local ANALYSIS_LOG="$VRAMR_TEMP/logfiles/analysis.log"
    > "$ANALYSIS_LOG"

    # Progress monitor
    monitor_analysis_progress() {
        local total=$1
        local progress_file=$2
        while true; do
            sleep 1
            local current_analyzed=$(cat "$progress_file" 2>/dev/null || echo 0)
            # Ensure current_analyzed has a value
            current_analyzed=${current_analyzed:-0}
            if [ "$current_analyzed" -ge "$total" ]; then
                better_progress_bar "$current_analyzed" "$total" "Analysis"
                break
            fi
            if ! ps -p $$ > /dev/null; then break; fi
            better_progress_bar "$current_analyzed" "$total" "Analysis"
        done
        local final_analyzed=$(cat "$progress_file" 2>/dev/null || echo "$total")
        # Ensure final_analyzed has a value
        final_analyzed=${final_analyzed:-$total}
        better_progress_bar "$final_analyzed" "$total" "Analysis"
        echo ""
    }

    monitor_analysis_progress "$TOTAL_FILES" "$PROGRESS_FILE" &
    local MONITOR_PID=$!

    # Create analysis script using ImageMagick with texconv fallback
    local ANALYSIS_SCRIPT=$(mktemp --tmpdir="$TEMP_DIR" analysis_script.XXXXXX)

    # Export the path to resolved commands for use in the script
    export TEXCONV_CMD MAGICK_CMD

    cat > "$ANALYSIS_SCRIPT" << 'EOF'
#!/bin/bash
# Texture analysis script using ImageMagick with texconv fallback

file="$1"
progress_file="$2"
output_dir="$3"
analysis_log="$4"
sql_file="$5"
# VRAMR_TEMP is needed for creating temp analysis dir
temp_base_dir="$6"
# TEXCONV_CMD and MAGICK_CMD are exported from parent

# Get relative path and filename
rel_path="${file#$output_dir/}"
filename="$(basename "$file")"

# Initialize variables
width=0
height=0
format="unknown"
parsed_correctly=0

# Primary analysis: Use ImageMagick
if [ -n "$MAGICK_CMD" ] && [ -x "$MAGICK_CMD" ]; then
    # Use identify to get dimensions
    magick_info=$("$MAGICK_CMD" identify -format "%w %h %m" "$file" 2>&1)
    magick_exit=$?

    if [ "$magick_exit" -eq 0 ] && [ -n "$magick_info" ]; then
        # Parse ImageMagick output
        read -r width height format_raw <<< "$magick_info"

        # Validate parsed values
        if [[ "$width" =~ ^[0-9]+$ ]] && [[ "$height" =~ ^[0-9]+$ ]]; then
            format="IM_$format_raw" # Prefix with IM_ to indicate ImageMagick parsed format
            parsed_correctly=1
            echo "Success: ImageMagick parsed $file: ${width}x${height} $format" >> "$analysis_log"
        fi
    else
        echo "Warning: ImageMagick identify failed for $file: $magick_info" >> "$analysis_log"
    fi
fi

# Fallback: Use texconv if ImageMagick parsing failed
if [ "$parsed_correctly" -eq 0 ] && [ -n "$TEXCONV_CMD" ] && [ -x "$TEXCONV_CMD" ]; then
    echo "Fallback: Using texconv to analyze $file..." >> "$analysis_log"

    # Create a dedicated temp dir for texconv analysis output
    texconv_temp_out=$(mktemp -d --tmpdir="$temp_base_dir" texconv_analysis_out.XXXXXX)

    # Run texconv, redirecting output file to the dedicated temp dir
    info=$("$TEXCONV_CMD" -nologo -y -o "$texconv_temp_out" -- "$file" 2>&1)
    texconv_exit=$?

    # Clean up the dedicated temp dir immediately
    if [ -d "$texconv_temp_out" ]; then rm -rf "$texconv_temp_out"; fi

    # Try to parse the "reading..." line
    reading_line=$(echo "$info" | grep 'reading ')

    if [ -n "$reading_line" ]; then
        # Extract content within the first parentheses: e.g., 512x512,10 BC1_UNORM 2D
        content=$(echo "$reading_line" | sed -n 's/.*reading.*(\([^)]*\)).*/\1/p')
        if [ -n "$content" ]; then
            # Extract dimensions part: 512x512
            dims=$(echo "$content" | awk -F, '{print $1}')
            # Extract format part: BC1_UNORM (from "10 BC1_UNORM 2D")
            # Get part after comma, trim leading space, get first word
            format_part=$(echo "$content" | awk -F, '{print $2}' | sed 's/^[[:space:]]*//' | awk '{print $2}')

            # Use regex to extract width and height from dims
            if [[ "$dims" =~ ^([0-9]+)x([0-9]+)$ ]] && [ -n "$format_part" ]; then
                width=${BASH_REMATCH[1]}
                height=${BASH_REMATCH[2]}
                format="TX_$format_part"  # Prefix with TX_ to indicate texconv parsed format
                parsed_correctly=1
                echo "  Success: texconv parsed $file: ${width}x${height} $format" >> "$analysis_log"
            fi
        fi
    fi

    # Log texconv exit code only if it failed AND parsing failed
    if [ "$texconv_exit" -ne 0 ] && [ "$parsed_correctly" -eq 0 ]; then
        echo "  Error: texconv exited with code $texconv_exit for $file and parsing failed." >> "$analysis_log"
    elif [ "$texconv_exit" -ne 0 ]; then
        echo "  Info: texconv exited with code $texconv_exit for $file, but metadata was parsed successfully." >> "$analysis_log"
    fi
fi

# If both methods failed, use fallback values
if [ "$parsed_correctly" -eq 0 ]; then
    echo "Warning: Both ImageMagick and texconv (if available) failed to parse $file. Using fallback values." >> "$analysis_log"
    width=1024   # Fallback width
    height=1024  # Fallback height
    format="unknown_fallback"  # Fallback format
fi

# Categorize texture
# Convert to lowercase for case-insensitive matching
lower_filename=$(echo "$filename" | tr '[:upper:]' '[:lower:]')
lower_path=$(echo "$file" | tr '[:upper:]' '[:lower:]')

# Determine texture type
type="other"
if [[ "$lower_filename" == *_n.dds || "$lower_filename" == *_normal.dds ]]; then
    type="normal"
elif [[ "$lower_filename" == *_d.dds || "$lower_filename" == *_diffuse.dds || "$lower_filename" == *_albedo.dds ]]; then
    type="diffuse"
elif [[ "$lower_filename" == *_p.dds || "$lower_filename" == *_parallax.dds || "$lower_filename" == *_height.dds ]]; then
    type="parallax"
elif [[ "$lower_filename" == *_m.dds || "$lower_filename" == *_material.dds ||
        "$lower_filename" == *_mt.dds || "$lower_filename" == *_masks.dds ||
        "$lower_filename" == *_specular.dds || "$lower_filename" == *_s.dds ||
        "$lower_filename" == *_g.dds || "$lower_filename" == *_glow.dds ||
        "$lower_filename" == *_emissive.dds || "$lower_filename" == *_e.dds ||
        "$lower_filename" == *_envmask.dds || "$lower_filename" == *_h.dds ||
        "$lower_filename" == *_ao.dds || "$lower_filename" == *_a.dds ]]; then
    type="material"
elif [[ "$lower_filename" == *_sk.dds || "$lower_filename" == *_skin.dds ]]; then
    type="skin"
fi

# Determine category
category="misc"
if [[ "$lower_path" == */architecture/* ]]; then
    category="architecture"
elif [[ "$lower_path" == */landscape/* || "$lower_path" == */terrain/* ]]; then
    category="landscape"
elif [[ "$lower_path" == */clutter/* ]]; then
    category="clutter"
elif [[ "$lower_path" == */actors/* || "$lower_path" == */character/* || "$lower_path" == */creatures/* ]]; then
    category="actors"
elif [[ "$lower_path" == */weapons/* ]]; then
    category="weapons"
elif [[ "$lower_path" == */armor/* ]]; then
    category="armor"
elif [[ "$lower_path" == */clothing/* ]]; then
    category="clothing"
elif [[ "$lower_path" == */effects/* ]]; then
    category="effects"
elif [[ "$lower_path" == */sky/* ]]; then
    category="sky"
elif [[ "$lower_path" == */interface/* ]]; then
    category="interface"
elif [[ "$lower_path" == */textures/lod/* || "$lower_path" == */terrain/lod/* ]]; then
    category="lod"
fi

# Prepare variables for SQL
sql_rel_path="$rel_path"
sql_filename="$filename"
sql_format="$format"
sql_category="$category"
sql_type="$type"

# Escape single quotes for SQL using sed
sql_rel_path=$(echo "$sql_rel_path" | sed "s/'/''/g")
sql_filename=$(echo "$sql_filename" | sed "s/'/''/g")
sql_format=$(echo "$sql_format" | sed "s/'/''/g")
sql_category=$(echo "$sql_category" | sed "s/'/''/g")
sql_type=$(echo "$sql_type" | sed "s/'/''/g")

# Generate SQL and append to file using single quotes for strings
(
    flock -x 200
    echo "INSERT INTO textures (path, filename, width, height, format, category, type) VALUES ('$sql_rel_path', '$sql_filename', $width, $height, '$sql_format', '$sql_category', '$sql_type');" >> "$sql_file"
) 200>"$sql_file.lock"

# Update progress
(
    flock -x 201
    current=$(cat "$progress_file" 2>/dev/null || echo 0)
    echo $((current + 1)) > "$progress_file"
) 201>"$progress_file.lock"
EOF

    # Make script executable
    chmod +x "$ANALYSIS_SCRIPT"

    # Process files using either parallel or xargs
    if command -v parallel &> /dev/null; then
        echo "Using GNU parallel for texture analysis..."
        tr '\0' '\n' < "$TEXTURE_FILES_LIST" | \
        parallel -j "$THREAD_COUNT" "$ANALYSIS_SCRIPT" {} "$PROGRESS_FILE" "$OUTPUT_TEXTURES_DIR" "$ANALYSIS_LOG" "$SQL_FILE" "$VRAMR_TEMP"
    else
        echo "GNU parallel not found, using xargs..."
        xargs -0 -n 1 -P "$THREAD_COUNT" "$ANALYSIS_SCRIPT" < "$TEXTURE_FILES_LIST" "$PROGRESS_FILE" "$OUTPUT_TEXTURES_DIR" "$ANALYSIS_LOG" "$SQL_FILE" "$VRAMR_TEMP"
    fi

    # Wait for all analysis operations to complete
    wait

    # Wait for monitor
    wait $MONITOR_PID 2>/dev/null || true

    # Finalize SQL file and import to database
    echo "COMMIT;" >> "$SQL_FILE"

    # Import SQL data into database using resolved SQLite
    echo "Importing analysis data into database ($DB_FILE)..."
    "$SQLITE_CMD" "$DB_FILE" < "$SQL_FILE"

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to execute SQL commands in $DB_FILE." | tee -a "$LOG_FILE"
        return 1
    fi

    # Display stats using resolved SQLite command
    local analyzed_count=$("$SQLITE_CMD" "$DB_FILE" "SELECT COUNT(*) FROM textures;")
    echo "Texture analysis complete. Analyzed $analyzed_count textures."
    echo "Database created at: $DB_FILE"
    echo "$(date) Linux-native texture analysis complete - $analyzed_count textures analyzed." >> "$LOG_FILE"

    # Display tool usage metrics if verbose mode
    if [ "$VERBOSE" -eq 1 ]; then
        local imagemagick_count=$("$SQLITE_CMD" "$DB_FILE" "SELECT COUNT(*) FROM textures WHERE format LIKE 'IM_%';")
        local texconv_count=$("$SQLITE_CMD" "$DB_FILE" "SELECT COUNT(*) FROM textures WHERE format LIKE 'TX_%';")
        local fallback_count=$("$SQLITE_CMD" "$DB_FILE" "SELECT COUNT(*) FROM textures WHERE format = 'unknown_fallback';")

        echo "Analysis Tool Usage:"
        echo "  - ImageMagick successfully analyzed: $imagemagick_count textures"
        echo "  - Texconv fallback used: $texconv_count textures"
        echo "  - Fallback values used: $fallback_count textures"

        echo "Analysis Tool Usage:" >> "$LOG_FILE"
        echo "  - ImageMagick successfully analyzed: $imagemagick_count textures" >> "$LOG_FILE"
        echo "  - Texconv fallback used: $texconv_count textures" >> "$LOG_FILE"
        echo "  - Fallback values used: $fallback_count textures" >> "$LOG_FILE"
    fi

    # Cleanup
    rm -f "$TEXTURE_FILES_LIST" "$PROGRESS_FILE" "$PROGRESS_FILE.lock" "$SQL_FILE" "$SQL_FILE.lock" "$ANALYSIS_SCRIPT"

    update_progress 69
    return 0
}

# Analyze textures - safe fallback (using ImageMagick with reduced threads)
analyze_textures_safely() {
    echo "$(date) Analyzing textures (safe mode)..." >> "$LOG_FILE"
    echo "Analyzing textures (using safe mode - 1 thread)..."

    local original_threads=$THREAD_COUNT
    THREAD_COUNT=1
    linux_native_analyze
    local exit_code=$?
    THREAD_COUNT=$original_threads

    if [ $exit_code -eq 0 ]; then
        echo "Texture analysis (safe mode) complete."
        echo "$(date) Texture analysis (safe mode) complete." >> "$LOG_FILE"
    else
         echo "Texture analysis (safe mode) failed. See logs."
         echo "$(date) Texture analysis (safe mode) failed." >> "$LOG_FILE"
    fi
    return $exit_code
}

# Native filtering implementation (using portable SQLite)
linux_native_filter() {
    echo "$(date) Filtering textures based on preset: $PRESET..." >> "$LOG_FILE"
    echo "Filtering textures based on preset: $PRESET"
    update_progress 69

    local DB_FILE="$VRAMR_TEMP/Output/VRAMr.db"

    # Check for resolved SQLite command
    if [ -z "$SQLITE_CMD" ] || [ ! -x "$SQLITE_CMD" ]; then
        echo "ERROR: SQLite command not found or not executable: $SQLITE_CMD" | tee -a "$LOG_FILE"
        return 1
    fi

    if [ ! -f "$DB_FILE" ]; then
        echo "ERROR: Database file not found: $DB_FILE. Cannot filter." | tee -a "$LOG_FILE"
        return 1
    fi

    echo "Applying filters for Preset: $PRESET (D:$DIFFUSE N:$NORMAL P:$PARALLAX M:$MATERIAL)"

    # More detailed filtering logic with optimization targets
    "$SQLITE_CMD" "$DB_FILE" <<EOL
-- Enable foreign keys and optimize processing
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;

-- Begin transaction for faster processing
BEGIN TRANSACTION;

-- Update diffuse textures
UPDATE textures SET
    processed = CASE
        WHEN width <= $DIFFUSE AND height <= $DIFFUSE THEN 1 -- Keep as is
        ELSE -2 -- Mark for downscale
    END,
    optimize_target_size = $DIFFUSE,
    optimize_target_format = 'BC7_UNORM_SRGB'
WHERE type = 'diffuse';

-- Update normal textures
UPDATE textures SET
    processed = CASE
        WHEN width <= $NORMAL AND height <= $NORMAL THEN 1 -- Keep as is
        ELSE -2 -- Mark for downscale
    END,
    optimize_target_size = $NORMAL,
    optimize_target_format = 'BC5_SNORM'
WHERE type = 'normal';

-- Update parallax textures
UPDATE textures SET
    processed = CASE
        WHEN width <= $PARALLAX AND height <= $PARALLAX THEN 1 -- Keep as is
        ELSE -2 -- Mark for downscale
    END,
    optimize_target_size = $PARALLAX,
    optimize_target_format = 'BC4_UNORM'
WHERE type = 'parallax';

-- Update material textures
UPDATE textures SET
    processed = CASE
        WHEN width <= $MATERIAL AND height <= $MATERIAL THEN 1 -- Keep as is
        ELSE -2 -- Mark for downscale
    END,
    optimize_target_size = $MATERIAL,
    optimize_target_format = 'BC7_UNORM'
WHERE type = 'material';

-- Handle special cases
UPDATE textures SET processed = -1 WHERE category = 'interface';
UPDATE textures SET processed = -1 WHERE category = 'lod';
UPDATE textures SET processed = -1 WHERE category = 'sky';
UPDATE textures SET processed = -1 WHERE filename LIKE '%_glow.dds';
UPDATE textures SET processed = -1 WHERE MAX(width, height) <= 256;

-- Mark tiny textures to be left alone
UPDATE textures SET processed = -1 WHERE width <= 64 OR height <= 64;

-- Final catch-all: Mark any remaining unprocessed textures as skip
UPDATE textures SET processed = -1 WHERE processed = 0;

-- --- Add Default Format Here ---
-- Final safety net: Assign a default valid format if none was set
UPDATE textures SET optimize_target_format = 'BC7_UNORM' WHERE optimize_target_format IS NULL;
-- --- End Default Format ---

-- Commit all changes
COMMIT;
EOL

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to apply filters to database $DB_FILE" | tee -a "$LOG_FILE"
        return 1
    fi

    # Generate detailed statistics using resolved SQLite command
    local filter_stats=$("$SQLITE_CMD" "$DB_FILE" "
SELECT
    'Total textures: ' || COUNT(*) AS statistics,
    'To optimize: ' || SUM(CASE WHEN processed = 1 THEN 1 ELSE 0 END) AS to_optimize,
    'To skip: ' || SUM(CASE WHEN processed = -1 THEN 1 ELSE 0 END) AS to_skip,
    'To downscale: ' || SUM(CASE WHEN processed = -2 THEN 1 ELSE 0 END) AS to_downscale,
    'By Type:' AS type_header,
    '  Diffuse: ' || SUM(CASE WHEN type = 'diffuse' THEN 1 ELSE 0 END) AS diffuse_count,
    '  Normal: ' || SUM(CASE WHEN type = 'normal' THEN 1 ELSE 0 END) AS normal_count,
    '  Parallax: ' || SUM(CASE WHEN type = 'parallax' THEN 1 ELSE 0 END) AS parallax_count,
    '  Material: ' || SUM(CASE WHEN type = 'material' THEN 1 ELSE 0 END) AS material_count,
    '  Other: ' || SUM(CASE WHEN type = 'other' THEN 1 ELSE 0 END) AS other_count
FROM textures;
")

    echo "Filtering complete. Statistics:"
    echo "$filter_stats" | sed 's/|/\n/g'
    echo "$(date) Filtering complete with preset $PRESET" >> "$LOG_FILE"
    echo "$filter_stats" | sed 's/|/\n/g' >> "$LOG_FILE"

    update_progress 74
    return 0
}

# Function to delete textures marked as skip (-1)
delete_skipped_textures() {
    echo "$(date) Deleting skipped textures..." >> "$LOG_FILE"
    echo "Deleting textures marked to be skipped..."
    update_progress 75 # Start progress for this step

    local DB_FILE="$VRAMR_TEMP/Output/VRAMr.db"
    local OUTPUT_TEXTURES_DIR="$VRAMR_TEMP/Output/textures"

    # Check dependencies
    if [ -z "$SQLITE_CMD" ] || [ ! -x "$SQLITE_CMD" ]; then
        echo "ERROR: SQLite command not found or not executable: $SQLITE_CMD" | tee -a "$LOG_FILE"
        return 1
    fi

    if [ ! -f "$DB_FILE" ]; then
        echo "ERROR: Database file not found: $DB_FILE. Cannot delete skipped files." | tee -a "$LOG_FILE"
        return 1
    fi

    local DELETE_LOG="$VRAMR_TEMP/logfiles/skipped_deletion.log"
    > "$DELETE_LOG"
    echo "Skipped texture deletion started at $(date)" >> "$DELETE_LOG"

    # Get count of textures to delete
    local TEXTURES_TO_DELETE=$("$SQLITE_CMD" "$DB_FILE" "SELECT COUNT(*) FROM textures WHERE processed = -1;")
    echo "Found $TEXTURES_TO_DELETE textures marked to be skipped and deleted"

    if [ "$TEXTURES_TO_DELETE" -eq 0 ]; then
        echo "No textures marked for skipping found."
        echo "$(date) No textures marked for skipping found." >> "$LOG_FILE"
        update_progress 80 # Progress update even if nothing to delete
        return 0
    fi

    # Create list of files to delete
    local DELETE_LIST_FILE=$(mktemp --tmpdir="$TEMP_DIR" delete_list.XXXXXX)
    # Select only the path, use printf '%s\0' for null termination
    "$SQLITE_CMD" "$DB_FILE" "SELECT path FROM textures WHERE processed = -1;" | while IFS= read -r line; do
        printf '%s\0' "$line"
    done > "$DELETE_LIST_FILE"

    # Progress tracking
    local PROGRESS_FILE=$(mktemp --tmpdir="$TEMP_DIR" delete_progress.XXXXXX)
    echo "0" > "$PROGRESS_FILE"
    touch "$PROGRESS_FILE.lock"

    # Progress monitor
    monitor_delete_progress() {
        local total=$1
        local progress_file=$2
        while true; do
            sleep 1
            local current_processed=$(cat "$progress_file" 2>/dev/null || echo 0)
            current_processed=${current_processed:-0}
            if [ "$current_processed" -ge "$total" ]; then
                better_progress_bar "$current_processed" "$total" "Deleting Skipped"
                break
            fi
            if ! ps -p $$ > /dev/null; then break; fi # Check parent process
            better_progress_bar "$current_processed" "$total" "Deleting Skipped"
        done
        local final_processed=$(cat "$progress_file" 2>/dev/null || echo "$total")
        final_processed=${final_processed:-$total}
        better_progress_bar "$final_processed" "$total" "Deleting Skipped"
        echo ""
    }

    monitor_delete_progress "$TEXTURES_TO_DELETE" "$PROGRESS_FILE" &
    local MONITOR_PID=$!

    # Create deletion script
    local DELETE_SCRIPT=$(mktemp --tmpdir="$TEMP_DIR" delete_script.XXXXXX)
    cat > "$DELETE_SCRIPT" << 'EOF'
#!/bin/bash
rel_path="$1"
progress_file="$2"
output_textures_dir="$3"
delete_log="$4"

file_to_delete="$output_textures_dir/$rel_path"

if [ -f "$file_to_delete" ]; then
    if rm -f "$file_to_delete"; then
        echo "Deleted: $rel_path" >> "$delete_log"
    else
        echo "Error deleting: $file_to_delete" >> "$delete_log"
    fi
else
    echo "Skipped deletion (not found): $file_to_delete" >> "$delete_log"
fi

# Update progress atomically
(
    flock -x 200
    current=$(cat "$progress_file" 2>/dev/null || echo 0)
    echo $((current + 1)) > "$progress_file"
) 200>"$progress_file.lock"
EOF

    # Make script executable
    chmod +x "$DELETE_SCRIPT"

    # Process using parallel or xargs (using null-terminated list)
    if command -v parallel &> /dev/null; then
        echo "Using GNU parallel for deleting skipped files..."
        # Use xargs -0 with parallel as a fallback if parallel itself fails?
        # Let's assume parallel works for now.
        # The previous edit incorrectly used xargs here instead of parallel.
        # Correcting to use parallel if available, otherwise xargs.
        cat "$DELETE_LIST_FILE" | parallel -0 -j "$THREAD_COUNT" "$DELETE_SCRIPT" {} "$PROGRESS_FILE" "$OUTPUT_TEXTURES_DIR" "$DELETE_LOG"
    else
        echo "GNU parallel not found, using xargs..."
        # Remove -n 1 as it's redundant with -I {}
        xargs -0 -P "$THREAD_COUNT" -I {} "$DELETE_SCRIPT" {} "$PROGRESS_FILE" "$OUTPUT_TEXTURES_DIR" "$DELETE_LOG" < "$DELETE_LIST_FILE"
    fi

    # Wait for all delete operations
    wait

    # Wait for monitor
    wait $MONITOR_PID 2>/dev/null || true

    local final_count=$(cat "$PROGRESS_FILE" 2>/dev/null || echo "$TEXTURES_TO_DELETE")
    echo "Deletion of skipped textures complete. Processed $final_count files."
    echo "$(date) Deletion of skipped textures complete. Processed $final_count files." >> "$LOG_FILE"

    # Cleanup
    rm -f "$DELETE_LIST_FILE" "$PROGRESS_FILE" "$PROGRESS_FILE.lock" "$DELETE_SCRIPT"

    # Remove empty directories potentially left behind
    find "$OUTPUT_TEXTURES_DIR" -type d -empty -delete 2>/dev/null || true

    update_progress 80 # Update progress after this step
    return 0
}
