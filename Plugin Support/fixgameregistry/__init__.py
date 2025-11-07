import mobase
from PyQt6.QtCore import QCoreApplication, qCritical, QDir, qDebug
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMessageBox

import os
import sys
import shutil
import subprocess
import re

# Import winreg only on Windows
if sys.platform == 'win32':
    import winreg
else:
    winreg = None

class FixGameRegKey(mobase.IPluginTool):

    # Use string constants for registry keys to support both Windows and Linux
    GAME_REGISTRY_KEYS = {
        "Enderal":    ("HKLM", "Software\\SureAI\\Enderal",                            "Install_Path"),
        "Fallout3":   ("HKLM", "Software\\Bethesda Softworks\\Fallout3",               "Installed Path"),
        "Fallout4":   ("HKLM", "Software\\Bethesda Softworks\\Fallout4",               "Installed Path"),
        "Fallout4VR": ("HKLM", "Software\\Bethesda Softworks\\Fallout 4 VR",           "Installed Path"),
        "FalloutNV":  ("HKLM", "Software\\Bethesda Softworks\\FalloutNV",              "Installed Path"),
        "Morrowind":  ("HKLM", "Software\\Bethesda Softworks\\Morrowind",              "Installed Path"),
        "Oblivion":   ("HKLM", "Software\\Bethesda Softworks\\Oblivion",               "Installed Path"),
        "Skyrim":     ("HKLM", "Software\\Bethesda Softworks\\Skyrim",                 "Installed Path"),
        "SkyrimSE":   ("HKLM", "Software\\Bethesda Softworks\\Skyrim Special Edition", "Installed Path"),
        "SkyrimVR":   ("HKLM", "Software\\Bethesda Softworks\\Skyrim VR",              "Installed Path"),
        "TTW":        ("HKLM", "Software\\Bethesda Softworks\\FalloutNV",              "Installed Path"),
        }

    def __init__(self):
        super().__init__()
        self._organizer = None
        self._parent = None

        # Better Wine detection: Check if WINEPREFIX is set (we're running under Wine/Proton)
        # Even if sys.platform says 'win32', if WINEPREFIX exists, we're on Linux with Wine
        self._winePrefix = os.environ.get('WINEPREFIX', '')
        self._isLinux = bool(self._winePrefix) or sys.platform.startswith('linux')

        # Check for required tools
        if self._isLinux:
            # Running in Wine/Proton - reg.exe should be available directly
            self._toolFound = shutil.which('reg') is not None or shutil.which('reg.exe') is not None
        else:
            # Native Windows - need PowerShell
            self._toolFound = shutil.which('powershell') is not None

    def __tr(self, str_):
        return QCoreApplication.translate("FixGameRegKey", str_)

    # IPlugin
    def init(self, organizer):
        self._organizer = organizer
        if (not self._organizer.onAboutToRun(lambda appName: self._checkInstallPath())):
            qCritical("Failed to register onAboutToRun callback!")
            return False
        return True

    def name(self):
        return "Fix Game Registry Key"

    def author(self):
        return "LostDragonist (updated by WilliamImm for 2.5.0, Linux support by NaK)"

    def description(self):
        return self.__tr("Checks the game's installation path registry key and fixes as needed")

    def version(self):
        return mobase.VersionInfo(1, 1, 0, 0)  # 1.1.0.0 - Added Linux/Wine support



    def settings(self):
        return [
            mobase.PluginSetting("debug_mode", self.__tr("Show dialogs and prompts (debug mode)"), False),
            ]

    # IPluginTool
    def displayName(self):
        return self.__tr("Check Game Registry Key")

    def tooltip(self):
        return self.description()

    def icon(self):
        return QIcon()

    def setParentWidget(self, widget):
        self._parent = widget

    def display(self):
        # Manual check via Tools menu - always show result
        if self._isActive():
           self._manualCheck()

    def _isActive(self):
        if self._getGameRegistryInfo() is None:
            active = False
        elif not self._toolFound:
            active = False
        else:
            active = True
        return active

    def _manualCheck(self):
        """Manual check triggered from Tools menu - always show result"""
        gameDirectory = self._organizer.managedGame().gameDirectory().canonicalPath()
        installPath = self._readInstallPath()

        if (gameDirectory != installPath):
            # Paths don't match - ask user
            if (gameDirectory == ''):
                gameDirectory = self.__tr('<invalid path>')
            if (installPath == ''):
                installPath = self.__tr('<invalid path>')

            answer = QMessageBox.question(self._parent,
                                          self.__tr("Registry key does not match"),
                                          self.__tr("The game's installation path in the registry does not match the managed game path in MO.\n\n"
                                          "Registry Game Path:\n\t{}\n"
                                          "Managed Game Path:\n\t{}\n\n"
                                          "Change the path in the registry to match the managed game path?").format(installPath, gameDirectory),
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                          QMessageBox.StandardButton.Yes)
            if (answer == QMessageBox.StandardButton.Yes):
                self._writeInstallPath()
                QMessageBox.information(self._parent,
                                      self.__tr("Success"),
                                      self.__tr("Registry updated successfully!"))
        else:
            # Paths match - show success
            QMessageBox.information(self._parent,
                                  self.__tr("Registry Check"),
                                  self.__tr("Game registry path is correct!\n\n"
                                          "Registry: {}\n"
                                          "Managed Game: {}").format(installPath, gameDirectory))

    def _checkInstallPath(self):
        if not self._isActive():
            return True

        gameDirectory = self._organizer.managedGame().gameDirectory().canonicalPath()
        installPath = self._readInstallPath()

        if (gameDirectory != installPath):
            # Paths don't match - need to fix
            if (gameDirectory == ''):
                gameDirectory = self.__tr('<invalid path>')
            if (installPath == ''):
                installPath = self.__tr('<invalid path>')

            # Check if debug mode is enabled
            debug_mode = self._organizer.pluginSetting(self.name(), "debug_mode")

            if debug_mode:
                # Debug mode: Ask user what to do
                answer = QMessageBox.question(self._parent,
                                              self.__tr("Registry key does not match"),
                                              self.__tr("The game's installation path in the registry does not match the managed game path in MO.\n\n"
                                              "Registry Game Path:\n\t{}\n"
                                              "Managed Game Path:\n\t{}\n\n"
                                              "Change the path in the registry to match the managed game path?").format(installPath, gameDirectory),
                                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                                              QMessageBox.StandardButton.Yes)
                if (answer == QMessageBox.StandardButton.Yes):
                    self._writeInstallPath()
                elif (answer == QMessageBox.StandardButton.Cancel):
                    return False
            else:
                # Normal mode: Auto-fix silently without prompting
                qDebug(f"Registry path mismatch detected - auto-fixing silently")
                self._writeInstallPath()

        return True

    def _readInstallPath(self):
        keyRoot, subKey, valueName = self._getGameRegistryInfo()
        installPath = ''

        if self._isLinux:
            # Linux/Wine/Proton: Use reg.exe directly (we're already inside Wine)
            try:
                reg_cmd = shutil.which('reg.exe') or shutil.which('reg')
                if not reg_cmd:
                    qCritical("reg.exe not found!")
                    return ''

                # Build the registry path
                regPath = f"{keyRoot}\\{subKey}"

                # Run reg query directly
                cmd = [reg_cmd, 'query', regPath, '/v', valueName, '/reg:32']

                qDebug(f"Running: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode == 0:
                    # Parse the output to extract the value
                    # Format: "    Installed Path    REG_SZ    Z:\path\to\game"
                    match = re.search(rf'{re.escape(valueName)}\s+REG_SZ\s+(.+)', result.stdout, re.IGNORECASE)
                    if match:
                        installPath = match.group(1).strip()
                        # Keep as Windows path - QDir will handle it in Wine
                        installPath = QDir(installPath).canonicalPath()
                        qDebug(f"Found registry value: {installPath}")
                else:
                    qDebug(f"Registry key not found or error: {result.stderr}")
            except Exception as e:
                qCritical(f"Failed to read registry on Linux: {e}")
        else:
            # Windows: Use winreg module
            try:
                # Convert string key to winreg constant
                if keyRoot == "HKLM":
                    key = winreg.HKEY_LOCAL_MACHINE
                else:
                    qCritical(f"Unsupported registry root: {keyRoot}")
                    return ''

                with winreg.OpenKey(key, subKey, 0, winreg.KEY_READ | winreg.KEY_WOW64_32KEY) as hKey:
                    try:
                        installPath, _ = winreg.QueryValueEx(hKey, valueName)
                        installPath = QDir(installPath).canonicalPath()
                    except FileNotFoundError:
                        installPath = ''
            except FileNotFoundError:
                installPath = ''

        return installPath

    def _writeInstallPath(self):
        # Figure out what MO is configured to
        gameDirectory = self._organizer.managedGame().gameDirectory().canonicalPath()

        # Get the registry info and check for possible problems
        keyRoot, subKey, valueName = self._getGameRegistryInfo()
        if keyRoot != "HKLM":
            qCritical("Only HKLM is supported!")
            return

        if self._isLinux:
            # Linux/Wine/Proton: Use reg.exe directly (we're already inside Wine)
            try:
                reg_cmd = shutil.which('reg.exe') or shutil.which('reg')
                if not reg_cmd:
                    qCritical("reg.exe not found!")
                    QMessageBox.critical(self._parent, "Error", "reg.exe not found in Wine environment!")
                    return

                # gameDirectory is already a Windows path when running in Wine
                winePath = gameDirectory

                # On 64-bit systems, we need to set BOTH registry paths:
                # 1. Normal 32-bit path with /reg:32
                # 2. Wow6432Node path for 64-bit compatibility

                # Build Wow6432Node path by replacing "Software\" at the start
                wow64_subkey = subKey.replace('Software\\', 'SOFTWARE\\Wow6432Node\\', 1) if subKey.startswith('Software\\') else f"SOFTWARE\\Wow6432Node\\{subKey}"

                registry_paths = [
                    (f"{keyRoot}\\{subKey}", '/reg:32'),  # 32-bit view
                    (f"{keyRoot}\\{wow64_subkey}", '/reg:64')  # 64-bit Wow6432Node view
                ]

                for regPath, reg_flag in registry_paths:
                    # Run reg add for both paths
                    cmd = [reg_cmd, 'add', regPath, '/v', valueName, '/d', winePath, '/f', reg_flag]

                    qDebug(f"Setting registry: {regPath}")
                    qDebug(f"Command: {' '.join(cmd)}")

                    result = subprocess.run(cmd, capture_output=True, text=True)

                    qDebug(f"Exit code: {result.returncode}")
                    if result.stdout:
                        qDebug(f"Output: {result.stdout}")
                    if result.stderr:
                        qDebug(f"Error: {result.stderr}")

                    if result.returncode != 0:
                        qCritical(f"Failed to set {regPath}: {result.stderr}")

                qDebug("Registry update completed for all paths!")
            except Exception as e:
                qCritical(f"Failed to write registry on Linux: {e}")
                import traceback
                qCritical(traceback.format_exc())
        else:
            # Windows: Use powershell to write to the registry as admin
            args = '\'add "{}\\{}" /v "{}" /d "{}" /f /reg:32\''.format("HKLM", subKey, valueName, gameDirectory.replace("'", "''"))
            cmd = ['powershell', 'Start-Process', '-Verb', 'runAs', 'reg', '-ArgumentList', args]
            try:
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                qDebug("Running the command \"{}\"".format(" ".join(cmd)))
                subprocess.check_call(cmd, startupinfo=si)
            except subprocess.CalledProcessError as e:
                qCritical("Powershell non-zero exit status: {}, {}".format(e.returncode, e.output))

    def _getGameRegistryInfo(self):
        gameName = self._organizer.managedGame().gameShortName()
        if gameName in self.GAME_REGISTRY_KEYS:
            return self.GAME_REGISTRY_KEYS[gameName]
        else:
            return None

def createPlugin():
    return FixGameRegKey()