package vortex

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/sulfurnitride/nak/internal/dependencies"
	"github.com/sulfurnitride/nak/internal/logging"
	"github.com/sulfurnitride/nak/internal/ui"
	"github.com/sulfurnitride/nak/internal/utils"
)

type VortexInstaller struct {
	logger *logging.Logger
}

type GitHubRelease struct {
	TagName string `json:"tag_name"`
	Assets  []struct {
		Name               string `json:"name"`
		BrowserDownloadURL string `json:"browser_download_url"`
	} `json:"assets"`
}

func NewVortexInstaller() *VortexInstaller {
	return &VortexInstaller{
		logger: logging.GetLogger(),
	}
}

func (v *VortexInstaller) DownloadVortex() error {
	v.logger.Info("Starting Vortex download and installation process")
	ui.PrintSection("Download and Install Vortex")

	// Check for required dependencies
	if err := v.checkDownloadDependencies(); err != nil {
		return err
	}

	// Always use Proton for Vortex installation (more reliable than system Wine)
	ui.PrintInfo("Using Proton for Vortex installation (more reliable than system Wine).")

	// Show progress info
	ui.PrintInfo("Starting Vortex download...")

	// Fetch the latest release info from GitHub
	ui.PrintInfo("Fetching latest release information from GitHub...")
	releaseInfo, err := v.fetchLatestRelease()
	if err != nil {
		return fmt.Errorf("failed to fetch release information: %w", err)
	}

	ui.PrintInfo("Release information fetched successfully")

	// Extract release version
	version := strings.TrimPrefix(releaseInfo.TagName, "v")
	ui.PrintSuccess(fmt.Sprintf("Latest version: %s", version))

	// Find the correct asset (vortex-setup-*.exe)
	downloadURL := ""
	for _, asset := range releaseInfo.Assets {
		if strings.HasPrefix(asset.Name, "vortex-setup-") && strings.HasSuffix(asset.Name, ".exe") {
			downloadURL = asset.BrowserDownloadURL
			break
		}
	}

	if downloadURL == "" {
		return fmt.Errorf("could not find appropriate vortex-setup-*.exe asset in the latest release")
	}

	filename := filepath.Base(downloadURL)
	ui.PrintInfo(fmt.Sprintf("Found asset: %s", filename))

	// Create a temporary directory for the download
	tempDir, err := os.MkdirTemp("", "vortex-download-*")
	if err != nil {
		return fmt.Errorf("failed to create temporary directory: %w", err)
	}
	// Don't defer cleanup - we need the file for installation

	tempFile := filepath.Join(tempDir, filename)

	// Download the file
	ui.PrintInfo(fmt.Sprintf("Downloading Vortex v%s...", version))
	ui.PrintInfo(fmt.Sprintf("From: %s", downloadURL))
	ui.PrintInfo(fmt.Sprintf("To: %s", tempFile))

	if err := utils.DownloadFile(downloadURL, tempFile); err != nil {
		return fmt.Errorf("failed to download Vortex: %w", err)
	}

	ui.PrintInfo("Download completed successfully")

	// Ask user where to install Vortex
	installDir, err := ui.GetInputWithTabCompletion("Install to directory", filepath.Join(utils.GetHomeDirSafe(), "Vortex"))
	if err != nil {
		return err
	}

	// Create the directory if it doesn't exist
	if err := utils.CreateDirectory(installDir); err != nil {
		return fmt.Errorf("failed to create directory %s: %w", installDir, err)
	}

	// Convert Linux path to proper Wine path (Z:\path\with\backslashes)
	wineInstallDir := "Z:" + strings.ReplaceAll(installDir, "/", "\\")

	// Always use Proton for Vortex installation
	ui.PrintInfo("We need to select a game to use its Proton prefix for Vortex installation.")
	ui.PrintInfo("Note: This is only for the installation process. Vortex will be installed to your chosen directory.")

	if err := utils.CheckDependencies(); err != nil {
		return err
	}

	games, err := utils.GetSteamGames()
	if err != nil {
		return fmt.Errorf("failed to get Steam games: %w", err)
	}

	if len(games) == 0 {
		return fmt.Errorf("no Steam games found. A game is needed to use its Proton prefix")
	}

	// Auto-select if only one game found
	var selectedGame utils.Game
	if len(games) == 1 {
		selectedGame = games[0]
		v.logger.Info(fmt.Sprintf("Auto-selected only game: %s (AppID: %s)", selectedGame.Name, selectedGame.AppID))
	} else {
		// Create menu for multiple games
		menuItems := make([]ui.MenuItem, len(games))
		for i, game := range games {
			menuItems[i] = ui.MenuItem{
				ID:          i + 1,
				Title:       fmt.Sprintf("%s (AppID: %s)", game.Name, game.AppID),
				Description: "Steam game",
			}
		}

		menu := ui.Menu{
			Title:    "Select Game for Proton Prefix (Installation Only)",
			Items:    menuItems,
			ExitText: "Cancel",
		}

		choice, err := ui.DisplayMenu(menu)
		if err != nil {
			return fmt.Errorf("menu error: %w", err)
		}

		if choice == len(games)+1 {
			return fmt.Errorf("no game selected")
		}

		if choice > 0 && choice <= len(games) {
			selectedGame = games[choice-1]
		} else {
			return fmt.Errorf("invalid selection")
		}
	}

	// Find the prefix path for the selected game
	steamRoot, err := utils.GetSteamRoot()
	if err != nil {
		return fmt.Errorf("could not find Steam root: %w", err)
	}

	compatDataPath, err := utils.FindGameCompatData(selectedGame.AppID, steamRoot)
	if err != nil {
		return fmt.Errorf("could not find game compatdata: %w", err)
	}

	prefixPath := filepath.Join(compatDataPath, "pfx")
	if !utils.DirectoryExists(prefixPath) {
		return fmt.Errorf("could not find Proton prefix at: %s", prefixPath)
	}

	// Install Vortex using the selected game's Proton prefix
	ui.PrintInfo(fmt.Sprintf("Installing Vortex to %s using %s's Proton prefix...", installDir, selectedGame.Name))
	ui.PrintInfo("This may take a few minutes. Please be patient.")
	ui.PrintInfo(fmt.Sprintf("Wine path: %s", wineInstallDir))

	// Run the installation command
	ui.PrintInfo(fmt.Sprintf("Using temp file: %s", tempFile))
	ui.PrintInfo(fmt.Sprintf("Checking if temp file exists: %t", utils.FileExists(tempFile)))
	err = v.runWithProtonWine(prefixPath, tempFile, "/S", fmt.Sprintf("/D=%s", wineInstallDir))

	// Check if Vortex was actually installed, regardless of stderr output
	vortexExe := filepath.Join(installDir, "Vortex.exe")
	if utils.FileExists(vortexExe) {
		v.logger.Info("Vortex installation completed successfully (Vortex.exe found)")
		ui.PrintSuccess(fmt.Sprintf("Vortex v%s has been successfully installed to:", version))
		ui.PrintInfo(installDir)
	} else if err != nil {
		v.logger.Error("Proton installation failed")
		return fmt.Errorf("failed to install Vortex with Proton: %w", err)
	} else {
		// Command succeeded but Vortex.exe not found - might be a different structure
		v.logger.Warning("Installation command succeeded but Vortex.exe not found at expected location")
		ui.PrintWarning("Warning: Vortex.exe was not found at the expected location.")
		ui.PrintInfo("It's possible the installation completed but with a different structure.")
		ui.PrintInfo(fmt.Sprintf("Please check %s to verify the installation.", installDir))
	}

	// Clean up temporary files
	os.RemoveAll(tempDir)

	// Ask if user wants to add to Steam
	ui.PrintInfo("Would you like to add Vortex to Steam as a non-Steam game?")
	confirmed, err := ui.ConfirmAction("Add to Steam?")
	if err != nil {
		return err
	}

	if confirmed {
		return v.addVortexToSteam(installDir)
	}

	return nil
}

func (v *VortexInstaller) checkDownloadDependencies() error {
	// Check for curl or wget
	if !utils.CommandExists("curl") && !utils.CommandExists("wget") {
		return fmt.Errorf("curl or wget is required for downloads")
	}

	// Check for jq
	if !utils.CommandExists("jq") {
		return fmt.Errorf("jq is required for parsing JSON")
	}

	return nil
}

func (v *VortexInstaller) fetchLatestRelease() (*GitHubRelease, error) {
	resp, err := http.Get("https://api.github.com/repos/Nexus-Mods/Vortex/releases/latest")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, resp.Status)
	}

	var release GitHubRelease
	if err := json.NewDecoder(resp.Body).Decode(&release); err != nil {
		return nil, err
	}

	return &release, nil
}

func (v *VortexInstaller) runWithProtonWine(prefixPath, command string, args ...string) error {
	// Get necessary paths
	steamRoot, err := utils.GetSteamRoot()
	if err != nil {
		return fmt.Errorf("could not find Steam root: %w", err)
	}

	protonPath, err := v.findProtonPath(steamRoot)
	if err != nil {
		return fmt.Errorf("could not find Proton installation: %w", err)
	}

	// Run the command with Proton's Wine (matching original bash script exactly)
	cmd := exec.Command("env",
		fmt.Sprintf("STEAM_COMPAT_CLIENT_INSTALL_PATH=%s", steamRoot),
		fmt.Sprintf("STEAM_COMPAT_DATA_PATH=%s", filepath.Dir(prefixPath)),
		protonPath, "run", command)
	cmd.Args = append(cmd.Args, args...)

	// Capture output for debugging
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	ui.PrintInfo(fmt.Sprintf("Running command: %s", strings.Join(cmd.Args, " ")))

	err = cmd.Run()
	if err != nil {
		v.logger.Error("Command failed with error: " + err.Error())
		if stdout.Len() > 0 {
			v.logger.Info("stdout: " + stdout.String())
		}
		if stderr.Len() > 0 {
			v.logger.Error("stderr: " + stderr.String())
		}
		return err
	}

	ui.PrintInfo("Command completed successfully")
	if stdout.Len() > 0 {
		ui.PrintInfo("stdout: " + stdout.String())
	}
	if stderr.Len() > 0 {
		ui.PrintInfo("stderr: " + stderr.String())
	}

	return nil
}

func (v *VortexInstaller) findProtonPath(steamRoot string) (string, error) {
	// Try to find Proton_Experimental in Steam libraries
	libraryFoldersPath := filepath.Join(steamRoot, "steamapps", "libraryfolders.vdf")

	// Read libraryfolders.vdf to find all Steam library paths
	steamPaths := []string{steamRoot}

	if utils.FileExists(libraryFoldersPath) {
		content, err := os.ReadFile(libraryFoldersPath)
		if err == nil {
			lines := strings.Split(string(content), "\n")
			for _, line := range lines {
				line = strings.TrimSpace(line)
				if strings.Contains(line, "\"path\"") {
					// Extract path from the line - handle both quoted and unquoted formats
					var libraryPath string
					if strings.Contains(line, "\"") {
						// Quoted format: "path"          "/home/luke/Downloads/TempSteamFolder"
						parts := strings.Split(line, "\"")
						if len(parts) >= 4 {
							libraryPath = parts[3]
						}
					} else {
						// Unquoted format: path          /home/luke/Downloads/TempSteamFolder
						parts := strings.Fields(line)
						if len(parts) >= 2 {
							libraryPath = parts[1]
						}
					}

					if libraryPath != "" {
						steamPaths = append(steamPaths, libraryPath)
					}
				}
			}
		}
	}

	// Look for Proton_Experimental in each library
	for _, path := range steamPaths {
		protonCandidate := filepath.Join(path, "steamapps", "common", "Proton - Experimental", "proton")
		if utils.FileExists(protonCandidate) {
			v.logger.Info(fmt.Sprintf("Found Proton path: %s", protonCandidate))
			return protonCandidate, nil
		}
	}

	return "", fmt.Errorf("Proton - Experimental not found in Steam libraries")
}

func (v *VortexInstaller) addVortexToSteam(vortexDir string) error {
	if vortexDir == "" || !utils.DirectoryExists(vortexDir) {
		return fmt.Errorf("invalid Vortex directory")
	}

	vortexExe := filepath.Join(vortexDir, "Vortex.exe")
	if !utils.FileExists(vortexExe) {
		return fmt.Errorf("Vortex.exe not found in %s", vortexDir)
	}

	ui.PrintSection("Add Vortex to Steam")

	// Ask for custom name
	vortexName, err := ui.GetInput("What name would you like to use for Vortex in Steam?", "Vortex")
	if err != nil {
		return err
	}

	if vortexName == "" {
		vortexName = "Vortex"
	}

	// Add to Steam using VDF manipulation
	v.logger.Info("Adding Vortex to Steam using steamtinkerlaunch...")
	ui.PrintInfo("Adding Vortex to Steam using steamtinkerlaunch...")

	// Use steamtinkerlaunch instead of VDF manipulation
	v.logger.Info("Adding Vortex to Steam using steamtinkerlaunch...")
	ui.PrintInfo("Adding Vortex to Steam using steamtinkerlaunch...")

	// Build the steamtinkerlaunch command
	args := []string{
		"ansg", // Add non-Steam game
		fmt.Sprintf("--appname=%s", vortexName),
		fmt.Sprintf("--exepath=%s", vortexExe),
		fmt.Sprintf("--startdir=%s", filepath.Dir(vortexExe)),
		"--compatibilitytool=default",
		"--launchoptions=",
	}

	v.logger.Info("Running steamtinkerlaunch command...")
	ui.PrintInfo("Running steamtinkerlaunch command...")

	// Run steamtinkerlaunch (system or embedded)
	output, err := utils.RunEmbeddedSTLWithOutput(args...)

	if err != nil {
		v.logger.Error("Failed to add Vortex to Steam: " + err.Error())
		v.logger.Error("steamtinkerlaunch output: " + string(output))
		ui.PrintWarning("Failed to add Vortex to Steam: " + err.Error())
		ui.PrintInfo("steamtinkerlaunch output: " + string(output))
		return fmt.Errorf("failed to add Vortex to Steam: %w", err)
	}

	v.logger.Info("Successfully added Vortex to Steam using steamtinkerlaunch")
	ui.PrintSuccess("Successfully added Vortex to Steam using steamtinkerlaunch")
	ui.PrintInfo("Output: " + string(output))

	ui.PrintSuccess("Vortex has been added to Steam successfully!")
	ui.PrintInfo("You can now launch Vortex from your Steam library.")
	ui.PrintInfo("Important: You should now:")
	ui.PrintInfo("1. Right-click on Vortex in Steam → Properties")
	ui.PrintInfo("2. Check 'Force the use of a specific Steam Play compatibility tool'")
	ui.PrintInfo("3. Select 'Proton_Experimental' from the dropdown menu")

	// Ask about restarting Steam
	restartConfirmed, err := ui.ConfirmAction("Do you want to restart Steam to ensure proper integration?")
	if err != nil {
		return err
	}

	if restartConfirmed {
		if err := utils.RestartSteam(); err != nil {
			v.logger.Warning("Failed to restart Steam: " + err.Error())
			ui.PrintWarning("Failed to restart Steam: " + err.Error())
			ui.PrintInfo("Please restart Steam manually.")
		}
	}

	// Ask about setting up dependencies
	confirmed, err := ui.ConfirmAction("Do you want to setup dependencies for " + vortexName + "?")
	if err != nil {
		return err
	}

	if confirmed {
		ui.ClearScreen()
		// Provide instructions to run the mod manager once
		ui.PrintInfo("To setup dependencies, you need to:")
		ui.PrintInfo("1. Launch " + vortexName + " from Steam")
		ui.PrintInfo("2. Let it run for a moment (it may show errors, that's normal)")
		ui.PrintInfo("3. Close " + vortexName + " completely")
		ui.PrintInfo("4. Come back here and press Enter when done")

		// Wait for user confirmation
		_, err = ui.GetInput("Press Enter when you've launched and closed "+vortexName+"...", "")
		if err != nil {
			return err
		}

		// Use the existing dependency installer system
		dependencyInstaller := dependencies.NewDependencyInstaller()
		if err := dependencyInstaller.InstallBasicDependencies(); err != nil {
			v.logger.Warning("Failed to setup dependencies: " + err.Error())
			ui.PrintWarning("Failed to setup dependencies: " + err.Error())
			ui.PrintInfo("You can setup dependencies manually later using protontricks.")
		}
	}

	return nil
}

func (v *VortexInstaller) SetupExistingVortex() error {
	ui.PrintSection("Set Up Existing Vortex")

	ui.PrintInfo("Please specify the location of your existing Vortex installation.")
	vortexDir, err := ui.GetInputWithTabCompletion("Vortex directory", "")
	if err != nil {
		return err
	}

	if vortexDir == "" {
		return fmt.Errorf("no directory specified")
	}

	if !utils.DirectoryExists(vortexDir) {
		return fmt.Errorf("directory does not exist: %s", vortexDir)
	}

	vortexExe := filepath.Join(vortexDir, "Vortex.exe")
	if !utils.FileExists(vortexExe) {
		return fmt.Errorf("Vortex.exe not found in %s", vortexDir)
	}

	ui.PrintSuccess(fmt.Sprintf("Found Vortex.exe in: %s", vortexDir))

	// Ask if user wants to add to Steam
	ui.PrintInfo("Would you like to add this Vortex installation to Steam as a non-Steam game?")
	confirmed, err := ui.ConfirmAction("Add to Steam?")
	if err != nil {
		return err
	}

	if confirmed {
		return v.addVortexToSteam(vortexDir)
	}

	return nil
}

func (v *VortexInstaller) SetupVortexNxmHandler() error {
	ui.PrintSection("Vortex NXM Link Handler Setup")

	// Check for Steam and get Steam root
	steamRoot, err := utils.GetSteamRoot()
	if err != nil {
		ui.PrintWarning("Could not find Steam installation: " + err.Error())
		ui.PrintInfo("Please ensure Steam is installed and running.")
		return nil
	}

	// Get non-Steam games and select one
	games, err := utils.GetNonSteamGames()
	if err != nil {
		return fmt.Errorf("could not get non-Steam games: %w", err)
	}

	if len(games) == 0 {
		return fmt.Errorf("no non-Steam games found")
	}

	// Auto-select if only one game found
	var selectedGame utils.Game
	if len(games) == 1 {
		selectedGame = games[0]
		v.logger.Info(fmt.Sprintf("Auto-selected only game: %s (AppID: %s)", selectedGame.Name, selectedGame.AppID))
	} else {
		// Create menu for multiple games
		menuItems := make([]ui.MenuItem, len(games))
		for i, game := range games {
			menuItems[i] = ui.MenuItem{
				ID:          i + 1,
				Title:       fmt.Sprintf("%s (AppID: %s)", game.Name, game.AppID),
				Description: "Non-Steam game",
			}
		}

		menu := ui.Menu{
			Title:    "Select Game for NXM Handler",
			Items:    menuItems,
			ExitText: "Cancel",
		}

		choice, err := ui.DisplayMenu(menu)
		if err != nil {
			return fmt.Errorf("menu error: %w", err)
		}

		if choice == len(games)+1 {
			return fmt.Errorf("user cancelled")
		}

		if choice > 0 && choice <= len(games) {
			selectedGame = games[choice-1]
		} else {
			return fmt.Errorf("invalid selection")
		}
	}

	// Find Proton path
	protonPath, err := v.findProtonPath(steamRoot)
	if err != nil {
		return fmt.Errorf("could not find Proton_Experimental: %w", err)
	}

	// Ask for Vortex.exe path
	var vortexPath string
	for {
		path, err := ui.GetInputWithTabCompletion("Enter FULL path to Vortex.exe (or 'b' to go back)", "")
		if err != nil {
			return err
		}

		// Check if user wants to go back
		if strings.ToLower(path) == "b" {
			v.logger.Info("User cancelled Vortex NXM handler setup")
			return nil
		}

		if utils.FileExists(path) {
			vortexPath = path
			v.logger.Info("Selected Vortex.exe: " + vortexPath)
			break
		}

		ui.PrintError("File not found! Try again or enter 'b' to go back.")
		v.logger.Warning("Invalid path: " + path)
	}

	// Create desktop file
	homeDir, err := utils.GetHomeDir()
	if err != nil {
		return fmt.Errorf("could not get home directory: %w", err)
	}

	steamCompatDataPath := filepath.Join(steamRoot, "steamapps", "compatdata", selectedGame.AppID)
	desktopFile := filepath.Join(homeDir, ".local", "share", "applications", "vortex-nxm-handler.desktop")

	// Create applications directory if it doesn't exist
	applicationsDir := filepath.Dir(desktopFile)
	if err := utils.CreateDirectory(applicationsDir); err != nil {
		return fmt.Errorf("could not create applications directory: %w", err)
	}

	// Create desktop file content
	execCommand := fmt.Sprintf(`bash -c 'env "STEAM_COMPAT_CLIENT_INSTALL_PATH=%s" "STEAM_COMPAT_DATA_PATH=%s" "%s" run "%s" "-d" "%%u"'`,
		steamRoot, steamCompatDataPath, protonPath, vortexPath)

	desktopContent := fmt.Sprintf(`[Desktop Entry]
Type=Application
Categories=Game;
Exec=%s
Name=Vortex NXM Handler
MimeType=x-scheme-handler/nxm;x-scheme-handler/nxm-protocol;
NoDisplay=true
`, execCommand)

	// Write desktop file
	if err := os.WriteFile(desktopFile, []byte(desktopContent), 0755); err != nil {
		return fmt.Errorf("could not create desktop file: %w", err)
	}

	// Register MIME handlers
	if err := v.registerVortexMimeHandlers(); err != nil {
		ui.PrintWarning("Could not register MIME handlers: " + err.Error())
	}

	ui.PrintSuccess("Vortex NXM Handler setup complete!")
	v.logger.Info("Vortex NXM Handler setup complete")

	return nil
}

func (v *VortexInstaller) registerVortexMimeHandlers() error {
	// Register both nxm and nxm-protocol handlers
	ui.PrintInfo("Registering nxm:// and nxm-protocol:// handlers...")

	// Register for nxm
	if err := v.registerSingleMimeHandler("nxm"); err != nil {
		v.logger.Warning("Failed to register nxm handler: " + err.Error())
	} else {
		ui.PrintSuccess("Success for nxm")
	}

	// Register for nxm-protocol
	if err := v.registerSingleMimeHandler("nxm-protocol"); err != nil {
		v.logger.Warning("Failed to register nxm-protocol handler: " + err.Error())
	} else {
		ui.PrintSuccess("Success for nxm-protocol")
	}

	return nil
}

func (v *VortexInstaller) registerSingleMimeHandler(protocol string) error {
	// Try xdg-mime first
	cmd := exec.Command("xdg-mime", "default", "vortex-nxm-handler.desktop", fmt.Sprintf("x-scheme-handler/%s", protocol))
	if err := cmd.Run(); err == nil {
		v.logger.Info(fmt.Sprintf("Success (via xdg-mime) for %s", protocol))
		return nil
	}

	// If xdg-mime fails, manually edit mimeapps.list
	homeDir, err := utils.GetHomeDir()
	if err != nil {
		return fmt.Errorf("could not get home directory: %w", err)
	}

	mimeappsPath := filepath.Join(homeDir, ".config", "mimeapps.list")

	// Create mimeapps.list if it doesn't exist
	if !utils.FileExists(mimeappsPath) {
		if err := os.MkdirAll(filepath.Dir(mimeappsPath), 0755); err != nil {
			return fmt.Errorf("could not create mimeapps directory: %w", err)
		}
		if err := os.WriteFile(mimeappsPath, []byte(""), 0644); err != nil {
			return fmt.Errorf("could not create mimeapps.list: %w", err)
		}
	}

	// Read existing content
	content, err := os.ReadFile(mimeappsPath)
	if err != nil {
		return fmt.Errorf("could not read mimeapps.list: %w", err)
	}

	// Remove any existing handler entries for this protocol
	lines := strings.Split(string(content), "\n")
	var newLines []string
	for _, line := range lines {
		if !strings.Contains(line, fmt.Sprintf("x-scheme-handler/%s", protocol)) {
			newLines = append(newLines, line)
		}
	}

	// Add the new handler
	newLines = append(newLines, fmt.Sprintf("x-scheme-handler/%s=vortex-nxm-handler.desktop", protocol))

	// Write back to file
	newContent := strings.Join(newLines, "\n")
	if err := os.WriteFile(mimeappsPath, []byte(newContent), 0644); err != nil {
		return fmt.Errorf("could not write mimeapps.list: %w", err)
	}

	// Update desktop database
	updateCmd := exec.Command("update-desktop-database", filepath.Join(homeDir, ".local", "share", "applications"))
	if err := updateCmd.Run(); err != nil {
		v.logger.Warning("Failed to update desktop database: " + err.Error())
	} else {
		v.logger.Info("Desktop database updated successfully")
	}

	v.logger.Info(fmt.Sprintf("Manual registration complete for %s", protocol))
	return nil
}

// findSteamRoot finds the Steam installation directory
func (v *VortexInstaller) findSteamRoot() (string, error) {
	// Common Steam installation paths
	possiblePaths := []string{
		os.Getenv("STEAM_ROOT"),
		"/home/" + os.Getenv("USER") + "/.local/share/Steam",
		"/home/" + os.Getenv("USER") + "/.steam/steam",
		"/usr/share/steam",
		"/opt/steam",
	}

	for _, path := range possiblePaths {
		if path != "" && utils.FileExists(path) {
			return path, nil
		}
	}

	return "", fmt.Errorf("Steam installation not found. Please ensure Steam is installed")
}
