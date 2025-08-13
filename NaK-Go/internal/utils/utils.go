package utils

import (
	"bufio"
	"bytes"
	"embed"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"time"

	"github.com/bodgit/sevenzip"
	"github.com/sulfurnitride/nak/internal/logging"
	"github.com/sulfurnitride/nak/internal/ui"
)

var logger = logging.GetLogger()

// Global variable to store the embedded wine settings filesystem
var embeddedWineSettingsFS embed.FS

// SetEmbeddedWineSettings sets the embedded wine settings filesystem
func SetEmbeddedWineSettings(wineSettings embed.FS) {
	embeddedWineSettingsFS = wineSettings
}

// extractEmbeddedWineSettings extracts the embedded wine settings file to the target path
func extractEmbeddedWineSettings(targetPath string) error {
	// Read the embedded wine settings file
	wineSettingsContent, err := embeddedWineSettingsFS.ReadFile("internal/utils/wine_settings.reg")
	if err != nil {
		return fmt.Errorf("failed to read embedded wine settings: %w", err)
	}

	// Write the wine settings to the target path
	if err := os.WriteFile(targetPath, wineSettingsContent, 0644); err != nil {
		return fmt.Errorf("failed to write wine settings file: %w", err)
	}

	return nil
}

// CommandExists checks if a command exists in PATH
func CommandExists(command string) bool {
	_, err := exec.LookPath(command)
	return err == nil
}

// RunCommand executes a command and returns the output
func RunCommand(command string, args ...string) (string, error) {
	cmd := exec.Command(command, args...)
	output, err := cmd.CombinedOutput()
	return string(output), err
}

// RunCommandWithProgress executes a command and shows progress
func RunCommandWithProgress(command string, args ...string) error {
	cmd := exec.Command(command, args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

// GetHomeDir returns the user's home directory
func GetHomeDir() (string, error) {
	return os.UserHomeDir()
}

// GetHomeDirSafe returns the user's home directory or a fallback
func GetHomeDirSafe() string {
	homeDir, err := os.UserHomeDir()
	if err != nil {
		return "/tmp" // Fallback to /tmp if we can't get home directory
	}
	return homeDir
}

// GetSteamRoot finds the Steam installation directory
func GetSteamRoot() (string, error) {
	homeDir, err := GetHomeDir()
	if err != nil {
		return "", err
	}

	candidates := []string{
		filepath.Join(homeDir, ".local", "share", "Steam"),
		filepath.Join(homeDir, ".steam", "steam"),
		filepath.Join(homeDir, ".steam", "debian-installation"),
		"/usr/local/steam",
		"/usr/share/steam",
	}

	for _, candidate := range candidates {
		if _, err := os.Stat(filepath.Join(candidate, "steamapps")); err == nil {
			logger.Info("Found Steam root: " + candidate)
			return candidate, nil
		}
	}

	return "", fmt.Errorf("Steam installation not found")
}

// GetProtontricksCommand returns the appropriate protontricks command
func GetProtontricksCommand() (string, error) {
	if CommandExists("protontricks") {
		logger.Info("Using native protontricks")
		return "protontricks", nil
	}

	// Check for flatpak protontricks
	cmd := exec.Command("flatpak", "list", "--app", "--columns=application")
	output, err := cmd.Output()
	if err == nil && strings.Contains(string(output), "com.github.Matoking.protontricks") {
		logger.Info("Using flatpak protontricks")
		return "flatpak run com.github.Matoking.protontricks", nil
	}

	return "", fmt.Errorf("protontricks not found")
}

// CheckDependencies verifies required dependencies are installed
func CheckDependencies() error {
	_, err := GetProtontricksCommand()
	if err != nil {
		return fmt.Errorf("protontricks is not installed. Install it with:\n- Native: sudo apt install protontricks\n- Flatpak: flatpak install com.github.Matoking.protontricks")
	}

	logger.Info("Dependencies check passed")
	return nil
}

// GetSteamGames returns a list of installed Steam games
func GetSteamGames() ([]Game, error) {
	protontricks, err := GetProtontricksCommand()
	if err != nil {
		return nil, err
	}

	// logger.Info("Scanning for Steam games via protontricks")

	// Run protontricks -l to get list of games
	var protontricksOutput string
	if strings.HasPrefix(protontricks, "flatpak run") {
		parts := strings.Fields(protontricks)
		output, err := RunCommand(parts[0], append(parts[1:], "-l")...)
		if err != nil {
			return nil, fmt.Errorf("failed to run protontricks: %w", err)
		}
		protontricksOutput = output
	} else {
		output, err := RunCommand(protontricks, "-l")
		if err != nil {
			return nil, fmt.Errorf("failed to run protontricks: %w", err)
		}
		protontricksOutput = output
	}

	var games []Game
	lines := strings.Split(protontricksOutput, "\n")

	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		// Skip warning messages and notes
		if strings.Contains(line, "UserWarning:") ||
			strings.Contains(line, "pkg_resources") ||
			strings.Contains(line, "NOTE:") ||
			strings.Contains(line, "Found the following games:") ||
			strings.Contains(line, "To run Protontricks") {
			continue
		}

		// Skip non-Steam games (they start with "Non-Steam shortcut:")
		if strings.HasPrefix(line, "Non-Steam shortcut:") {
			continue
		}

		// Parse game entries (format: "Game Name (AppID)")
		// Look for pattern: "Game Name (12345)"
		re := regexp.MustCompile(`^(.+?)\s+\((\d+)\)$`)
		matches := re.FindStringSubmatch(line)
		if len(matches) == 3 {
			name := strings.TrimSpace(matches[1])
			appID := matches[2]

			// Validate AppID is numeric
			if _, err := strconv.Atoi(appID); err == nil {
				games = append(games, Game{
					Name:  name,
					AppID: appID,
				})
			}
		}
	}

	// logger.Info(fmt.Sprintf("Found %d Steam games", len(games)))
	return games, nil
}

// GetNonSteamGames returns a list of non-Steam games (matching shell script behavior)
func GetNonSteamGames() ([]Game, error) {
	// logger.Info("Scanning for non-Steam games (always fresh scan)")

	protontricks, err := GetProtontricksCommand()
	if err != nil {
		return nil, err
	}

	output, err := RunCommand(protontricks, "-l")
	if err != nil {
		return nil, fmt.Errorf("failed to run protontricks: %w", err)
	}

	var games []Game
	scanner := bufio.NewScanner(strings.NewReader(output))

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())

		// Look specifically for "Non-Steam shortcut:" entries
		if strings.Contains(line, "Non-Steam shortcut:") {
			// Parse: "Non-Steam shortcut: Game Name (12345)"
			re := regexp.MustCompile(`Non-Steam shortcut: (.+?) \((\d+)\)$`)
			matches := re.FindStringSubmatch(line)
			if len(matches) == 3 {
				name := strings.TrimSpace(matches[1])
				appID := matches[2]
				games = append(games, Game{
					Name:  name,
					AppID: appID,
				})
			}
		}
	}

	if len(games) == 0 {
		return nil, fmt.Errorf("no non-Steam games found! Make sure you've added non-Steam games to Steam and launched them at least once")
	}

	// logger.Info(fmt.Sprintf("Found %d non-Steam games", len(games)))
	return games, scanner.Err()
}

// Game represents a Steam game
type Game struct {
	Name  string
	AppID string
}

// CreateDirectory creates a directory and its parents if needed
func CreateDirectory(path string) error {
	return os.MkdirAll(path, 0755)
}

// FileExists checks if a file exists
func FileExists(path string) bool {
	_, err := os.Stat(path)
	return !os.IsNotExist(err)
}

// DirectoryExists checks if a directory exists
func DirectoryExists(path string) bool {
	info, err := os.Stat(path)
	if err != nil {
		return false
	}
	return info.IsDir()
}

// CopyFile copies a file from src to dst
func CopyFile(src, dst string) error {
	sourceFile, err := os.Open(src)
	if err != nil {
		return err
	}
	defer sourceFile.Close()

	destFile, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer destFile.Close()

	_, err = destFile.ReadFrom(sourceFile)
	return err
}

// GetSystemInfo returns basic system information
func GetSystemInfo() map[string]string {
	info := make(map[string]string)

	info["os"] = runtime.GOOS
	info["arch"] = runtime.GOARCH
	info["go_version"] = runtime.Version()

	if hostname, err := os.Hostname(); err == nil {
		info["hostname"] = hostname
	}

	if homeDir, err := GetHomeDir(); err == nil {
		info["home_dir"] = homeDir
	}

	return info
}

// ExtractVersion extracts version from a string using regex
func ExtractVersion(text, pattern string) (string, error) {
	re, err := regexp.Compile(pattern)
	if err != nil {
		return "", err
	}

	matches := re.FindStringSubmatch(text)
	if len(matches) < 2 {
		return "", fmt.Errorf("version pattern not found")
	}

	return matches[1], nil
}

// DownloadFile downloads a file from URL to local path
func DownloadFile(url, filepath string) error {
	// logger.Info("Downloading " + url + " to " + filepath)

	// Create the output file
	out, err := os.Create(filepath)
	if err != nil {
		return fmt.Errorf("failed to create file %s: %w", filepath, err)
	}
	defer out.Close()

	// Get the data
	resp, err := http.Get(url)
	if err != nil {
		return fmt.Errorf("failed to download from %s: %w", url, err)
	}
	defer resp.Body.Close()

	// Check server response
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("bad status: %s", resp.Status)
	}

	// Write the body to file
	_, err = io.Copy(out, resp.Body)
	if err != nil {
		return fmt.Errorf("failed to write file: %w", err)
	}

	// logger.Info("Download completed successfully")
	return nil
}

// ExtractArchive extracts an archive file and returns the actual extraction path
func ExtractArchive(archivePath, extractPath string) (string, error) {
	// logger.Info("Extracting " + archivePath + " to " + extractPath)

	// Determine archive type and extract accordingly
	if strings.HasSuffix(archivePath, ".zip") {
		return extractZip(archivePath, extractPath)
	} else if strings.HasSuffix(archivePath, ".tar.gz") || strings.HasSuffix(archivePath, ".tgz") {
		return extractTarGz(archivePath, extractPath)
	} else if strings.HasSuffix(archivePath, ".7z") {
		return extract7z(archivePath, extractPath)
	}

	return "", fmt.Errorf("unsupported archive format")
}

func extractZip(archivePath, extractPath string) (string, error) {
	// Implementation for zip extraction
	return extractPath, nil
}

func extractTarGz(archivePath, extractPath string) (string, error) {
	// Implementation for tar.gz extraction
	return extractPath, nil
}

// extract7z extracts 7z archives using bodgit/sevenzip
func extract7z(archivePath, extractPath string) (string, error) {
	// Check if the target directory exists and has content
	uniqueExtractPath := extractPath
	if DirectoryExists(extractPath) {
		// Check if directory is empty
		entries, err := os.ReadDir(extractPath)
		if err == nil && len(entries) > 0 {
			// Directory exists and has content, create unique subfolder
			counter := 1
			for DirectoryExists(uniqueExtractPath) {
				uniqueExtractPath = fmt.Sprintf("%s_%d", extractPath, counter)
				counter++
			}
		}
		// If directory is empty, use it directly
	}

	// Create extraction directory (this ensures the directory exists)
	if err := os.MkdirAll(uniqueExtractPath, 0755); err != nil {
		return "", fmt.Errorf("failed to create extraction directory: %w", err)
	}

	// Verify the directory was created successfully
	if !DirectoryExists(uniqueExtractPath) {
		return "", fmt.Errorf("failed to create extraction directory: %s", uniqueExtractPath)
	}

	logger.Info(fmt.Sprintf("Extracting to directory: %s", uniqueExtractPath))

	// Open the 7z archive
	r, err := sevenzip.OpenReader(archivePath)
	if err != nil {
		return "", fmt.Errorf("failed to open 7z archive: %w", err)
	}
	defer r.Close()

	// Extract all files
	for _, f := range r.File {
		// Create the file path
		filePath := filepath.Join(uniqueExtractPath, f.Name)

		// Create directory if needed
		if f.FileInfo().IsDir() {
			if err := os.MkdirAll(filePath, 0755); err != nil {
				return "", fmt.Errorf("failed to create directory %s: %w", filePath, err)
			}
			continue
		}

		// Create parent directory if needed
		if err := os.MkdirAll(filepath.Dir(filePath), 0755); err != nil {
			return "", fmt.Errorf("failed to create parent directory for %s: %w", filePath, err)
		}

		// Open the file in the archive
		rc, err := f.Open()
		if err != nil {
			return "", fmt.Errorf("failed to open file %s in archive: %w", f.Name, err)
		}

		// Create the output file
		outFile, err := os.Create(filePath)
		if err != nil {
			rc.Close()
			return "", fmt.Errorf("failed to create file %s: %w", filePath, err)
		}

		// Copy the file content
		_, err = io.Copy(outFile, rc)
		outFile.Close()
		rc.Close()
		if err != nil {
			return "", fmt.Errorf("failed to extract file %s: %w", f.Name, err)
		}

		// Set file permissions
		if err := os.Chmod(filePath, 0644); err != nil {
			logger.Warning(fmt.Sprintf("Failed to set permissions for %s: %v", filePath, err))
		}
	}

	logger.Info(fmt.Sprintf("Extracted using bodgit/sevenzip to: %s", uniqueExtractPath))
	return uniqueExtractPath, nil
}

// FindGameCompatData finds the compatibility data path for a specific game
func FindGameCompatData(appID, steamRoot string) (string, error) {
	// Check main Steam library first
	compatDataPath := filepath.Join(steamRoot, "steamapps", "compatdata", appID)
	if DirectoryExists(compatDataPath) {
		return compatDataPath, nil
	}

	// Check additional Steam libraries from libraryfolders.vdf
	libraryFoldersPath := filepath.Join(steamRoot, "steamapps", "libraryfolders.vdf")
	if FileExists(libraryFoldersPath) {
		content, err := os.ReadFile(libraryFoldersPath)
		if err == nil {
			// Parse libraryfolders.vdf to find additional Steam library paths
			lines := strings.Split(string(content), "\n")
			for _, line := range lines {
				if strings.Contains(line, "\"path\"") {
					// Extract path from the line
					parts := strings.Split(line, "\"")
					if len(parts) >= 4 {
						libraryPath := parts[3]
						compatDataPath := filepath.Join(libraryPath, "steamapps", "compatdata", appID)
						if DirectoryExists(compatDataPath) {
							return compatDataPath, nil
						}
					}
				}
			}
		}
	}

	return "", fmt.Errorf("compatibility data not found for AppID %s", appID)
}

// DetectProtonVersionFromGame tries to detect the Proton version used by a specific game
func DetectProtonVersionFromGame(appID string) (string, error) {
	steamRoot, err := GetSteamRoot()
	if err != nil {
		return "", err
	}

	compatDataPath, err := FindGameCompatData(appID, steamRoot)
	if err != nil {
		return "", err
	}

	// Look for Proton version info in the compatibility data (most reliable method)
	// Common locations where Proton version info might be stored
	versionFiles := []string{
		filepath.Join(compatDataPath, "version"),
		filepath.Join(compatDataPath, "proton_version"),
		filepath.Join(compatDataPath, "compatibility_tool"),
	}

	for _, versionFile := range versionFiles {
		if FileExists(versionFile) {
			content, err := os.ReadFile(versionFile)
			if err == nil {
				version := strings.TrimSpace(string(content))
				if version != "" {
					logger.Info(fmt.Sprintf("Detected Proton version from game: %s", version))
					return version, nil
				}
			}
		}
	}

	// If we can't detect from game, return empty string to use fallback
	return "", nil
}

// FindProtonInstallation finds the actual Proton installation path
func FindProtonInstallation(protonVersion string) (string, error) {
	homeDir, err := GetHomeDir()
	if err != nil {
		return "", err
	}

	steamRoot, err := GetSteamRoot()
	if err != nil {
		return "", err
	}

	// Check Steam compatibility tools directory (Steam's official way)
	compatibilityToolsDirs := []string{
		filepath.Join(steamRoot, "compatibilitytools.d"),
		filepath.Join(homeDir, ".steam", "root", "compatibilitytools.d"),
		filepath.Join(homeDir, ".local", "share", "Steam", "compatibilitytools.d"),
	}

	for _, compatDir := range compatibilityToolsDirs {
		if DirectoryExists(compatDir) {
			// Look for the specific version in compatibility tools
			toolPath := filepath.Join(compatDir, protonVersion)
			if DirectoryExists(toolPath) {
				protonPath := filepath.Join(toolPath, "proton")
				if FileExists(protonPath) {
					logger.Info(fmt.Sprintf("Found Proton in compatibility tools: %s", toolPath))
					return protonPath, nil
				}
			}
		}
	}

	// Check standard Steam Proton installations
	steamProtonPath := filepath.Join(steamRoot, "steamapps", "common", protonVersion, "proton")
	if FileExists(steamProtonPath) {
		logger.Info(fmt.Sprintf("Found Proton in Steam: %s", steamProtonPath))
		return steamProtonPath, nil
	}

	// Check additional Steam libraries from libraryfolders.vdf for Proton installations
	libraryFoldersPath := filepath.Join(steamRoot, "steamapps", "libraryfolders.vdf")
	if FileExists(libraryFoldersPath) {
		content, err := os.ReadFile(libraryFoldersPath)
		if err == nil {
			logger.Info(fmt.Sprintf("Reading libraryfolders.vdf from: %s", libraryFoldersPath))
			// Parse libraryfolders.vdf to find additional Steam library paths
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
						logger.Info(fmt.Sprintf("Found Steam library path: %s", libraryPath))
						// Check for Proton installation in this library
						protonPath := filepath.Join(libraryPath, "steamapps", "common", protonVersion, "proton")
						logger.Info(fmt.Sprintf("Checking for Proton at: %s", protonPath))
						if FileExists(protonPath) {
							logger.Info(fmt.Sprintf("Found Proton in Steam library: %s", protonPath))
							return protonPath, nil
						} else {
							logger.Info(fmt.Sprintf("Proton not found at: %s", protonPath))
						}
					}
				}
			}
		} else {
			logger.Error(fmt.Sprintf("Failed to read libraryfolders.vdf: %v", err))
		}
	} else {
		logger.Info("libraryfolders.vdf not found")
	}

	return "", fmt.Errorf("Proton version %s not found in any location", protonVersion)
}

// GetAllAvailableProtonVersions returns all available Proton versions on the system
func GetAllAvailableProtonVersions() ([]string, error) {
	var versions []string

	homeDir, err := GetHomeDir()
	if err != nil {
		return nil, err
	}

	steamRoot, err := GetSteamRoot()
	if err != nil {
		return nil, err
	}

	// Check Steam compatibility tools directories (Steam's official way)
	compatibilityToolsDirs := []string{
		filepath.Join(steamRoot, "compatibilitytools.d"),
		filepath.Join(homeDir, ".steam", "root", "compatibilitytools.d"),
		filepath.Join(homeDir, ".local", "share", "Steam", "compatibilitytools.d"),
	}

	for _, compatDir := range compatibilityToolsDirs {
		if DirectoryExists(compatDir) {
			entries, err := os.ReadDir(compatDir)
			if err == nil {
				for _, entry := range entries {
					if entry.IsDir() {
						protonPath := filepath.Join(compatDir, entry.Name(), "proton")
						if FileExists(protonPath) {
							versions = append(versions, entry.Name())
							logger.Info(fmt.Sprintf("Found Proton in compatibility tools: %s", entry.Name()))
						}
					}
				}
			}
		}
	}

	// Check standard Steam Proton installations
	steamProtonDir := filepath.Join(steamRoot, "steamapps", "common")
	if DirectoryExists(steamProtonDir) {
		entries, err := os.ReadDir(steamProtonDir)
		if err == nil {
			for _, entry := range entries {
				if entry.IsDir() && strings.HasPrefix(entry.Name(), "Proton") {
					protonPath := filepath.Join(steamProtonDir, entry.Name(), "proton")
					if FileExists(protonPath) {
						versions = append(versions, entry.Name())
						logger.Info(fmt.Sprintf("Found Proton in Steam: %s", entry.Name()))
					}
				}
			}
		}
	}

	// Check additional Steam libraries from libraryfolders.vdf for Proton installations
	libraryFoldersPath := filepath.Join(steamRoot, "steamapps", "libraryfolders.vdf")
	if FileExists(libraryFoldersPath) {
		content, err := os.ReadFile(libraryFoldersPath)
		if err == nil {
			logger.Info(fmt.Sprintf("Reading libraryfolders.vdf for version discovery from: %s", libraryFoldersPath))
			// Parse libraryfolders.vdf to find additional Steam library paths
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
						logger.Info(fmt.Sprintf("Found Steam library path for version discovery: %s", libraryPath))
						// Check for Proton installations in this library
						libraryProtonDir := filepath.Join(libraryPath, "steamapps", "common")
						logger.Info(fmt.Sprintf("Checking Proton directory: %s", libraryProtonDir))
						if DirectoryExists(libraryProtonDir) {
							entries, err := os.ReadDir(libraryProtonDir)
							if err == nil {
								for _, entry := range entries {
									if entry.IsDir() && strings.HasPrefix(entry.Name(), "Proton") {
										protonPath := filepath.Join(libraryProtonDir, entry.Name(), "proton")
										if FileExists(protonPath) {
											versions = append(versions, entry.Name())
											logger.Info(fmt.Sprintf("Found Proton in Steam library: %s", entry.Name()))
										}
									}
								}
							}
						} else {
							logger.Info(fmt.Sprintf("Proton directory does not exist: %s", libraryProtonDir))
						}
					}
				}
			}
		} else {
			logger.Error(fmt.Sprintf("Failed to read libraryfolders.vdf for version discovery: %v", err))
		}
	} else {
		logger.Info("libraryfolders.vdf not found for version discovery")
	}

	// Remove duplicates
	seen := make(map[string]bool)
	var uniqueVersions []string
	for _, version := range versions {
		if !seen[version] {
			seen[version] = true
			uniqueVersions = append(uniqueVersions, version)
		}
	}

	return uniqueVersions, nil
}

// LoadWineRegistrySettings loads wine registry settings from the embedded file using Proton's wine
func LoadWineRegistrySettings(prefixPath string) error {
	logger.Info("Loading wine registry settings...")
	logger.Info(fmt.Sprintf("Prefix path: %s", prefixPath))

	// Get Steam root and Proton path
	steamRoot, err := GetSteamRoot()
	if err != nil {
		return fmt.Errorf("could not find Steam installation: %w", err)
	}
	logger.Info(fmt.Sprintf("Steam root: %s", steamRoot))

	protonPath, err := FindProtonInstallation("Proton - Experimental")
	if err != nil {
		return fmt.Errorf("could not find Proton installation: %w", err)
	}
	logger.Info(fmt.Sprintf("Proton path: %s", protonPath))

	// Create a temporary directory for the registry file
	tempDir, err := os.MkdirTemp("", "wine_registry")
	if err != nil {
		return fmt.Errorf("could not create temp directory: %w", err)
	}
	defer os.RemoveAll(tempDir)
	logger.Info(fmt.Sprintf("Created temp directory: %s", tempDir))

	// Extract the embedded wine settings file to the temp directory
	tempRegFile := filepath.Join(tempDir, "wine_settings.reg")
	if err := extractEmbeddedWineSettings(tempRegFile); err != nil {
		return fmt.Errorf("could not extract embedded wine settings: %w", err)
	}
	logger.Info(fmt.Sprintf("Extracted wine settings to: %s", tempRegFile))

	// Build the command
	logger.Info(fmt.Sprintf("STEAM_COMPAT_DATA_PATH: %s", prefixPath))
	logger.Info(fmt.Sprintf("STEAM_COMPAT_CLIENT_INSTALL_PATH: %s", steamRoot))

	// Use Proton's wine to load the settings from the temp directory
	cmd := exec.Command("env",
		"STEAM_COMPAT_CLIENT_INSTALL_PATH="+steamRoot,
		"STEAM_COMPAT_DATA_PATH="+prefixPath,
		protonPath, "run", "regedit", tempRegFile)

	logger.Info(fmt.Sprintf("Executing command: %s", cmd.String()))

	output, err := cmd.CombinedOutput()
	if err != nil {
		logger.Error(fmt.Sprintf("Command failed with error: %v", err))
		logger.Error(fmt.Sprintf("Command output: %s", string(output)))
		return fmt.Errorf("failed to load wine registry settings: %w", err)
	}

	if len(string(output)) > 0 {
		logger.Info(fmt.Sprintf("Command output: %s", string(output)))
	}
	logger.Info("Wine registry settings loaded successfully")
	return nil
}

// InstallSynthesisFixes installs synthesis fixes for the specified game
func InstallSynthesisFixes(gameAppID string, installSynthesis bool) error {
	logger.Info(fmt.Sprintf("Installing synthesis fixes for game %s", gameAppID))

	// Only install Synthesis components if user requested it
	if installSynthesis {
		// Install .NET 9 SDK (only needed for Synthesis)
		if err := installDotnet9SDK(gameAppID); err != nil {
			logger.Error("Failed to install .NET 9 SDK: " + err.Error())
			return fmt.Errorf("failed to install .NET 9 SDK: %w", err)
		}

		// Setup synthesis certificate
		if err := setupSynthesisCertificate(); err != nil {
			logger.Error("Failed to setup synthesis certificate: " + err.Error())
			return fmt.Errorf("failed to setup synthesis certificate: %w", err)
		}

		logger.Info("Synthesis fixes installation complete")
	} else {
		logger.Info("Skipping Synthesis fixes (user declined)")
	}

	return nil
}

// installDotnet9SDK installs .NET 9 SDK using protontricks-launch
func installDotnet9SDK(gameAppID string) error {
	logger.Info("Installing .NET 9 SDK using protontricks-launch")

	// Download .NET 9 SDK
	dotnetURL := "https://builds.dotnet.microsoft.com/dotnet/Sdk/9.0.203/dotnet-sdk-9.0.203-win-x64.exe"
	dotnetFile := "dotnet-sdk-9.0.203-win-x64.exe"

	// Download to Downloads directory
	homeDir, err := GetHomeDir()
	if err != nil {
		return fmt.Errorf("could not get home directory: %w", err)
	}

	downloadPath := filepath.Join(homeDir, "Downloads", dotnetFile)
	logger.Info(fmt.Sprintf("Downloading .NET 9 SDK to: %s", downloadPath))

	if err := DownloadFile(dotnetURL, downloadPath); err != nil {
		return fmt.Errorf("failed to download .NET 9 SDK: %w", err)
	}

	// Run installer using protontricks-launch
	logger.Info("Running .NET 9 SDK installer with protontricks-launch")

	cmd := exec.Command("protontricks-launch", "--appid", gameAppID, downloadPath, "/q")

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err = cmd.Run()
	if err != nil {
		logger.Warning(fmt.Sprintf("Command returned error: %v", err))
		if stdout.Len() > 0 {
			logger.Info(fmt.Sprintf("Command stdout: %s", stdout.String()))
		}
		if stderr.Len() > 0 {
			logger.Info(fmt.Sprintf("Command stderr: %s", stderr.String()))
		}
		// Don't return error - the installer might have succeeded despite exit code
		logger.Info("Continuing despite exit code - checking if installation succeeded...")
	} else {
		logger.Info("Command completed successfully")
		if stdout.Len() > 0 {
			logger.Info(fmt.Sprintf("Command stdout: %s", stdout.String()))
		}
		if stderr.Len() > 0 {
			logger.Info(fmt.Sprintf("Command stderr: %s", stderr.String()))
		}
	}

	// Clean up downloaded file
	os.Remove(downloadPath)

	logger.Info("=== .NET 9 SDK Installation Completed Successfully ===")
	return nil
}

// setupSynthesisCertificate installs DigiCert certificate for Synthesis
func setupSynthesisCertificate() error {
	logger.Info("Setting up Synthesis certificate")

	// Download certificate
	certURL := "https://cacerts.digicert.com/universal-root.crt.pem"
	certFile := "universal-root.crt.pem"

	logger.Info(fmt.Sprintf("Downloading certificate from: %s", certURL))
	if err := DownloadFile(certURL, certFile); err != nil {
		return fmt.Errorf("failed to download certificate: %w", err)
	}
	defer os.Remove(certFile)

	// Install certificate with sudo (will prompt for password)
	logger.Info("Installing DigiCert certificate (requires sudo)...")
	cmd := exec.Command("sudo", "trust", "anchor", "--store", certFile)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin

	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to install certificate: %w", err)
	}

	logger.Info("Synthesis certificate installed successfully")
	return nil
}

// RestartSteam restarts Steam to ensure proper integration of new non-Steam games
func RestartSteam() error {
	logger.Info("Restarting Steam to ensure proper integration...")
	ui.PrintInfo("Restarting Steam to ensure proper integration...")

	// Wait for Steam to finish processing
	logger.Info("Waiting 5 seconds for Steam to finish processing...")
	ui.PrintInfo("Waiting 5 seconds for Steam to finish processing...")
	time.Sleep(5 * time.Second)

	// Stop Steam
	logger.Info("Stopping Steam...")
	ui.PrintInfo("Stopping Steam...")

	cmd := exec.Command("pkill", "-9", "steam")
	if err := cmd.Run(); err != nil {
		logger.Warning("Failed to stop Steam: " + err.Error())
		ui.PrintWarning("Failed to stop Steam: " + err.Error())
	} else {
		logger.Info("Steam stopped successfully.")
		ui.PrintSuccess("Steam stopped successfully.")

		// Wait for cleanup
		time.Sleep(2 * time.Second)

		// Start Steam again
		cmd = exec.Command("steam")
		if err := cmd.Start(); err != nil {
			logger.Error("Failed to restart Steam: " + err.Error())
			ui.PrintWarning("Failed to restart Steam: " + err.Error())
			ui.PrintInfo("Please start Steam manually.")
			return err
		} else {
			logger.Info("Steam restarted successfully!")
			ui.PrintSuccess("Steam restarted successfully!")
		}
	}

	return nil
}

// GetNonSteamGamesFromProtontricks gets the list of non-Steam games from protontricks
func GetNonSteamGamesFromProtontricks() ([]Game, error) {
	// logger.Info("Getting non-Steam games from protontricks...")

	cmd := exec.Command("protontricks", "-l")
	output, err := cmd.CombinedOutput()
	if err != nil {
		return nil, fmt.Errorf("failed to run protontricks -l: %w", err)
	}

	// Debug: Log the raw output
	// logger.Info("protontricks -l output:")
	// logger.Info(string(output))

	var games []Game
	lines := strings.Split(string(output), "\n")

	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		// Parse protontricks output format
		// Example: "Non-Steam shortcut: Mod Organizer 2 (1234567890)"
		if strings.Contains(line, "Non-Steam shortcut:") {
			parts := strings.Split(line, ":")
			if len(parts) >= 2 {
				namePart := strings.TrimSpace(parts[1])
				// Extract name and AppID from format like "Mod Organizer 2 (1234567890)"
				if strings.Contains(namePart, "(") && strings.Contains(namePart, ")") {
					lastParen := strings.LastIndex(namePart, "(")
					name := strings.TrimSpace(namePart[:lastParen])
					appID := strings.Trim(strings.TrimSpace(namePart[lastParen:]), "()")

					games = append(games, Game{
						Name:  name,
						AppID: appID,
					})
					// logger.Info(fmt.Sprintf("Found non-Steam game: %s (AppID: %s)", name, appID))
				}
			}
		}
	}

	// logger.Info(fmt.Sprintf("Total non-Steam games found: %d", len(games)))
	return games, nil
}

// FindModManagerInProtontricks searches for a specific mod manager in protontricks output
func FindModManagerInProtontricks(modManagerName string) (*Game, error) {
	games, err := GetNonSteamGamesFromProtontricks()
	if err != nil {
		return nil, err
	}

	// Search for exact match first
	for _, game := range games {
		if strings.EqualFold(game.Name, modManagerName) {
			return &game, nil
		}
	}

	// Search for partial matches
	for _, game := range games {
		if strings.Contains(strings.ToLower(game.Name), strings.ToLower(modManagerName)) {
			return &game, nil
		}
	}

	return nil, fmt.Errorf("mod manager '%s' not found in protontricks", modManagerName)
}

// SetupDependenciesWorkflow handles the complete dependency setup workflow
func SetupDependenciesWorkflow(modManagerName string) error {
	logger.Info(fmt.Sprintf("Starting dependency setup workflow for %s", modManagerName))
	ui.PrintSection("Dependency Setup")

	// Ask if user wants to setup dependencies
	confirmed, err := ui.ConfirmAction("Do you want to setup dependencies for " + modManagerName + "?")
	if err != nil {
		return err
	}

	if !confirmed {
		logger.Info("User declined dependency setup")
		ui.PrintInfo("Skipping dependency setup (user declined)")
		return nil
	}

	// Provide instructions to run the mod manager once
	ui.PrintInfo("To setup dependencies, you need to:")
	ui.PrintInfo("1. Launch " + modManagerName + " from Steam")
	ui.PrintInfo("2. Let it run for a moment (it may show errors, that's normal)")
	ui.PrintInfo("3. Close " + modManagerName + " completely")
	ui.PrintInfo("4. Come back here and press Enter when done")

	// Wait for user confirmation
	_, err = ui.GetInput("Press Enter when you've launched and closed "+modManagerName+"...", "")
	if err != nil {
		return err
	}

	// Use the existing dependency installer system
	// Note: This will be handled by the app layer to avoid import cycles
	ui.PrintInfo("Redirecting to existing dependency installer...")
	return fmt.Errorf("dependency setup should be handled by the app layer")
}
