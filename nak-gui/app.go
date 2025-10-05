package main

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

// App struct
type App struct {
	ctx context.Context
}

// NewApp creates a new App application struct
func NewApp() *App {
	return &App{}
}

// startup is called when the app starts. The context is saved
// so we can call the runtime methods
func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
}

// Game represents a detected game
type Game struct {
	Name     string `json:"name"`
	Path     string `json:"path"`
	Platform string `json:"platform"`
	AppID    string `json:"app_id"`
}

// ScanGamesResult represents the result of scanning for games
type ScanGamesResult struct {
	Success bool   `json:"success"`
	Count   int    `json:"count"`
	Games   []Game `json:"games"`
	Error   string `json:"error,omitempty"`
}

// DependencyInfo represents information about a dependency
type DependencyInfo struct {
	Installed bool   `json:"installed"`
	Version   string `json:"version,omitempty"`
	Status    string `json:"status"`
}

// CheckDependenciesResult represents the result of checking dependencies
type CheckDependenciesResult struct {
	Success      bool                      `json:"success"`
	Dependencies map[string]DependencyInfo `json:"dependencies"`
	Error        string                    `json:"error,omitempty"`
}

// executeBackend runs the Python backend with the given arguments
func (a *App) executeBackend(args ...string) ([]byte, error) {
	// Check if we're running in an AppImage
	appDir := os.Getenv("APPDIR")
	fmt.Printf("APPDIR environment variable: %s\n", appDir)

	// Get the directory where the current executable is running from
	exePath, err := os.Executable()
	var exeDir string
	if err != nil {
		fmt.Printf("Warning: Could not get executable path: %v\n", err)
	} else {
		exeDir = filepath.Dir(exePath)
		fmt.Printf("Executable directory: %s\n", exeDir)
	}

	// Try multiple possible paths for the backend
	backendPaths := []string{}

	// If running in AppImage, try APPDIR path first
	if appDir != "" {
		backendPaths = append(backendPaths, filepath.Join(appDir, "usr", "bin", "nak-backend"))
	}

	// If we got the executable directory, try the absolute path
	if exeDir != "" {
		backendPaths = append(backendPaths, filepath.Join(exeDir, "nak-backend"))
	}

	// Then try relative paths
	backendPaths = append(backendPaths,
		"./nak-backend",       // Same directory as executable
		"nak-backend",         // PATH lookup
		"../nak-backend",      // Parent directory
		"../dist/nak_backend", // Development path
	)

	var lastErr error
	for _, path := range backendPaths {
		fmt.Printf("Trying backend path: %s\n", path)

		cmd := exec.Command(path, args...)

		// Pass environment variables to the Python backend
		cmd.Env = os.Environ()

		output, err := cmd.CombinedOutput()
		if err == nil {
			fmt.Printf("Backend executed successfully with path: %s\n", path)
			return output, nil
		}
		fmt.Printf("Backend execution failed with path %s: %v\n", path, err)
		fmt.Printf("Backend error output: %s\n", string(output))
		lastErr = err
	}

	return nil, fmt.Errorf("failed to execute backend (tried %d paths): %v", len(backendPaths), lastErr)
}

// executeBackendWithStreaming executes the backend command and streams output in real-time
func (a *App) executeBackendWithStreaming(command string, args ...string) ([]byte, error) {
	// Find the backend executable (same logic as executeBackend)
	executablePath, err := os.Executable()
	if err != nil {
		return nil, fmt.Errorf("failed to get executable path: %v", err)
	}

	executableDir := filepath.Dir(executablePath)
	fmt.Printf("Executable directory: %s\n", executableDir)

	// Try different possible paths for the backend
	backendPaths := []string{
		filepath.Join(executableDir, "nak-backend"), // AppImage path
		"./nak-backend", // Relative path
		"nak-backend",   // System PATH
	}

	var lastErr error
	for _, backendPath := range backendPaths {
		fmt.Printf("Trying backend path: %s\n", backendPath)

		// Build the command
		cmdArgs := append([]string{command}, args...)
		cmd := exec.Command(backendPath, cmdArgs...)

		// Pass environment variables to the Python backend
		cmd.Env = os.Environ()

		// Set up pipes for streaming output
		stdout, err := cmd.StdoutPipe()
		if err != nil {
			lastErr = fmt.Errorf("failed to create stdout pipe: %v", err)
			continue
		}

		stderr, err := cmd.StderrPipe()
		if err != nil {
			lastErr = fmt.Errorf("failed to create stderr pipe: %v", err)
			continue
		}

		// Start the command
		if err := cmd.Start(); err != nil {
			lastErr = fmt.Errorf("failed to start backend: %v", err)
			continue
		}

		// Stream output in real-time
		var allOutput []byte
		scanner := bufio.NewScanner(stdout)
		for scanner.Scan() {
			line := scanner.Bytes()
			allOutput = append(allOutput, line...)
			allOutput = append(allOutput, '\n')

			// Print the line to console for debugging
			fmt.Printf("Backend output: %s\n", string(line))
		}

		// Also capture stderr
		stderrScanner := bufio.NewScanner(stderr)
		for stderrScanner.Scan() {
			line := stderrScanner.Bytes()
			allOutput = append(allOutput, line...)
			allOutput = append(allOutput, '\n')
			fmt.Printf("Backend stderr: %s\n", string(line))
		}

		// Wait for the command to complete
		if err := cmd.Wait(); err != nil {
			lastErr = fmt.Errorf("backend execution failed with path %s: %v", backendPath, err)
			continue
		}

		fmt.Printf("Backend executed successfully with path: %s\n", backendPath)
		return allOutput, nil
	}

	return nil, fmt.Errorf("failed to execute backend (tried %d paths): %v", len(backendPaths), lastErr)
}

// ScanGames scans for installed games
func (a *App) ScanGames() ScanGamesResult {
	fmt.Printf("ScanGames: Calling executeBackend with 'list-games'\n")
	output, err := a.executeBackend("list-games")
	if err != nil {
		fmt.Printf("ScanGames: Backend execution error: %v\n", err)
		return ScanGamesResult{
			Success: false,
			Error:   err.Error(),
		}
	}

	fmt.Printf("ScanGames: Backend output length: %d\n", len(output))

	// Extract JSON from output (skip log messages)
	jsonOutput := extractJSON(output)
	fmt.Printf("ScanGames: Extracted JSON: %s\n", string(jsonOutput))

	var result ScanGamesResult
	if err := json.Unmarshal(jsonOutput, &result); err != nil {
		fmt.Printf("ScanGames: JSON parsing error: %v\n", err)
		return ScanGamesResult{
			Success: false,
			Error:   fmt.Sprintf("Failed to parse response: %v", err),
		}
	}

	fmt.Printf("ScanGames: Parsed result - Success: %v, Count: %d, Games: %d\n", result.Success, result.Count, len(result.Games))
	return result
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// extractJSON extracts JSON from output that may contain log messages
func extractJSON(output []byte) []byte {
	// Convert to string for easier manipulation
	str := string(output)

	// Find the first '{' character (start of JSON object)
	start := strings.Index(str, "{")
	if start == -1 {
		return output // No JSON found, return as-is
	}

	// Count braces to find the matching closing brace
	braceCount := 0
	end := -1
	for i := start; i < len(str); i++ {
		if str[i] == '{' {
			braceCount++
		} else if str[i] == '}' {
			braceCount--
			if braceCount == 0 {
				end = i + 1
				break
			}
		}
	}

	if end == -1 {
		return output[start:] // No end found, return from start
	}

	return []byte(str[start:end])
}

// CheckDependencies checks system dependencies
func (a *App) CheckDependencies() CheckDependenciesResult {
	output, err := a.executeBackend("check-deps")
	if err != nil {
		return CheckDependenciesResult{
			Success: false,
			Error:   err.Error(),
		}
	}

	var result CheckDependenciesResult
	if err := json.Unmarshal(output, &result); err != nil {
		return CheckDependenciesResult{
			Success: false,
			Error:   fmt.Sprintf("Failed to parse response: %v", err),
		}
	}

	return result
}

// TestInstallMO2 is a simple test function
func (a *App) TestInstallMO2(installDir string) string {
	fmt.Printf("TestInstallMO2 called with: %s\n", installDir)
	return fmt.Sprintf(`{"success": true, "message": "Test completed successfully", "install_dir": "%s"}`, installDir)
}

// InstallMO2WithDirectory installs Mod Organizer 2 to a specific directory
func (a *App) InstallMO2WithDirectory(installDir string) string {
	fmt.Printf("InstallMO2WithDirectory called with: %s\n", installDir)
	fmt.Printf("Calling executeBackend with args: install-mo2, --install-dir, %s\n", installDir)

	// Use streaming backend to get real-time progress
	output, err := a.executeBackendWithStreaming("install-mo2", "--install-dir", installDir)
	if err != nil {
		fmt.Printf("Backend execution error: %v\n", err)
		return fmt.Sprintf("Error: %v", err)
	}
	result := strings.TrimSpace(string(output))
	fmt.Printf("Backend output: %s\n", result)
	return result
}

// SelectDirectory shows a directory selection dialog
func (a *App) SelectDirectory() string {
	fmt.Println("SelectDirectory called")

	// Try the native dialog first
	selectedDir, err := runtime.OpenDirectoryDialog(a.ctx, runtime.OpenDialogOptions{
		Title:            "Select Mod Organizer 2 Installation Directory",
		DefaultDirectory: "/home/luke",
	})
	if err != nil {
		fmt.Printf("Error opening directory dialog: %v\n", err)
		// Fallback: return a default directory
		return "/home/luke/Documents/ModOrganizer2"
	}
	fmt.Printf("Selected directory: %s\n", selectedDir)
	return selectedDir
}

// LaunchMO2 launches Mod Organizer 2
func (a *App) LaunchMO2() string {
	output, err := a.executeBackend("launch-mo2")
	if err != nil {
		return fmt.Sprintf("Error: %v", err)
	}
	return strings.TrimSpace(string(output))
}

// MO2Installation represents a detected MO2 installation
type MO2Installation struct {
	Path    string `json:"path"`
	Exe     string `json:"exe"`
	Prefix  string `json:"prefix"`
	Version string `json:"version"`
}

// FindMO2Result represents the result of finding MO2 installations
type FindMO2Result struct {
	Success       bool              `json:"success"`
	Count         int               `json:"count"`
	Installations []MO2Installation `json:"installations"`
	Error         string            `json:"error,omitempty"`
}

// FindMO2 finds existing MO2 installations
func (a *App) FindMO2() FindMO2Result {
	output, err := a.executeBackend("find-mo2")
	if err != nil {
		return FindMO2Result{
			Success: false,
			Error:   err.Error(),
		}
	}

	var result FindMO2Result
	if err := json.Unmarshal(output, &result); err != nil {
		return FindMO2Result{
			Success: false,
			Error:   fmt.Sprintf("Failed to parse response: %v", err),
		}
	}

	return result
}

// BrowseForMO2Folder opens a directory picker for the user to select MO2 folder
func (a *App) BrowseForMO2Folder() string {
	selection, err := runtime.OpenDirectoryDialog(a.ctx, runtime.OpenDialogOptions{
		Title:            "Select Mod Organizer 2 Folder",
		DefaultDirectory: "",
	})

	if err != nil {
		return fmt.Sprintf(`{"success": false, "error": "%s"}`, err.Error())
	}

	if selection == "" {
		return `{"success": false, "error": "No folder selected"}`
	}

	// Return the selected path as JSON
	return fmt.Sprintf(`{"success": true, "path": "%s"}`, selection)
}

// SetupExistingMO2 sets up an existing MO2 installation
func (a *App) SetupExistingMO2(mo2Path, customName string) string {
	fmt.Printf("SetupExistingMO2 called with path: %s, name: %s\n", mo2Path, customName)
	fmt.Printf("Calling executeBackend with args: setup-existing-mo2, --mo2-path, %s, --custom-name, %s\n", mo2Path, customName)

	// Use streaming backend to get real-time progress
	output, err := a.executeBackendWithStreaming("setup-existing-mo2", "--mo2-path", mo2Path, "--custom-name", customName)
	if err != nil {
		fmt.Printf("Backend execution error: %v\n", err)
		return fmt.Sprintf("Error: %v", err)
	}
	result := strings.TrimSpace(string(output))
	fmt.Printf("Backend output: %s\n", result)
	return result
}

// ConfigureNXMHandler configures NXM handler for a game
func (a *App) ConfigureNXMHandler(appID, nxmHandlerPath string) string {
	fmt.Printf("ConfigureNXMHandler called with AppID: %s, path: %s\n", appID, nxmHandlerPath)
	fmt.Printf("Calling executeBackend with args: configure-nxm-handler, --app-id, %s, --nxm-handler-path, %s\n", appID, nxmHandlerPath)

	output, err := a.executeBackend("configure-nxm-handler", "--app-id", appID, "--nxm-handler-path", nxmHandlerPath)
	if err != nil {
		fmt.Printf("Backend execution error: %v\n", err)
		return fmt.Sprintf("{\"success\": false, \"error\": \"%v\"}", err)
	}

	// Extract JSON from output (skip log messages)
	jsonOutput := extractJSON(output)
	result := strings.TrimSpace(string(jsonOutput))
	fmt.Printf("Backend JSON output: %s\n", result)
	return result
}

// RemoveNXMHandlers removes all NXM handlers
func (a *App) RemoveNXMHandlers() string {
	fmt.Printf("RemoveNXMHandlers called\n")
	fmt.Printf("Calling executeBackend with args: remove-nxm-handlers\n")

	output, err := a.executeBackend("remove-nxm-handlers")
	if err != nil {
		fmt.Printf("Backend execution error: %v\n", err)
		return fmt.Sprintf("{\"success\": false, \"error\": \"%v\"}", err)
	}

	// Extract JSON from output (skip log messages)
	jsonOutput := extractJSON(output)
	result := strings.TrimSpace(string(jsonOutput))
	fmt.Printf("Backend JSON output: %s\n", result)
	return result
}
