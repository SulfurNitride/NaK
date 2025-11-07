# Phase 2: NaK Storage Migration Implementation

## Overview
Phase 1 implemented basic symlink support for new installations. Phase 2 will handle migrating existing installations with all their scripts and symlinks intact.

---

## What Needs Fixing When NaK Folder Moves

### 1. Launch Scripts (`.sh` files in prefix directories)
**Location:** `~/NaK/Prefixes/{prefix_name}/`

**Files:**
- `launch_mo2.sh` / `launch_vortex.sh`
- `kill_prefix.sh`
- `fix_game_registry.sh`
- `nxm_*.sh` (in `~/NaK/NXM_Links/`)

**Problem:** Hardcoded absolute paths like:
```bash
PROTON_GE="/home/luke/NaK/ProtonGE/active"
PREFIX="/home/luke/NaK/Prefixes/mo2_skyrim/pfx"
```

**Solution:** Regenerate all scripts with new paths

---

### 2. Symlinks to Launch Scripts
**Location:** Inside mod manager install directories (e.g., `ModOrganizer2/`)

**Files:**
- `"Launch MO2"` → `~/NaK/Prefixes/.../launch_mo2.sh`
- `"Kill MO2 Prefix"` → `~/NaK/Prefixes/.../kill_prefix.sh`
- `"Fix Game Registry"` → `~/NaK/Prefixes/.../fix_game_registry.sh`

**Problem:** Absolute symlinks point to old NaK location

**Solution:** Recreate symlinks pointing to new location

---

### 3. NXM Handler Configuration
**Location:**
- `~/NaK/NXM_Links/nxm_*.sh` (scripts)
- `~/.local/share/applications/nxm-handler.desktop` (desktop file)
- `NAK_MANAGED_INSTANCE.txt` marker files in each prefix

**Problem:**
- Scripts contain hardcoded paths
- Marker files reference absolute script paths
- Desktop file may reference old paths

**Solution:**
- Regenerate NXM scripts
- Update marker files
- Update desktop file

---

### 4. Save Symlinks (Bethesda Games)
**Location:** Various game save directories

**Files:** Symlinks to `~/NaK/Prefixes/.../drive_c/users/.../Documents/My Games/...`

**Problem:** May use absolute paths to old NaK location

**Solution:** Recreate save symlinks if using absolute paths (relative symlinks will work)

---

### 5. Hardcoded Path References in Python Code
**Files to Update:**
- `src/utils/launch_script_generator.py:42` - `Path.home() / "NaK"`
- `src/utils/nxm_handler_manager.py:31-34` - `Path.home() / "NaK"`
- `src/core/unverum_installer.py`
- `src/mod_managers/vortex/installer.py`
- `src/mod_managers/mo2/installer.py`
- `src/utils/save_symlinker.py`
- Any other files found by: `grep -r "Path.home() / \"NaK\""`

**Solution:** Create a central helper function that returns the correct NaK path

---

## Implementation Strategy

### Step 1: Create Central Path Helper
```python
# src/utils/nak_paths.py
from pathlib import Path
from src.utils.settings_manager import SettingsManager

def get_nak_home() -> Path:
    """Get the actual NaK home directory (resolves symlinks)"""
    nak_path = Path.home() / "NaK"

    # If it's a symlink, resolve it to get real location
    if nak_path.is_symlink():
        return nak_path.resolve()

    return nak_path
```

### Step 2: Replace All Hardcoded References
Replace all instances of `Path.home() / "NaK"` with `get_nak_home()`

### Step 3: Implement Migration Tool
```python
class NaKMigrationTool:
    """Handles migrating existing NaK installations to new location"""

    def migrate(self, new_location: Path, move_data: bool = True):
        """
        Migrate NaK folder to new location

        Steps:
        1. Move/copy NaK folder to new location
        2. Scan all prefixes for scripts and symlinks
        3. Regenerate all launch scripts with new paths
        4. Recreate all symlinks pointing to launch scripts
        5. Update NXM handler scripts and markers
        6. Verify save symlinks (recreate if needed)
        7. Create ~/NaK symlink to new location
        8. Save new location to settings
        """
        pass
```

### Step 4: Detection & Scanning
```python
def scan_existing_installations(self):
    """
    Scan ~/NaK/Prefixes/ for all mod manager installations

    Returns dict with:
    - prefix_path
    - manager_type (MO2/Vortex)
    - install_dir
    - scripts_to_regenerate []
    - symlinks_to_recreate []
    """
    pass
```

### Step 5: Script Regeneration
```python
def regenerate_all_scripts(self, prefix_info: dict):
    """
    Regenerate all .sh scripts for a prefix with new paths

    - Read marker file to get original config
    - Regenerate launch script
    - Regenerate kill script
    - Regenerate registry fix script
    - Regenerate NXM script
    """
    pass
```

### Step 6: Symlink Recreation
```python
def recreate_symlinks(self, prefix_info: dict):
    """
    Recreate symlinks in mod manager install directory

    - Find all symlinks pointing to old scripts
    - Delete old symlinks
    - Create new symlinks pointing to new script locations
    """
    pass
```

---

## User Experience (UI Flow)

### Migration Wizard (Phase 2)

When user changes storage location in Settings:

```
┌─────────────────────────────────────┐
│  Migrate NaK Storage Location       │
├─────────────────────────────────────┤
│                                     │
│  Detected Installations:            │
│  ✓ Skyrim SE MO2                   │
│  ✓ Fallout 4 Vortex                │
│  ✓ Starfield MO2                   │
│                                     │
│  These will be migrated:            │
│  • Launch scripts (3 per install)  │
│  • NXM handler configuration       │
│  • Save symlinks                   │
│                                     │
│  [ ] Move data (recommended)       │
│  [ ] Start fresh (backup old)      │
│                                     │
│     [Cancel]  [Migrate]            │
└─────────────────────────────────────┘
```

Progress dialog during migration:
```
┌─────────────────────────────────────┐
│  Migrating Storage...               │
├─────────────────────────────────────┤
│  [████████░░░░░░░░░░] 45%          │
│                                     │
│  ✓ Moved data to new location      │
│  ✓ Regenerated launch scripts      │
│  ⟳ Recreating symlinks...          │
│    - Skyrim SE MO2                 │
│                                     │
└─────────────────────────────────────┘
```

---

## Testing Checklist

- [ ] Migrate with existing MO2 installation
- [ ] Migrate with existing Vortex installation
- [ ] Verify launch scripts work after migration
- [ ] Verify kill scripts work after migration
- [ ] Verify registry fix scripts work
- [ ] Verify NXM links route to correct instance
- [ ] Verify save symlinks still work
- [ ] Test rollback (restore to original location)
- [ ] Test with multiple mod managers
- [ ] Test with no existing installations (fresh setup)

---

## Edge Cases to Handle

1. **Partial migration failure** - Rollback mechanism
2. **Insufficient space** on target drive - Pre-check before migration
3. **Target location has existing NaK folder** - Merge or error?
4. **Broken symlinks before migration** - Log warnings, continue
5. **User cancels mid-migration** - Rollback or resume?
6. **NaK folder already a symlink** - Update existing symlink
7. **Multiple mod managers for same game** - Identify all instances

---

## Files to Create

1. `src/utils/nak_paths.py` - Central path helper
2. `src/utils/nak_migration_tool.py` - Migration logic
3. `nak-flet/dialogs/migration_wizard.py` - Migration UI
4. `tests/test_nak_migration.py` - Unit tests

---

## Files to Modify

1. All files with `Path.home() / "NaK"` hardcoded
2. `src/utils/launch_script_generator.py` - Use central path helper
3. `src/utils/nxm_handler_manager.py` - Use central path helper
4. `nak-flet/dialogs/settings_dialog.py` - Add migration wizard launch
5. `src/utils/nak_storage_manager.py` - Add migration support

---

## Priority Order

### High Priority (Phase 2A)
1. Create central path helper
2. Replace hardcoded paths in Python code
3. Basic migration tool (scripts only)

### Medium Priority (Phase 2B)
4. Symlink recreation
5. NXM handler migration
6. Full migration wizard UI

### Low Priority (Phase 2C)
7. Save symlink handling
8. Rollback mechanism
9. Advanced edge cases

---

## Notes

- Migration should be **optional** - users can start fresh if they prefer
- Always create backups before migration
- Provide clear progress feedback
- Log everything for debugging
- Test extensively with real mod setups
