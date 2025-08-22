package dependencies

import (
	"bytes"
	"fmt"
	"os/exec"
	"strings"

	"github.com/sulfurnitride/nak/internal/logging"
	"github.com/sulfurnitride/nak/internal/ui"
	"github.com/sulfurnitride/nak/internal/utils"
)

type DependencyInstaller struct {
	logger *logging.Logger
}

func NewDependencyInstaller() *DependencyInstaller {
	return &DependencyInstaller{
		logger: logging.GetLogger(),
	}
}

// InstallBasicDependencies installs common Proton components for any mod manager
func (d *DependencyInstaller) InstallBasicDependencies() error {
	ui.ClearScreen()
	ui.PrintSection("Install Basic Dependencies")

	ui.PrintInfo("Checking for required dependencies...")

	// Check for protontricks (native or flatpak)
	protontricksCmd := ""
	if utils.CommandExists("protontricks") {
		protontricksCmd = "protontricks"
		d.logger.Info("Using native protontricks")
	} else if utils.CommandExists("flatpak") {
		// Check if protontricks flatpak is installed using grep for efficiency
		cmd := exec.Command("sh", "-c", "flatpak list --app --columns=application | grep -q com.github.Matoking.protontricks && echo 'found'")
		output, err := cmd.Output()
		if err == nil && strings.Contains(string(output), "found") {
			protontricksCmd = "flatpak run com.github.Matoking.protontricks"
			d.logger.Info("Using flatpak protontricks")
		}
	}

	if protontricksCmd == "" {
		ui.PrintWarning("Protontricks is not installed.")
		ui.PrintInfo("Install it with:")
		ui.PrintInfo("- Native: sudo apt install protontricks")
		ui.PrintInfo("- Flatpak: flatpak install com.github.Matoking.protontricks")
		return nil
	}

	// Note: We use Proton's Wine instead of system Wine, so no system Wine check needed
	ui.PrintInfo("Using Proton's Wine for installations (no system Wine required)")

	// Check for Steam (not flatpak)
	if utils.CommandExists("flatpak") {
		cmd := exec.Command("flatpak", "list", "--app", "--columns=application")
		output, err := cmd.Output()
		if err == nil && strings.Contains(string(output), "com.valvesoftware.Steam") {
			ui.PrintWarning("Detected Steam installed via Flatpak.")
			ui.PrintInfo("This tool doesn't support Flatpak Steam installations.")
			ui.PrintInfo("Please install Steam natively.")
			return nil
		}
	}

	ui.PrintSuccess("All required dependencies are available!")
	ui.PrintInfo("Protontricks: " + protontricksCmd)
	ui.PrintInfo("Proton Wine: Available")
	ui.PrintInfo("Steam: Native installation detected")

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
		d.logger.Info(fmt.Sprintf("Auto-selected only game: %s (AppID: %s)", selectedGame.Name, selectedGame.AppID))
		return d.installProtonDependencies(selectedGame, protontricksCmd)
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
		d.logger.Info(fmt.Sprintf("Selected game: %s (AppID: %s)", selectedGame.Name, selectedGame.AppID))
		return d.installProtonDependencies(selectedGame, protontricksCmd)
	}

	return nil
}

// GetGameComponents returns the components to install for a specific game (matching shell script logic)
func (d *DependencyInstaller) GetGameComponents(appID string) []string {
	switch appID {
	case "22380": // Fallout New Vegas
		return []string{
			"fontsmooth=rgb",
			"xact",
			"xact_x64",
			"d3dx9_43",
			"d3dx9",
			"vcrun2022",
		}
	case "976620": // Enderal Special Edition
		return []string{
			"fontsmooth=rgb",
			"xact",
			"xact_x64",
			"d3dx11_43",
			"d3dcompiler_43",
			"d3dcompiler_47",
			"vcrun2022",
			"dotnet6",
			"dotnet7",
			"dotnet8",
		}
	default: // Default components for other games
		return []string{
			"fontsmooth=rgb",
			"xact",
			"xact_x64",
			"vcrun2022",
			"dotnet6",
			"dotnet7",
			"dotnet8",
			"dotnetdesktop6",
			"d3dcompiler_47",
			"d3dx11_43",
			"d3dcompiler_43",
			"d3dx9_43",
			"d3dx9",
			"vkd3d",
		}
	}
}

func (d *DependencyInstaller) installProtonDependencies(game utils.Game, protontricksCmd string) error {
	ui.PrintSection("Install Proton Dependencies")
	ui.PrintInfo(fmt.Sprintf("Installing dependencies for %s (AppID: %s)", game.Name, game.AppID))

	// Get components based on game AppID (matching shell script logic)
	components := d.GetGameComponents(game.AppID)

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
	var stdout, stderr bytes.Buffer
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

	return nil
}
