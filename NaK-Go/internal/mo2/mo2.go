package mo2

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/sulfurnitride/nak/internal/dependencies"
	"github.com/sulfurnitride/nak/internal/logging"
	"github.com/sulfurnitride/nak/internal/ui"
	"github.com/sulfurnitride/nak/internal/utils"
)

type GitHubRelease struct {
	TagName string `json:"tag_name"`
	Assets  []struct {
		Name               string `json:"name"`
		BrowserDownloadURL string `json:"browser_download_url"`
	} `json:"assets"`
}

type MO2Installer struct {
	logger *logging.Logger
}

func NewMO2Installer() *MO2Installer {
	return &MO2Installer{
		logger: logging.GetLogger(),
	}
}

// DownloadMO2 downloads and installs the latest version of Mod Organizer 2
func (m *MO2Installer) DownloadMO2() error {
	ui.PrintSection("Download Mod Organizer 2")

	// Check dependencies
	if err := m.checkDependencies(); err != nil {
		return err
	}

	// Get latest release info
	release, err := m.getLatestRelease()
	if err != nil {
		return err
	}

	ui.PrintInfo(fmt.Sprintf("Latest version: %s", release.TagName))

	// Debug: show available assets
	m.logger.Info("Available assets:")
	for _, asset := range release.Assets {
		if strings.HasPrefix(asset.Name, "Mod.Organizer-") {
			m.logger.Info(fmt.Sprintf("  - %s", asset.Name))
		}
	}

	// Find the correct asset
	downloadURL, filename, err := m.findMO2Asset(release)
	if err != nil {
		return err
	}

	ui.PrintInfo(fmt.Sprintf("Found asset: %s", filename))

	// Get installation directory
	installDir, err := m.getInstallDirectory()
	if err != nil {
		return err
	}

	// Download the file
	tempFile, err := m.downloadFile(downloadURL, filename)
	if err != nil {
		return err
	}
	defer os.Remove(tempFile)

	// Extract the archive
	actualInstallDir, err := m.extractArchive(tempFile, installDir)
	if err != nil {
		return err
	}

	// Verify installation
	if err := m.verifyInstallation(actualInstallDir); err != nil {
		return err
	}

	ui.PrintSuccess("Mod Organizer 2 installed successfully!")
	ui.PrintInfo(fmt.Sprintf("Installation directory: %s", actualInstallDir))

	// Ask if user wants to add to Steam
	ui.PrintInfo("Would you like to add MO2 to Steam as a non-Steam game?")
	confirmed, err := ui.ConfirmAction("Add to Steam?")
	if err != nil {
		return err
	}

	if confirmed {
		// Find the MO2 executable
		mo2Exe := filepath.Join(actualInstallDir, "ModOrganizer.exe")
		if !utils.FileExists(mo2Exe) {
			// Try to find it in subdirectories
			mo2Exe, err = m.findMO2Executable(actualInstallDir)
			if err != nil {
				ui.PrintWarning("Could not find ModOrganizer.exe. Please add MO2 to Steam manually.")
				return nil
			}
		}

		// Add to Steam using the same approach as the app.go setupExistingMO2 function
		if err := m.addMO2ToSteam(actualInstallDir, mo2Exe); err != nil {
			ui.PrintWarning(fmt.Sprintf("Failed to add MO2 to Steam: %v", err))
		}
	}

	return nil
}

// checkDependencies verifies that required tools are available
func (m *MO2Installer) checkDependencies() error {
	m.logger.Info("Checking MO2 dependencies")

	// Check for curl
	if !utils.CommandExists("curl") {
		return fmt.Errorf("curl is required but not installed")
	}

	// Check for 7z tools
	if !m.check7zTools() {
		ui.PrintInfo("No system 7z tools found. Will use native Go extraction.")
	}

	return nil
}

// check7zTools checks for system 7z tools
func (m *MO2Installer) check7zTools() bool {
	tools := []string{"7z", "7za", "7zr", "7zip", "p7zip"}

	for _, tool := range tools {
		if utils.CommandExists(tool) {
			m.logger.Info(fmt.Sprintf("Found system %s command", tool))
			return true
		}
	}

	return false
}

// getLatestRelease fetches the latest release info from GitHub
func (m *MO2Installer) getLatestRelease() (*GitHubRelease, error) {
	ui.PrintInfo("Fetching latest release information from GitHub...")

	resp, err := http.Get("https://api.github.com/repos/ModOrganizer2/modorganizer/releases/latest")
	if err != nil {
		return nil, fmt.Errorf("failed to fetch release information: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("GitHub API returned status: %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %w", err)
	}

	var release GitHubRelease
	if err := json.Unmarshal(body, &release); err != nil {
		return nil, fmt.Errorf("failed to parse release information: %w", err)
	}

	return &release, nil
}

// findMO2Asset finds the correct MO2 asset in the release
func (m *MO2Installer) findMO2Asset(release *GitHubRelease) (string, string, error) {
	// Look for the exact pattern: Mod.Organizer-X.Y.Z.7z (main release)
	for _, asset := range release.Assets {
		if strings.HasPrefix(asset.Name, "Mod.Organizer-") &&
			strings.HasSuffix(asset.Name, ".7z") &&
			!strings.Contains(asset.Name, "pdbs") &&
			!strings.Contains(asset.Name, "src") &&
			!strings.Contains(asset.Name, "uibase") &&
			!strings.Contains(asset.Name, "uicpp") &&
			!strings.Contains(asset.Name, "bsa") {
			return asset.BrowserDownloadURL, asset.Name, nil
		}
	}

	// If no main release found, look for any 7z file (but exclude problematic ones)
	for _, asset := range release.Assets {
		if strings.HasPrefix(asset.Name, "Mod.Organizer-") &&
			strings.HasSuffix(asset.Name, ".7z") &&
			!strings.Contains(asset.Name, "src") {
			return asset.BrowserDownloadURL, asset.Name, nil
		}
	}

	return "", "", fmt.Errorf("could not find appropriate Mod.Organizer-*.7z asset in the latest release")
}

// getInstallDirectory prompts the user for installation directory
func (m *MO2Installer) getInstallDirectory() (string, error) {
	defaultDir := filepath.Join(os.Getenv("HOME"), "ModOrganizer2")

	ui.PrintInfo(fmt.Sprintf("Default directory: %s", defaultDir))
	ui.PrintInfo("You can use ~ for home directory (e.g., ~/Games/MO2)")

	installDir, err := ui.GetInputWithTabCompletion("Extract to directory", defaultDir)
	if err != nil {
		return "", err
	}

	// Expand ~ to home directory
	if strings.HasPrefix(installDir, "~") {
		homeDir, err := os.UserHomeDir()
		if err != nil {
			return "", fmt.Errorf("failed to get home directory: %w", err)
		}
		installDir = filepath.Join(homeDir, installDir[1:])
	}

	// Create directory if it doesn't exist
	if err := utils.CreateDirectory(installDir); err != nil {
		return "", fmt.Errorf("failed to create directory: %w", err)
	}

	return installDir, nil
}

// downloadFile downloads the MO2 archive
func (m *MO2Installer) downloadFile(url, filename string) (string, error) {
	ui.PrintInfo(fmt.Sprintf("Downloading Mod Organizer 2..."))
	ui.PrintInfo(fmt.Sprintf("From: %s", url))

	// Create temporary file
	tempFile := filepath.Join(os.TempDir(), filename)

	// Download the file
	resp, err := http.Get(url)
	if err != nil {
		return "", fmt.Errorf("failed to download file: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("download failed with status: %d", resp.StatusCode)
	}

	file, err := os.Create(tempFile)
	if err != nil {
		return "", fmt.Errorf("failed to create temporary file: %w", err)
	}
	defer file.Close()

	// Copy the response body to the file
	_, err = io.Copy(file, resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to write file: %w", err)
	}

	ui.PrintSuccess("Download completed!")
	return tempFile, nil
}

// extractArchive extracts the 7z archive and returns the actual extraction path
func (m *MO2Installer) extractArchive(archivePath, extractPath string) (string, error) {
	ui.PrintInfo(fmt.Sprintf("Extracting to %s...", extractPath))

	// Try system 7z tools first
	if m.check7zTools() {
		return m.extractWithSystem7z(archivePath, extractPath)
	}

	// Fall back to native Go extraction
	return utils.ExtractArchive(archivePath, extractPath)
}

// extractWithSystem7z extracts using system 7z tools
func (m *MO2Installer) extractWithSystem7z(archivePath, extractPath string) (string, error) {
	tools := []string{"7z", "7za", "7zr", "7zip", "p7zip"}

	for _, tool := range tools {
		if utils.CommandExists(tool) {
			args := []string{"x", archivePath, "-o" + extractPath, "-y"}
			if err := utils.RunCommandWithProgress(tool, args...); err == nil {
				ui.PrintSuccess(fmt.Sprintf("Extracted using %s", tool))
				return extractPath, nil
			}
		}
	}

	return "", fmt.Errorf("failed to extract with system 7z tools")
}

// verifyInstallation verifies that MO2 was installed correctly
func (m *MO2Installer) verifyInstallation(installDir string) error {
	mo2Exe := filepath.Join(installDir, "ModOrganizer.exe")

	if !utils.FileExists(mo2Exe) {
		// Try to find it in subdirectories
		mo2Exe, err := m.findMO2Executable(installDir)
		if err != nil {
			return fmt.Errorf("could not find ModOrganizer.exe in the extracted files")
		}
		ui.PrintInfo(fmt.Sprintf("Found ModOrganizer.exe in: %s", filepath.Dir(mo2Exe)))
	}

	return nil
}

// findMO2Executable searches for ModOrganizer.exe in subdirectories
func (m *MO2Installer) findMO2Executable(rootDir string) (string, error) {
	var foundPath string

	err := filepath.Walk(rootDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		if !info.IsDir() && info.Name() == "ModOrganizer.exe" {
			foundPath = path
			return filepath.SkipAll // Found it, stop walking
		}

		return nil
	})

	if err != nil && err != filepath.SkipAll {
		return "", err
	}

	if foundPath == "" {
		return "", fmt.Errorf("ModOrganizer.exe not found")
	}

	return foundPath, nil
}

// addMO2ToSteam adds MO2 to Steam as a non-Steam game using steamtinkerlaunch
func (m *MO2Installer) addMO2ToSteam(installDir, mo2Exe string) error {
	m.logger.Info("Adding MO2 to Steam using steamtinkerlaunch...")
	ui.PrintInfo("Adding MO2 to Steam using steamtinkerlaunch...")

	// Ask for custom name
	mo2Name, err := ui.GetInput("What name would you like to use for Mod Organizer 2 in Steam?", "Mod Organizer 2")
	if err != nil {
		return err
	}

	if mo2Name == "" {
		mo2Name = "Mod Organizer 2"
	}

	// Build the steamtinkerlaunch command
	args := []string{
		"ansg", // Add non-Steam game
		fmt.Sprintf("--appname=%s", mo2Name),
		fmt.Sprintf("--exepath=%s", mo2Exe),
		fmt.Sprintf("--startdir=%s", filepath.Dir(mo2Exe)),
		"--compatibilitytool=default",
		"--launchoptions=",
	}

	// m.logger.Info("Running steamtinkerlaunch command...")
	ui.PrintInfo("Running steamtinkerlaunch command...")

	// Run steamtinkerlaunch (system or embedded)
	output, err := utils.RunEmbeddedSTLWithOutput(args...)

	if err != nil {
		m.logger.Error("Failed to add MO2 to Steam: " + err.Error())
		m.logger.Error("steamtinkerlaunch output: " + string(output))
		ui.PrintWarning("Failed to add MO2 to Steam: " + err.Error())
		ui.PrintInfo("steamtinkerlaunch output: " + string(output))
		return fmt.Errorf("failed to add MO2 to Steam: %w", err)
	}

	// m.logger.Info("Successfully added MO2 to Steam using steamtinkerlaunch")
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
			m.logger.Warning("Failed to restart Steam: " + err.Error())
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
			m.logger.Warning("Failed to setup dependencies: " + err.Error())
			ui.PrintWarning("Failed to setup dependencies: " + err.Error())
			ui.PrintInfo("You can setup dependencies manually later using protontricks.")
		}
	}

	return nil
}

// findSteamRoot finds the Steam installation directory
func (m *MO2Installer) findSteamRoot() (string, error) {
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
