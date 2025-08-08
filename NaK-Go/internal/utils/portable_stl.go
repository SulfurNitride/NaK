package utils

import (
	"embed"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

// Global variable to store the embedded STL filesystem
var embeddedSTLFS embed.FS

// SetEmbeddedSTL sets the embedded STL filesystem
func SetEmbeddedSTL(stl embed.FS) {
	embeddedSTLFS = stl
}

// FindPortableSTL searches for the portable STL in multiple possible locations
func FindPortableSTL() (string, error) {
	// Get the executable path
	executablePath, err := os.Executable()
	if err != nil {
		return "", fmt.Errorf("failed to get executable path: %w", err)
	}

	nakDir := filepath.Dir(executablePath)

	// First, try to copy portable STL to the same directory as nak binary
	if err := copyPortableSTLToBinaryDir(nakDir); err == nil {
		stlPath := filepath.Join(nakDir, "portable_stl", "steamtinkerlaunch")
		if FileExists(stlPath) {
			return stlPath, nil
		}
	}

	// Possible locations to search for portable STL
	possiblePaths := []string{
		// Same directory as nak binary
		filepath.Join(nakDir, "portable_stl", "steamtinkerlaunch"),
		// Current working directory
		filepath.Join(".", "portable_stl", "steamtinkerlaunch"),
		// Home directory
		filepath.Join(os.Getenv("HOME"), "portable_stl", "steamtinkerlaunch"),
		// Downloads directory
		filepath.Join(os.Getenv("HOME"), "Downloads", "portable_stl", "steamtinkerlaunch"),
		// Desktop directory
		filepath.Join(os.Getenv("HOME"), "Desktop", "portable_stl", "steamtinkerlaunch"),
	}

	// Search for the portable STL
	for _, path := range possiblePaths {
		if FileExists(path) {
			return path, nil
		}
	}

	return "", fmt.Errorf("portable steamtinkerlaunch not found in any of the expected locations")
}

// copyPortableSTLToBinaryDir copies the portable STL to the same directory as the nak binary
func copyPortableSTLToBinaryDir(nakDir string) error {
	// Look for portable_stl in the current working directory
	currentSTL := "./portable_stl"
	if !DirectoryExists(currentSTL) {
		return fmt.Errorf("portable_stl directory not found in current directory")
	}

	// Copy to nak binary directory
	targetSTL := filepath.Join(nakDir, "portable_stl")

	// Use cp command to copy the directory
	cmd := exec.Command("cp", "-r", currentSTL, targetSTL)
	return cmd.Run()
}

// RunPortableSTL runs STL with fallback to portable version
func RunPortableSTL(args ...string) error {
	// Try system STL first
	if CommandExists("steamtinkerlaunch") {
		cmd := exec.Command("steamtinkerlaunch", args...)
		return cmd.Run()
	}

	// Fall back to portable STL - try multiple possible locations
	portableSTLPath, err := FindPortableSTL()
	if err != nil {
		return fmt.Errorf("portable steamtinkerlaunch not found: %w", err)
	}

	nakDir := filepath.Dir(portableSTLPath)
	cmd := exec.Command(portableSTLPath, args...)
	cmd.Dir = nakDir // Set working directory

	return cmd.Run()
}

// RunPortableSTLWithOutput runs STL and returns the output
func RunPortableSTLWithOutput(args ...string) (string, error) {
	// Try system STL first
	if CommandExists("steamtinkerlaunch") {
		cmd := exec.Command("steamtinkerlaunch", args...)
		output, err := cmd.CombinedOutput()
		return string(output), err
	}

	// Fall back to portable STL - try multiple possible locations
	portableSTLPath, err := FindPortableSTL()
	if err != nil {
		return "", fmt.Errorf("portable steamtinkerlaunch not found: %w", err)
	}

	nakDir := filepath.Dir(portableSTLPath)
	cmd := exec.Command(portableSTLPath, args...)
	cmd.Dir = nakDir // Set working directory

	output, err := cmd.CombinedOutput()
	return string(output), err
}

// RunEmbeddedSTLWithOutput runs STL and returns the output using embedded STL
func RunEmbeddedSTLWithOutput(args ...string) (string, error) {
	// Try system STL first
	if CommandExists("steamtinkerlaunch") {
		cmd := exec.Command("steamtinkerlaunch", args...)
		output, err := cmd.CombinedOutput()
		return string(output), err
	}

	// Fall back to embedded STL
	stlPath, err := extractEmbeddedSTL()
	if err != nil {
		return "", fmt.Errorf("failed to extract embedded STL: %w", err)
	}

	cmd := exec.Command(stlPath, args...)
	cmd.Dir = filepath.Dir(stlPath) // Set working directory to STL directory

	output, err := cmd.CombinedOutput()
	return string(output), err
}

// extractEmbeddedSTL extracts the embedded STL to the same directory as the nak binary
func extractEmbeddedSTL() (string, error) {
	// Get the directory where nak binary is located
	executablePath, err := os.Executable()
	if err != nil {
		return "", fmt.Errorf("failed to get executable path: %w", err)
	}

	nakDir := filepath.Dir(executablePath)
	stlDir := filepath.Join(nakDir, "embedded_stl")
	stlPath := filepath.Join(stlDir, "steamtinkerlaunch")

	// Check if already extracted
	if FileExists(stlPath) {
		return stlPath, nil
	}

	// Create the embedded_stl directory
	if err := os.MkdirAll(stlDir, 0755); err != nil {
		return "", fmt.Errorf("failed to create embedded STL directory: %w", err)
	}

	// Extract the embedded STL files
	if err := extractEmbeddedSTLFiles(stlDir); err != nil {
		return "", fmt.Errorf("failed to extract embedded STL files: %w", err)
	}

	// Schedule cleanup of embedded_stl directory on program exit
	go func() {
		// Wait a bit to ensure STL has finished using the files
		time.Sleep(5 * time.Second)
		os.RemoveAll(stlDir)
	}()

	return stlPath, nil
}

// extractEmbeddedSTLFiles extracts all embedded STL files to the target directory
func extractEmbeddedSTLFiles(targetDir string) error {
	// Extract steamtinkerlaunch script
	stlContent, err := embeddedSTLFS.ReadFile("portable_stl/steamtinkerlaunch")
	if err != nil {
		return fmt.Errorf("failed to read embedded STL script: %w", err)
	}

	stlPath := filepath.Join(targetDir, "steamtinkerlaunch")
	if err := os.WriteFile(stlPath, stlContent, 0755); err != nil {
		return fmt.Errorf("failed to write STL script: %w", err)
	}

	// Extract lang directory if it exists
	langEntries, err := embeddedSTLFS.ReadDir("portable_stl/lang")
	if err == nil {
		langDir := filepath.Join(targetDir, "lang")
		if err := os.MkdirAll(langDir, 0755); err != nil {
			return fmt.Errorf("failed to create lang directory: %w", err)
		}

		for _, entry := range langEntries {
			if !entry.IsDir() {
				content, err := embeddedSTLFS.ReadFile("portable_stl/lang/" + entry.Name())
				if err != nil {
					continue // Skip files we can't read
				}

				langFile := filepath.Join(langDir, entry.Name())
				if err := os.WriteFile(langFile, content, 0644); err != nil {
					continue // Skip files we can't write
				}
			}
		}
	}

	// Create STL configuration directory in user's home directory
	homeDir, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("failed to get home directory: %w", err)
	}

	stlConfigDir := filepath.Join(homeDir, ".config", "steamtinkerlaunch")
	if err := os.MkdirAll(stlConfigDir, 0755); err != nil {
		return fmt.Errorf("failed to create STL config directory: %w", err)
	}

	// Create global.conf with dependency checks disabled
	globalConf := `# STL Configuration for embedded usage
SKIPINTDEPCHECK="1"
`
	globalConfPath := filepath.Join(stlConfigDir, "global.conf")
	if err := os.WriteFile(globalConfPath, []byte(globalConf), 0644); err != nil {
		return fmt.Errorf("failed to write STL global.conf: %w", err)
	}

	return nil
}
