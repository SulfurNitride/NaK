# Fix Game Registry Key - Linux/Wine Support

**Modified by NaK Linux Modding Helper**
Version: 1.1.0.0

Original by: LostDragonist (updated by WilliamImm for MO2 2.5.0)

## What's New in This Version

This is a modified version of the "Fix Game Registry Key" plugin that adds **full Linux/Wine/Proton support** while maintaining Windows compatibility.

### Changes:
- ✅ **Linux Support**: Works with Wine and Proton prefixes
- ✅ **Auto-detects platform**: Uses `wine reg` on Linux, `powershell` on Windows
- ✅ **WINEPREFIX aware**: Automatically uses the correct Wine prefix from MO2's environment
- ✅ **Path conversion**: Handles Unix ↔ Windows path conversion (Z: drive)
- ✅ **No UAC prompts on Linux**: Wine doesn't need elevated permissions for registry changes
- ✅ **Proper plugin structure**: Renamed to `__init__.py` and includes `import mobase`

## Installation

### For MO2 on Linux (Wine/Proton):

1. Copy the entire `fixgameregistry` folder to your MO2 plugins directory:
   ```bash
   cp -r fixgameregistry /path/to/MO2/plugins/
   ```

2. Make sure Wine is available in your PATH (it usually is when running MO2 through Proton)

3. Launch MO2 - the plugin should auto-load

4. Check if it's loaded: Go to **Tools → Tool Plugins** → you should see "Check Game Registry Key"

### For MO2 on Windows:

Same installation as before - just copy the folder to `<MO2 install>/plugins`

## How It Works

### On Linux with Wine/Proton:
When MO2 runs through Wine/Proton, the plugin:
- **Detects Wine environment** by checking for `WINEPREFIX` environment variable
- **Uses `reg.exe` directly** (Wine's built-in registry tool)
- **No external wine calls needed** - already running inside Wine
- **Handles Windows paths natively** - paths are already in Z:\ format
- **No UAC prompts** - Wine doesn't need elevated permissions

### On Windows:
- Uses Python's `winreg` module to read registry
- Uses PowerShell with elevated permissions to write registry (UAC prompt)

## Supported Games

- Skyrim (all releases)
- Fallout 3
- Fallout New Vegas (including TTW)
- Fallout 4 (including VR)
- Oblivion
- Morrowind
- Enderal (standalone)

## FAQ

### Does this work with Proton prefixes?
Yes! When MO2 runs through Proton, it sets the `WINEPREFIX` environment variable, which this plugin uses to find and modify the correct registry.

### Do I need to set WINEPREFIX manually?
No, MO2 automatically sets it when running through Wine/Proton.

### What if the plugin doesn't activate?
The plugin checks for:
1. Supported game (from the list above)
2. Wine or wine64 in PATH (on Linux) or PowerShell (on Windows)

If either check fails, the plugin won't activate.

### Can I still use this on Windows?
Yes! All original Windows functionality is preserved. The plugin detects the platform and uses the appropriate method.

## License

MIT License (same as original)

You are free to use, modify, and distribute this plugin.

## Credits

- **LostDragonist**: Original plugin creator
- **WilliamImm**: MO2 2.5.0 compatibility update
- **NaK Linux Modding Helper**: Linux/Wine/Proton support

## Troubleshooting

### Plugin shows "mobase is not defined" error
This shouldn't happen with this version as `import mobase` is already included.

### Registry changes don't apply on Linux
- Check that Wine is installed and in your PATH
- Check MO2's log for error messages (look for qCritical/qDebug output)
- Verify your WINEPREFIX is correct: `echo $WINEPREFIX`

### Game still can't find installation path
Try manually running the "Check Game Registry Key" tool from **Tools → Tool Plugins** menu.

### Want to see registry fix dialogs?

By default, the plugin automatically fixes registry mismatches silently in the background. If you want to see prompts and dialogs for debugging:

1. Go to **MO2 Settings → Plugins**
2. Find "Fix Game Registry Key"
3. Enable the "Show dialogs and prompts (debug mode)" setting
