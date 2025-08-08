package limo

import (
	"fmt"
	"os/exec"
	"strings"

	"github.com/sulfurnitride/nak/internal/dependencies"
	"github.com/sulfurnitride/nak/internal/logging"
	"github.com/sulfurnitride/nak/internal/ui"
	"github.com/sulfurnitride/nak/internal/utils"
)

type LimoConfigurator struct {
	logger *logging.Logger
}

func NewLimoConfigurator() *LimoConfigurator {
	return &LimoConfigurator{
		logger: logging.GetLogger(),
	}
}

func (l *LimoConfigurator) ConfigureGamesForLimo() error {
	l.logger.Info("Starting Limo game configuration")
	ui.PrintSection("Configure Games for Limo")

	ui.PrintInfo("Limo is a Linux-native mod manager that uses game prefixes directly.")
	ui.PrintInfo("This tool will help you prepare your game prefixes with the necessary dependencies.")

	// Check dependencies
	if err := utils.CheckDependencies(); err != nil {
		return err
	}

	// Get protontricks command
	protontricksCmd, err := utils.GetProtontricksCommand()
	if err != nil {
		return err
	}

	ui.PrintInfo("Scanning for Steam games...")
	games, err := utils.GetSteamGames()
	if err != nil {
		return fmt.Errorf("could not get Steam games: %w", err)
	}

	if len(games) == 0 {
		ui.PrintWarning("No Steam games found.")
		return nil
	}

	ui.PrintSuccess(fmt.Sprintf("Found %d Steam games", len(games)))

	// All Steam games found by protontricks can work with Limo
	ui.PrintInfo(fmt.Sprintf("Found %d Steam games that can be configured for Limo", len(games)))

	// Auto-select if only one game found
	if len(games) == 1 {
		selectedGame := games[0]
		l.logger.Info(fmt.Sprintf("Auto-selected only game: %s (AppID: %s)", selectedGame.Name, selectedGame.AppID))
		return l.configureGameForLimo(selectedGame, protontricksCmd)
	}

	// Create menu for multiple games
	menuItems := make([]ui.MenuItem, len(games))
	for i, game := range games {
		menuItems[i] = ui.MenuItem{
			ID:          i + 1,
			Title:       fmt.Sprintf("%s (AppID: %s)", game.Name, game.AppID),
			Description: "Steam game with Proton support",
		}
	}

	menu := ui.Menu{
		Title:    "Select Game for Limo Configuration",
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
		l.logger.Info(fmt.Sprintf("Selected game: %s (AppID: %s)", selectedGame.Name, selectedGame.AppID))
		return l.configureGameForLimo(selectedGame, protontricksCmd)
	}

	return nil
}

func (l *LimoConfigurator) configureGameForLimo(game utils.Game, protontricksCmd string) error {
	l.logger.Info(fmt.Sprintf("Configuring %s (AppID: %s) for Limo", game.Name, game.AppID))

	ui.PrintSection("Configure Game for Limo")
	ui.PrintInfo(fmt.Sprintf("Configuring %s for Limo compatibility", game.Name))
	ui.PrintInfo("This will install necessary dependencies in the game's Proton prefix.")

	// Use the shared dependency installer
	installer := dependencies.NewDependencyInstaller()

	// Get components based on game AppID
	components := installer.GetGameComponents(game.AppID)

	ui.PrintInfo("Components to install:")
	for _, comp := range components {
		ui.PrintInfo("- " + comp)
	}

	confirmed, err := ui.ConfirmAction("Continue with installation? This may take several minutes.")
	if err != nil || !confirmed {
		return nil
	}

	ui.PrintInfo("Installing components... This may take several minutes.")

	// Build the protontricks command
	args := []string{"--no-bwrap", game.AppID, "-q"}
	args = append(args, components...)

	// Split the protontricks command if it's a flatpak command
	var cmd *exec.Cmd
	if strings.HasPrefix(protontricksCmd, "flatpak run") {
		parts := strings.Fields(protontricksCmd)
		cmd = exec.Command(parts[0], append(parts[1:], args...)...)
	} else {
		cmd = exec.Command(protontricksCmd, args...)
	}

	// Set up output capture
	var stdout, stderr strings.Builder
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	// Run the command
	ui.PrintInfo("Running installation...")
	err = cmd.Run()

	if err != nil {
		ui.PrintError("Installation failed: " + err.Error())
		if stderr.Len() > 0 {
			ui.PrintError("Error output: " + stderr.String())
		}
		return fmt.Errorf("protontricks installation failed: %w", err)
	}

	ui.PrintSuccess("Dependencies installed successfully!")
	ui.PrintInfo("The following components were installed:")
	for _, comp := range components {
		ui.PrintInfo("- " + comp)
	}

	// Load wine registry settings for better compatibility
	ui.PrintInfo("Loading wine registry settings...")
	steamRoot, err := utils.GetSteamRoot()
	if err == nil {
		compatDataPath, err := utils.FindGameCompatData(game.AppID, steamRoot)
		if err == nil {
			if err := utils.LoadWineRegistrySettings(compatDataPath); err != nil {
				ui.PrintWarning("Failed to load wine registry settings: " + err.Error())
			} else {
				ui.PrintSuccess("Wine registry settings loaded successfully!")
			}
		}
	}

	// Ask if user wants to install Synthesis certificate
	installSynthesis, err := ui.ConfirmAction("Install Synthesis certificate? (Required for Synthesis mod patcher)")
	if err != nil {
		ui.PrintWarning("Failed to get user input, skipping Synthesis certificate")
		installSynthesis = false
	}

	// Install synthesis fixes only if user requested it
	if installSynthesis {
		ui.PrintInfo("Installing synthesis fixes...")
		if err := utils.InstallSynthesisFixes(game.AppID, installSynthesis); err != nil {
			ui.PrintWarning("Failed to install synthesis fixes: " + err.Error())
		} else {
			ui.PrintSuccess("Synthesis fixes installed successfully!")
		}
	} else {
		ui.PrintInfo("Skipping Synthesis fixes (user declined)")
	}

	// Provide Limo-specific instructions
	l.printLimoInstructions(game)

	return nil
}

func (l *LimoConfigurator) printLimoInstructions(game utils.Game) {
	ui.PrintSection("Limo Configuration Complete")
	ui.PrintSuccess(fmt.Sprintf("%s has been configured for Limo!", game.Name))

	ui.PrintInfo("Next steps to use Limo:")
	ui.PrintInfo("1. Install Limo from: https://github.com/linuxgaming/limo")
	ui.PrintInfo("2. Launch Limo and select your game")
	ui.PrintInfo("3. Limo will automatically detect the configured prefix")
	ui.PrintInfo("4. You can now install and manage mods directly in Linux")

	ui.PrintInfo("")
	ui.PrintInfo("Limo advantages:")
	ui.PrintInfo("- Native Linux mod manager")
	ui.PrintInfo("- No need for Wine/Proton for the mod manager")
	ui.PrintInfo("- Better performance and integration")
	ui.PrintInfo("- Direct access to Linux file systems")

	ui.PrintInfo("")
	ui.PrintInfo("Note: Some mods may still require Windows-specific tools.")
	ui.PrintInfo("For those cases, you can still use MO2 or Vortex alongside Limo.")
}
