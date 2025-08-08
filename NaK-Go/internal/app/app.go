package app

import (
	"embed"
	"fmt"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"

	"github.com/sulfurnitride/nak/internal/config"
	"github.com/sulfurnitride/nak/internal/dependencies"
	"github.com/sulfurnitride/nak/internal/limo"
	"github.com/sulfurnitride/nak/internal/logging"
	"github.com/sulfurnitride/nak/internal/mo2"
	"github.com/sulfurnitride/nak/internal/ui"
	"github.com/sulfurnitride/nak/internal/utils"
	"github.com/sulfurnitride/nak/internal/vortex"
)

type App struct {
	version     string
	date        string
	logger      *logging.Logger
	embeddedSTL embed.FS
}

func NewApp(version, date string) *App {
	return &App{
		version:     version,
		date:        date,
		logger:      logging.GetLogger(),
		embeddedSTL: embed.FS{},
	}
}

// SetEmbeddedSTL sets the embedded STL filesystem
func (a *App) SetEmbeddedSTL(stl embed.FS) {
	a.embeddedSTL = stl
}

func (a *App) Run() error {
	// Set up signal handling for graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigChan
		a.logger.Info("Received shutdown signal")
		logging.Close()
		os.Exit(0)
	}()

	// Print welcome message
	ui.PrintHeader(a.version, a.date)
	ui.PrintInfo("Welcome to NaK - The Linux Modding Helper!")
	ui.PrintInfo("This tool helps you set up and configure mod managers for Linux gaming.")

	// Check dependencies at startup
	a.checkDependencies()

	ui.Pause("Press Enter to start...")

	// Check for updates if enabled (silent)
	if config.Get("check_updates", "true") == "true" {
		a.checkForUpdates()
	}

	// Main program loop
	return a.mainMenu()
}

func (a *App) mainMenu() error {
	for {
		// Clear screen and show header at the start of each menu iteration
		ui.ClearScreenAndShowHeader(a.version, a.date)

		menu := ui.Menu{
			Title: "Main Menu",
			Items: []ui.MenuItem{
				{
					ID:          1,
					Title:       "Mod Managers",
					Description: "Set up MO2, Vortex, Limo, and manage NXM handlers",
					Action:      a.modManagersMenu,
				},
				{
					ID:          2,
					Title:       "Game-Specific Info",
					Description: "Information about supported games and launch options",
					Action:      a.gameSpecificMenu,
				},
			},
			ExitText: "Exit",
		}

		choice, err := ui.DisplayMenu(menu)
		if err != nil {
			return fmt.Errorf("menu error: %w", err)
		}

		if choice == len(menu.Items)+1 {
			a.logger.Info("User exited application")
			ui.PrintSuccess("Thank you for using NaK!")
			return nil
		}

		if choice > 0 && choice <= len(menu.Items) {
			if err := menu.Items[choice-1].Action(); err != nil {
				ui.PrintError("Error: " + err.Error())
				ui.Pause("Press Enter to continue...")
			}
		}
	}
}

// Mod Managers Menu
func (a *App) modManagersMenu() error {
	ui.ClearScreenAndShowHeader(a.version, a.date)

	menu := ui.Menu{
		Title: "Mod Managers",
		Items: []ui.MenuItem{
			{
				ID:          1,
				Title:       "Mod Organizer 2 Setup",
				Description: "Set up MO2 with Proton, NXM handler, and dependencies",
				Action:      a.mo2SetupMenu,
			},
			{
				ID:          2,
				Title:       "Vortex Setup",
				Description: "Set up Vortex with Proton, NXM handler, and dependencies",
				Action:      a.vortexSetupMenu,
			},
			{
				ID:          3,
				Title:       "Limo Setup",
				Description: "Set up game prefixes for Limo (Linux native mod manager)",
				Action:      a.limoSetupMenu,
			},
			{
				ID:          4,
				Title:       "Remove NXM Handlers",
				Description: "Remove previously configured NXM handlers",
				Action:      a.removeNxmHandlers,
			},
		},
		ExitText: "Back to Main Menu",
	}

	choice, err := ui.DisplayMenu(menu)
	if err != nil {
		return fmt.Errorf("menu error: %w", err)
	}

	switch choice {
	case 1:
		return a.mo2SetupMenu()
	case 2:
		return a.vortexSetupMenu()
	case 3:
		return a.limoSetupMenu()
	case 4:
		return a.removeNxmHandlers()
	case 5:
		return nil // Back to main menu
	}

	return nil
}

func (a *App) mo2SetupMenu() error {
	ui.ClearScreenAndShowHeader(a.version, a.date)

	menu := ui.Menu{
		Title: "Mod Organizer 2 Setup",
		Items: []ui.MenuItem{
			{
				ID:          1,
				Title:       "Download Mod Organizer 2",
				Description: "Download and install the latest version",
				Action:      a.downloadMO2,
			},
			{
				ID:          2,
				Title:       "Set Up Existing Installation",
				Description: "Configure an existing MO2 installation",
				Action:      a.setupExistingMO2,
			},
			{
				ID:          3,
				Title:       "Install Basic Dependencies",
				Description: "Install common Proton components for MO2",
				Action:      a.installBasicDependencies,
			},
			{
				ID:          4,
				Title:       "Configure NXM Handler",
				Description: "Set up Nexus Mod Manager link handling",
				Action:      a.configureNxmHandler,
			},
		},
		ExitText: "Back to Main Menu",
	}

	for {
		choice, err := ui.DisplayMenu(menu)
		if err != nil {
			return fmt.Errorf("menu error: %w", err)
		}

		if choice == len(menu.Items)+1 {
			return nil
		}

		if choice > 0 && choice <= len(menu.Items) {
			if err := menu.Items[choice-1].Action(); err != nil {
				ui.PrintError("Error: " + err.Error())
			}
			ui.Pause("Press Enter to continue...")
		}
	}
}

func (a *App) vortexSetupMenu() error {
	ui.ClearScreenAndShowHeader(a.version, a.date)

	menu := ui.Menu{
		Title: "Vortex Setup",
		Items: []ui.MenuItem{
			{
				ID:          1,
				Title:       "Download Vortex",
				Description: "Download and install the latest version",
				Action:      a.downloadVortex,
			},
			{
				ID:          2,
				Title:       "Set Up Existing Installation",
				Description: "Configure an existing Vortex installation",
				Action:      a.setupExistingVortex,
			},
			{
				ID:          3,
				Title:       "Install Basic Dependencies",
				Description: "Install common Proton components for Vortex",
				Action:      a.installBasicDependencies,
			},
			{
				ID:          4,
				Title:       "Configure NXM Handler",
				Description: "Set up Nexus Mod Manager link handling",
				Action:      a.configureVortexNxmHandler,
			},
		},
		ExitText: "Back to Main Menu",
	}

	for {
		choice, err := ui.DisplayMenu(menu)
		if err != nil {
			return fmt.Errorf("menu error: %w", err)
		}

		if choice == len(menu.Items)+1 {
			return nil
		}

		if choice > 0 && choice <= len(menu.Items) {
			if err := menu.Items[choice-1].Action(); err != nil {
				ui.PrintError("Error: " + err.Error())
			}
			ui.Pause("Press Enter to continue...")
		}
	}
}

func (a *App) limoSetupMenu() error {
	ui.ClearScreenAndShowHeader(a.version, a.date)

	ui.PrintSection("Limo Setup (Linux Native Mod Manager)")
	ui.PrintInfo("Limo is a Linux-native mod manager that uses game prefixes directly.")
	ui.PrintInfo("This tool will help you prepare your game prefixes with the necessary dependencies.")

	menu := ui.Menu{
		Title: "Limo Setup",
		Items: []ui.MenuItem{
			{
				ID:          1,
				Title:       "Configure Games for Limo",
				Description: "Install dependencies for game prefixes",
				Action:      a.configureGamesForLimo,
			},
		},
		ExitText: "Back to Main Menu",
	}

	for {
		choice, err := ui.DisplayMenu(menu)
		if err != nil {
			return fmt.Errorf("menu error: %w", err)
		}

		if choice == len(menu.Items)+1 {
			return nil
		}

		if choice > 0 && choice <= len(menu.Items) {
			if err := menu.Items[choice-1].Action(); err != nil {
				ui.PrintError("Error: " + err.Error())
			}
			ui.Pause("Press Enter to continue...")
		}
	}
}

func (a *App) gameSpecificMenu() error {
	ui.PrintSection("Game-Specific Launch Options And Game Dependencies")

	// Get Steam root
	steamRoot, err := utils.GetSteamRoot()
	if err != nil {
		ui.PrintWarning("Could not find Steam installation: " + err.Error())
		return nil
	}

	// Check for specific games
	fnvCompatdata, _ := utils.FindGameCompatData("22380", steamRoot)
	enderalCompatdata, _ := utils.FindGameCompatData("976620", steamRoot)

	// Create menu items for available games
	var menuItems []ui.MenuItem
	itemID := 1

	// FNV option
	if fnvCompatdata != "" {
		menuItems = append(menuItems, ui.MenuItem{
			ID:          itemID,
			Title:       "Fallout New Vegas",
			Description: "Launch options and dependency setup for FNV modding",
			Action:      a.showFNVInfo,
		})
		itemID++
	}

	// Enderal option
	if enderalCompatdata != "" {
		menuItems = append(menuItems, ui.MenuItem{
			ID:          itemID,
			Title:       "Enderal",
			Description: "Launch options and dependency setup for Enderal modding",
			Action:      a.showEnderalInfo,
		})
		itemID++
	}

	// If no games found
	if len(menuItems) == 0 {
		ui.PrintWarning("No supported games found. Make sure you have installed and run at least one of:")
		ui.PrintInfo("- Fallout New Vegas (AppID: 22380)")
		ui.PrintInfo("- Enderal (AppID: 976620)")
		ui.Pause("Press Enter to continue...")
		return nil
	}

	// Display menu
	menu := ui.Menu{
		Title:    "Game-Specific Information",
		Items:    menuItems,
		ExitText: "Back to Main Menu",
	}

	choice, err := ui.DisplayMenu(menu)
	if err != nil {
		return fmt.Errorf("menu error: %w", err)
	}

	if choice == len(menuItems)+1 {
		return nil // Back to main menu
	}

	if choice > 0 && choice <= len(menuItems) {
		return menuItems[choice-1].Action()
	}

	return nil
}

// showFNVInfo shows Fallout New Vegas specific information
func (a *App) showFNVInfo() error {
	ui.PrintSection("Fallout New Vegas - Launch Options & Dependencies")

	// Get Steam root and compatdata path
	steamRoot, err := utils.GetSteamRoot()
	if err != nil {
		ui.PrintError("Could not find Steam installation: " + err.Error())
		return nil
	}

	fnvCompatdata, err := utils.FindGameCompatData("22380", steamRoot)
	if err != nil {
		ui.PrintError("Could not find FNV compatdata: " + err.Error())
		return nil
	}

	ui.PrintInfo("For Fallout New Vegas modlists, use this launch option:")
	ui.PrintCommand(fmt.Sprintf("STEAM_COMPAT_DATA_PATH=\"%s\" %%command%%", fnvCompatdata))

	ui.PrintInfo("")
	ui.PrintInfo("Would you like to set up Fallout New Vegas dependencies? (Choose yes if modding)")
	confirmed, err := ui.ConfirmAction("Set up FNV dependencies?")
	if err != nil {
		return err
	}
	if confirmed {
		return a.setupFNVDependencies()
	}

	return nil
}

// showEnderalInfo shows Enderal specific information
func (a *App) showEnderalInfo() error {
	ui.PrintSection("Enderal - Launch Options & Dependencies")

	// Get Steam root and compatdata path
	steamRoot, err := utils.GetSteamRoot()
	if err != nil {
		ui.PrintError("Could not find Steam installation: " + err.Error())
		return nil
	}

	enderalCompatdata, err := utils.FindGameCompatData("976620", steamRoot)
	if err != nil {
		ui.PrintError("Could not find Enderal compatdata: " + err.Error())
		return nil
	}

	ui.PrintInfo("For Enderal modlists, use this launch option:")
	ui.PrintCommand(fmt.Sprintf("STEAM_COMPAT_DATA_PATH=\"%s\" %%command%%", enderalCompatdata))

	ui.PrintInfo("")
	ui.PrintInfo("Would you like to set up Enderal dependencies? (Choose yes if modding)")
	confirmed, err := ui.ConfirmAction("Set up Enderal dependencies?")
	if err != nil {
		return err
	}
	if confirmed {
		return a.setupEnderalDependencies()
	}

	return nil
}

// setupFNVDependencies sets up Fallout New Vegas dependencies
func (a *App) setupFNVDependencies() error {
	ui.PrintSection("Setting up Fallout New Vegas Dependencies")
	ui.PrintInfo("Installing FNV-specific dependencies via protontricks...")

	// Get Steam root and FNV compatdata path
	steamRoot, err := utils.GetSteamRoot()
	if err != nil {
		ui.PrintError("Could not find Steam installation: " + err.Error())
		return err
	}

	fnvCompatdata, err := utils.FindGameCompatData("22380", steamRoot)
	if err != nil {
		ui.PrintError("Could not find FNV compatdata: " + err.Error())
		return err
	}

	// Load wine registry settings first
	ui.PrintInfo("Loading wine registry settings...")
	if err := utils.LoadWineRegistrySettings(fnvCompatdata); err != nil {
		ui.PrintWarning("Failed to load wine registry settings: " + err.Error())
		ui.PrintInfo("Continuing with dependency installation...")
	}

	// Get protontricks command
	protontricksCmd, err := utils.GetProtontricksCommand()
	if err != nil {
		ui.PrintError("Could not find protontricks: " + err.Error())
		return err
	}

	// Install FNV dependencies (ONLY the specific list from bash script)
	dependencies := []string{"fontsmooth=rgb", "xact", "xact_x64", "d3dx9_43", "d3dx9", "vcrun2022"}

	ui.PrintInfo("Installing FNV-specific dependencies:")
	for _, dep := range dependencies {
		ui.PrintInfo(fmt.Sprintf("- %s", dep))
	}

	for _, dep := range dependencies {
		ui.PrintInfo(fmt.Sprintf("Installing %s...", dep))
		cmd := exec.Command(protontricksCmd, "22380", "-q", dep)
		if err := cmd.Run(); err != nil {
			ui.PrintWarning(fmt.Sprintf("Failed to install %s: %v", dep, err))
		} else {
			ui.PrintSuccess(fmt.Sprintf("Successfully installed %s", dep))
		}
	}

	ui.PrintSuccess("Fallout New Vegas dependencies setup complete!")

	return nil
}

// setupEnderalDependencies sets up Enderal dependencies
func (a *App) setupEnderalDependencies() error {
	ui.PrintSection("Setting up Enderal Dependencies")
	ui.PrintInfo("Installing Enderal-specific dependencies via protontricks...")

	// Get protontricks command
	protontricksCmd, err := utils.GetProtontricksCommand()
	if err != nil {
		ui.PrintError("Could not find protontricks: " + err.Error())
		return err
	}

	// Install Enderal dependencies
	dependencies := []string{"vcrun2019", "d3dx9", "dotnet40", "xact"}

	for _, dep := range dependencies {
		ui.PrintInfo(fmt.Sprintf("Installing %s...", dep))
		cmd := exec.Command(protontricksCmd, "976620", dep)
		if err := cmd.Run(); err != nil {
			ui.PrintWarning(fmt.Sprintf("Failed to install %s: %v", dep, err))
		} else {
			ui.PrintSuccess(fmt.Sprintf("Successfully installed %s", dep))
		}
	}

	ui.PrintSuccess("Enderal dependencies setup complete!")
	return nil
}

func (a *App) removeNxmHandlers() error {
	ui.PrintSection("Remove NXM Handlers")
	ui.PrintInfo("This will remove previously configured NXM handlers.")

	confirmed, err := ui.ConfirmAction("Are you sure you want to remove NXM handlers?")
	if err != nil {
		return err
	}

	if confirmed {
		ui.PrintInfo("Removing NXM handlers...")

		// Remove desktop file
		desktopFile := filepath.Join(utils.GetHomeDirSafe(), ".local", "share", "applications", "nxm-handler.desktop")
		if utils.FileExists(desktopFile) {
			if err := os.Remove(desktopFile); err != nil {
				ui.PrintWarning(fmt.Sprintf("Failed to remove desktop file: %v", err))
			} else {
				ui.PrintSuccess("Removed NXM handler desktop file")
			}
		}

		// Remove MIME type registration
		ui.PrintInfo("Removing MIME type registration...")
		cmd := exec.Command("xdg-mime", "uninstall", "application/x-nxm")
		if err := cmd.Run(); err != nil {
			ui.PrintWarning("Failed to remove MIME type registration")
		} else {
			ui.PrintSuccess("Removed MIME type registration")
		}

		// Update desktop database
		ui.PrintInfo("Updating desktop database...")
		cmd = exec.Command("update-desktop-database", filepath.Join(utils.GetHomeDirSafe(), ".local", "share", "applications"))
		if err := cmd.Run(); err != nil {
			ui.PrintWarning("Failed to update desktop database")
		} else {
			ui.PrintSuccess("Updated desktop database")
		}

		ui.PrintSuccess("NXM handlers removed successfully!")
	} else {
		ui.PrintInfo("Operation cancelled.")
	}

	return nil
}

// MO2 Setup Actions
func (a *App) downloadMO2() error {
	installer := mo2.NewMO2Installer()
	return installer.DownloadMO2()
}

func (a *App) setupExistingMO2() error {
	ui.PrintSection("Set Up Existing MO2 Installation")
	ui.PrintInfo("This will add MO2 to Steam as a non-Steam game and restart Steam.")

	// Get the MO2 installation path
	mo2Path, err := ui.GetInputWithTabCompletion("Enter the path to your existing MO2 installation", "")
	if err != nil {
		return err
	}

	if mo2Path == "" {
		ui.PrintWarning("No path provided.")
		return nil
	}

	// Validate the path
	if !utils.DirectoryExists(mo2Path) {
		ui.PrintError("The specified directory does not exist.")
		return nil
	}

	// Look for ModOrganizer.exe in the directory
	mo2Exe := filepath.Join(mo2Path, "ModOrganizer.exe")
	if !utils.FileExists(mo2Exe) {
		ui.PrintError("ModOrganizer.exe not found in the specified directory.")
		ui.PrintInfo("Please make sure you've selected the correct MO2 installation directory.")
		return nil
	}

	ui.PrintSuccess("Found ModOrganizer.exe in the specified directory.")

	// Ask for custom name
	mo2Name, err := ui.GetInput("What name would you like to use for Mod Organizer 2 in Steam?", "Mod Organizer 2")
	if err != nil {
		return err
	}

	if mo2Name == "" {
		mo2Name = "Mod Organizer 2"
	}

	// Add to Steam using steamtinkerlaunch
	ui.PrintInfo("Adding MO2 to Steam using steamtinkerlaunch...")

	// Build the steamtinkerlaunch command
	args := []string{
		"ansg", // Add non-Steam game
		fmt.Sprintf("--appname=%s", mo2Name),
		fmt.Sprintf("--exepath=%s", mo2Exe),
		fmt.Sprintf("--startdir=%s", filepath.Dir(mo2Exe)),
		"--compatibilitytool=default",
		"--launchoptions=",
	}

	ui.PrintInfo("Running steamtinkerlaunch command...")

	// Run steamtinkerlaunch (system or embedded)
	output, err := utils.RunEmbeddedSTLWithOutput(args...)

	if err != nil {
		a.logger.Error("Failed to add MO2 to Steam: " + err.Error())
		a.logger.Error("steamtinkerlaunch output: " + string(output))
		ui.PrintWarning("Failed to add MO2 to Steam: " + err.Error())
		ui.PrintInfo("steamtinkerlaunch output: " + string(output))
		return fmt.Errorf("failed to add MO2 to Steam: %w", err)
	}

	ui.PrintSuccess("Successfully added MO2 to Steam using steamtinkerlaunch")
	ui.PrintInfo("Output: " + string(output))

	ui.PrintSuccess("MO2 has been added to Steam successfully!")
	ui.PrintInfo("You can now launch MO2 from your Steam library.")

	// Ask about restarting Steam
	restartConfirmed, err := ui.ConfirmAction("Do you want to restart Steam to ensure proper integration?")
	if err != nil {
		return err
	}

	if restartConfirmed {
		if err := utils.RestartSteam(); err != nil {
			a.logger.Warning("Failed to restart Steam: " + err.Error())
			ui.PrintWarning("Failed to restart Steam: " + err.Error())
			ui.PrintInfo("Please restart Steam manually.")
		}
	}

	// Ask about setting up dependencies
	confirmed, err := ui.ConfirmAction("Do you want to setup dependencies for " + mo2Name + "?")
	if err != nil {
		return err
	}

	if confirmed {
		ui.ClearScreen()
		// Provide instructions to run the mod manager once
		ui.PrintInfo("To setup dependencies, you need to:")
		ui.PrintInfo("1. Launch " + mo2Name + " from Steam")
		ui.PrintInfo("2. Let it run for a moment (it may show errors, that's normal)")
		ui.PrintInfo("3. Close " + mo2Name + " completely")
		ui.PrintInfo("4. Come back here and press Enter when done")

		// Wait for user confirmation
		_, err = ui.GetInput("Press Enter when you've launched and closed "+mo2Name+"...", "")
		if err != nil {
			return err
		}

		// Use the existing dependency installer system
		dependencyInstaller := dependencies.NewDependencyInstaller()
		if err := dependencyInstaller.InstallBasicDependencies(); err != nil {
			a.logger.Warning("Failed to setup dependencies: " + err.Error())
			ui.PrintWarning("Failed to setup dependencies: " + err.Error())
			ui.PrintInfo("You can setup dependencies manually later using protontricks.")
		}
	}

	return nil
}

func (a *App) installBasicDependencies() error {
	installer := dependencies.NewDependencyInstaller()
	return installer.InstallBasicDependencies()
}

func (a *App) configureNxmHandler() error {
	ui.PrintSection("Configure NXM Handler")

	ui.PrintInfo("This will set up NXM link handling for Mod Organizer 2.")
	ui.PrintInfo("NXM links will open directly in MO2 when clicked in your browser.")

	confirmed, err := ui.ConfirmAction("Continue with NXM handler configuration?")
	if err != nil || !confirmed {
		return nil
	}

	// Get non-Steam games and select one (matching shell script behavior)
	ui.PrintSection("Fetching Non-Steam Games")
	ui.PrintInfo("Scanning for non-Steam games...")

	games, err := utils.GetNonSteamGames()
	if err != nil {
		ui.PrintError("Could not get non-Steam games: " + err.Error())
		return nil
	}

	// Auto-select if only one game found (matching shell script behavior)
	if len(games) == 1 {
		selectedGame := games[0]
		a.logger.Info(fmt.Sprintf("Auto-selected only game: %s (AppID: %s)", selectedGame.Name, selectedGame.AppID))
		return a.setupNxmHandler(selectedGame)
	}

	// Create menu items for games (matching shell script display format)
	menuItems := make([]ui.MenuItem, len(games))
	for i, game := range games {
		menuItems[i] = ui.MenuItem{
			ID:          i + 1,
			Title:       fmt.Sprintf("%s (AppID: %s)", game.Name, game.AppID),
			Description: "Non-Steam game",
		}
	}

	menu := ui.Menu{
		Title:    "Available Non-Steam Games",
		Items:    menuItems,
		ExitText: "Cancel",
	}

	choice, err := ui.DisplayMenu(menu)
	if err != nil {
		return fmt.Errorf("menu error: %w", err)
	}

	if choice == len(games)+1 {
		return nil // User cancelled
	}

	if choice > 0 && choice <= len(games) {
		selectedGame := games[choice-1]
		a.logger.Info(fmt.Sprintf("Selected game: %s (AppID: %s)", selectedGame.Name, selectedGame.AppID))
		return a.setupNxmHandler(selectedGame)
	}

	return nil
}

func (a *App) setupNxmHandler(game utils.Game) error {
	a.logger.Info(fmt.Sprintf("Setting up NXM handler for %s (AppID: %s)", game.Name, game.AppID))

	ui.PrintSection("NXM Link Handler Setup")

	// Check for Steam and get Steam root
	steamRoot, err := utils.GetSteamRoot()
	if err != nil {
		ui.PrintWarning("Could not find Steam installation: " + err.Error())
		ui.PrintInfo("Please ensure Steam is installed and running.")
		return nil
	}

	// Find Proton path (matching shell script logic)
	protonPath, err := a.findProtonPath(steamRoot, game.AppID)
	if err != nil {
		ui.PrintWarning("Could not automatically detect Proton version.")
		ui.PrintInfo("Please select a Proton version manually:")
		ui.PrintInfo("Note: Only Steam compatibility tools are supported. AUR packages are not detected.")

		// Let user select from available Proton versions
		protonPath, err = a.selectProtonVersion(steamRoot)
		if err != nil {
			ui.PrintError("Could not find any Proton installation. Make sure Proton is installed in Steam.")
			return nil
		}
	} else {
		// Even if detection worked, let user choose if they want to use a different version
		ui.PrintInfo("Detected Proton version from game compatibility data.")
		ui.PrintInfo("You can choose to use a different Proton version if needed.")
		ui.PrintInfo("Note: Only Steam compatibility tools are supported. AUR packages are not detected.")

		confirmed, err := ui.ConfirmAction("Use detected Proton version? (N to choose different)")
		if err != nil || !confirmed {
			// Let user select from available Proton versions
			protonPath, err = a.selectProtonVersion(steamRoot)
			if err != nil {
				ui.PrintError("Could not find any Proton installation. Make sure Proton is installed in Steam.")
				return nil
			}
		}
	}

	// Ask for nxmhandler.exe path (matching shell script behavior)
	ui.PrintInfo("Enter FULL path to nxmhandler.exe (or 'b' to go back)")
	nxmHandlerPath, err := ui.GetInputWithTabCompletion("Path to nxmhandler.exe: ", "")
	if err != nil {
		return err
	}

	// Check if user wants to go back
	if strings.ToLower(nxmHandlerPath) == "b" {
		a.logger.Info("User cancelled NXM handler setup")
		return nil
	}

	// Check if file exists
	if !utils.FileExists(nxmHandlerPath) {
		ui.PrintError("File not found! Try again or enter 'b' to go back.")
		return fmt.Errorf("invalid path: %s", nxmHandlerPath)
	}

	a.logger.Info("Selected nxmhandler.exe: " + nxmHandlerPath)

	// Create desktop file (matching shell script logic)
	homeDir, err := utils.GetHomeDir()
	if err != nil {
		return fmt.Errorf("could not get home directory: %w", err)
	}

	steamCompatDataPath := filepath.Join(steamRoot, "steamapps", "compatdata", game.AppID)
	desktopFile := filepath.Join(homeDir, ".local", "share", "applications", "modorganizer2-nxm-handler.desktop")

	// Create applications directory if it doesn't exist
	applicationsDir := filepath.Dir(desktopFile)
	if err := utils.CreateDirectory(applicationsDir); err != nil {
		return fmt.Errorf("could not create applications directory: %w", err)
	}

	// Create desktop file content (matching shell script)
	// Check if this is a Wine-based Proton (like Proton Cachy)
	var execCommand string
	if strings.Contains(protonPath, "bin/wine") {
		// For Wine-based Proton, use wine directly
		execCommand = fmt.Sprintf(`bash -c 'env "STEAM_COMPAT_CLIENT_INSTALL_PATH=%s" "STEAM_COMPAT_DATA_PATH=%s" "%s" "%s" "%%u"'`,
			steamRoot, steamCompatDataPath, protonPath, nxmHandlerPath)
	} else {
		// For standard Proton, use the proton script
		execCommand = fmt.Sprintf(`bash -c 'env "STEAM_COMPAT_CLIENT_INSTALL_PATH=%s" "STEAM_COMPAT_DATA_PATH=%s" "%s" run "%s" "%%u"'`,
			steamRoot, steamCompatDataPath, protonPath, nxmHandlerPath)
	}

	desktopContent := fmt.Sprintf(`[Desktop Entry]
Type=Application
Categories=Game;
Exec=%s
Name=Mod Organizer 2 NXM Handler
MimeType=x-scheme-handler/nxm;
NoDisplay=true
`, execCommand)

	// Write desktop file
	if err := os.WriteFile(desktopFile, []byte(desktopContent), 0755); err != nil {
		return fmt.Errorf("could not create desktop file: %w", err)
	}

	// Register MIME handler
	if err := a.registerMimeHandler(); err != nil {
		ui.PrintWarning("Could not register MIME handler: " + err.Error())
	}

	ui.PrintSuccess("NXM Handler setup complete!")
	a.logger.Info("NXM Handler setup complete")

	return nil
}

func (a *App) findProtonPath(steamRoot string, gameAppID string) (string, error) {
	// First, try to detect the Proton version from the game's compatibility data
	if gameAppID != "" {
		detectedVersion, err := utils.DetectProtonVersionFromGame(gameAppID)
		if err == nil && detectedVersion != "" {
			// Try to find the detected Proton version using enhanced detection
			protonPath, err := utils.FindProtonInstallation(detectedVersion)
			if err == nil {
				a.logger.Info(fmt.Sprintf("Using detected Proton version: %s", detectedVersion))
				return protonPath, nil
			}
		}
	}

	// Fallback: Get all available Proton versions and use the first one
	availableVersions, err := utils.GetAllAvailableProtonVersions()
	if err == nil && len(availableVersions) > 0 {
		// Use the first available version (usually the most recent)
		protonPath, err := utils.FindProtonInstallation(availableVersions[0])
		if err == nil {
			a.logger.Info(fmt.Sprintf("Using fallback Proton version: %s", availableVersions[0]))
			return protonPath, nil
		}
	}

	return "", fmt.Errorf("Proton not found in any location")
}

func (a *App) selectProtonVersion(steamRoot string) (string, error) {
	// Get all available Proton versions using enhanced detection
	availableVersions, err := utils.GetAllAvailableProtonVersions()
	if err != nil {
		return "", fmt.Errorf("failed to get Proton versions: %w", err)
	}

	if len(availableVersions) == 0 {
		return "", fmt.Errorf("no Proton versions found")
	}

	// If only one version is available, use it automatically
	if len(availableVersions) == 1 {
		protonPath, err := utils.FindProtonInstallation(availableVersions[0])
		if err != nil {
			return "", fmt.Errorf("failed to find Proton installation: %w", err)
		}
		a.logger.Info(fmt.Sprintf("Auto-selected only available Proton version: %s", availableVersions[0]))
		return protonPath, nil
	}

	// Create menu for multiple versions
	menuItems := make([]ui.MenuItem, len(availableVersions))
	for i, version := range availableVersions {
		menuItems[i] = ui.MenuItem{
			ID:          i + 1,
			Title:       version,
			Description: "Proton version",
		}
	}

	menu := ui.Menu{
		Title:    "Select Proton Version",
		Items:    menuItems,
		ExitText: "Cancel",
	}

	choice, err := ui.DisplayMenu(menu)
	if err != nil {
		return "", fmt.Errorf("menu error: %w", err)
	}

	if choice == len(availableVersions)+1 {
		return "", fmt.Errorf("user cancelled")
	}

	if choice > 0 && choice <= len(availableVersions) {
		selectedVersion := availableVersions[choice-1]
		protonPath, err := utils.FindProtonInstallation(selectedVersion)
		if err != nil {
			return "", fmt.Errorf("failed to find Proton installation: %w", err)
		}
		a.logger.Info(fmt.Sprintf("User selected Proton version: %s", selectedVersion))
		return protonPath, nil
	}

	return "", fmt.Errorf("invalid selection")
}

func (a *App) registerMimeHandler() error {
	// Register nxm:// protocol handler
	ui.PrintInfo("Registering nxm:// handler...")

	// Try xdg-mime first
	cmd := exec.Command("xdg-mime", "default", "modorganizer2-nxm-handler.desktop", "x-scheme-handler/nxm")
	if err := cmd.Run(); err == nil {
		ui.PrintSuccess("Success (via xdg-mime)")
		a.logger.Info("MIME handler registered via xdg-mime")
		return nil
	}

	// If xdg-mime fails, manually edit mimeapps.list
	ui.PrintInfo("xdg-mime failed, trying manual registration...")

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

	// Remove any existing nxm handler entries
	lines := strings.Split(string(content), "\n")
	var newLines []string
	for _, line := range lines {
		if !strings.Contains(line, "x-scheme-handler/nxm") {
			newLines = append(newLines, line)
		}
	}

	// Add the new handler
	newLines = append(newLines, "x-scheme-handler/nxm=modorganizer2-nxm-handler.desktop")

	// Write back to file
	newContent := strings.Join(newLines, "\n")
	if err := os.WriteFile(mimeappsPath, []byte(newContent), 0644); err != nil {
		return fmt.Errorf("could not write mimeapps.list: %w", err)
	}

	// Update desktop database
	updateCmd := exec.Command("update-desktop-database", filepath.Join(homeDir, ".local", "share", "applications"))
	if err := updateCmd.Run(); err != nil {
		a.logger.Warning("Failed to update desktop database: " + err.Error())
		ui.PrintWarning("Failed to update desktop database: " + err.Error())
	} else {
		a.logger.Info("Desktop database updated successfully")
	}

	ui.PrintSuccess("Manual registration complete!")
	a.logger.Info("MIME handler registered manually")
	return nil
}

func (a *App) configureGamesForLimo() error {
	configurator := limo.NewLimoConfigurator()
	return configurator.ConfigureGamesForLimo()
}

func (a *App) checkForUpdates() {
	a.logger.Info("Checking for updates")

	// For now, just log that update checking is enabled
	// In a real implementation, this would check against a remote repository
	// or GitHub releases for new versions
	a.logger.Info("Update checking enabled (no updates available)")
}

func (a *App) checkDependencies() {
	ui.PrintInfo("Checking system dependencies...")

	// Check for protontricks
	if !utils.CommandExists("protontricks") {
		ui.PrintWarning("Protontricks is not installed.")
		ui.PrintInfo("Install it with: sudo apt install protontricks")
	} else {
		ui.PrintSuccess("✓ Protontricks: Available")
	}

	// Check for Steam
	_, err := utils.GetSteamRoot()
	if err != nil {
		ui.PrintWarning("Steam installation not found.")
		ui.PrintInfo("Please install Steam natively (not via Flatpak)")
	} else {
		ui.PrintSuccess("✓ Steam: Native installation detected")
	}

	// Check for flatpak Steam (not supported)
	if utils.CommandExists("flatpak") {
		cmd := exec.Command("flatpak", "list", "--app", "--columns=application")
		output, err := cmd.Output()
		if err == nil && strings.Contains(string(output), "com.valvesoftware.Steam") {
			ui.PrintWarning("⚠ Flatpak Steam detected - not supported")
			ui.PrintInfo("Please install Steam natively for best compatibility")
		}
	}

	ui.PrintInfo("Dependency check complete.")
}

func (a *App) logSystemInfo() {
	info := utils.GetSystemInfo()
	a.logger.Info("System information:")
	for key, value := range info {
		a.logger.Info(fmt.Sprintf("  %s: %s", key, value))
	}
}

// Vortex Setup Actions
func (a *App) downloadVortex() error {
	installer := vortex.NewVortexInstaller()
	return installer.DownloadVortex()
}

func (a *App) setupExistingVortex() error {
	installer := vortex.NewVortexInstaller()
	return installer.SetupExistingVortex()
}

func (a *App) configureVortexNxmHandler() error {
	installer := vortex.NewVortexInstaller()
	return installer.SetupVortexNxmHandler()
}
