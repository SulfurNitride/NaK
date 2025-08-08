package config

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/sulfurnitride/nak/internal/logging"
)

type Config struct {
	LoggingLevel         string
	ShowAdvancedOptions  string
	CheckUpdates         string
	EnableTelemetry      string
	PreferredGameAppID   string
	DefaultScaling       string
	EnableDetailedProgress string
	AutoDetectGames      string
	CacheSteamPath       string
}

var (
	configDir  string
	configFile string
	config     *Config
	logger     *logging.Logger
)

func Init() error {
	logger = logging.GetLogger()
	
	// Set up config directory
	homeDir, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("failed to get home directory: %w", err)
	}
	
	configDir = filepath.Join(homeDir, ".config", "nak")
	configFile = filepath.Join(configDir, "config.ini")
	
	// Create config directory if it doesn't exist
	if err := os.MkdirAll(configDir, 0755); err != nil {
		return fmt.Errorf("failed to create config directory: %w", err)
	}
	
	// Create default config if it doesn't exist
	if err := createDefaultConfig(); err != nil {
		return fmt.Errorf("failed to create default config: %w", err)
	}
	
	// Load configuration
	if err := loadConfig(); err != nil {
		return fmt.Errorf("failed to load config: %w", err)
	}
	
	logger.Info("Configuration initialized successfully")
	return nil
}

func createDefaultConfig() error {
	if _, err := os.Stat(configFile); err == nil {
		// Config file already exists
		return nil
	}
	
	logger.Info("Creating default configuration file")
	
	file, err := os.Create(configFile)
	if err != nil {
		return err
	}
	defer file.Close()
	
	writer := bufio.NewWriter(file)
	
	// Write header
	fmt.Fprintf(writer, "# NaK Configuration\n")
	fmt.Fprintf(writer, "# Created: %s\n", time.Now().Format("2006-01-02 15:04:05"))
	fmt.Fprintf(writer, "\n")
	
	// Write default values
	defaults := map[string]string{
		"logging_level":           "0",
		"show_advanced_options":   "false",
		"check_updates":           "true",
		"enable_telemetry":        "false",
		"preferred_game_appid":    "",
		"default_scaling":         "96",
		"enable_detailed_progress": "true",
		"auto_detect_games":       "true",
		"cache_steam_path":        "true",
	}
	
	for key, value := range defaults {
		fmt.Fprintf(writer, "%s=%s\n", key, value)
	}
	
	return writer.Flush()
}

func loadConfig() error {
	file, err := os.Open(configFile)
	if err != nil {
		return err
	}
	defer file.Close()
	
	config = &Config{}
	scanner := bufio.NewScanner(file)
	
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		
		key := strings.TrimSpace(parts[0])
		value := strings.TrimSpace(parts[1])
		
		switch key {
		case "logging_level":
			config.LoggingLevel = value
		case "show_advanced_options":
			config.ShowAdvancedOptions = value
		case "check_updates":
			config.CheckUpdates = value
		case "enable_telemetry":
			config.EnableTelemetry = value
		case "preferred_game_appid":
			config.PreferredGameAppID = value
		case "default_scaling":
			config.DefaultScaling = value
		case "enable_detailed_progress":
			config.EnableDetailedProgress = value
		case "auto_detect_games":
			config.AutoDetectGames = value
		case "cache_steam_path":
			config.CacheSteamPath = value
		}
	}
	
	return scanner.Err()
}

func Get(key, defaultValue string) string {
	if config == nil {
		return defaultValue
	}
	
	switch key {
	case "logging_level":
		if config.LoggingLevel != "" {
			return config.LoggingLevel
		}
	case "show_advanced_options":
		if config.ShowAdvancedOptions != "" {
			return config.ShowAdvancedOptions
		}
	case "check_updates":
		if config.CheckUpdates != "" {
			return config.CheckUpdates
		}
	case "enable_telemetry":
		if config.EnableTelemetry != "" {
			return config.EnableTelemetry
		}
	case "preferred_game_appid":
		if config.PreferredGameAppID != "" {
			return config.PreferredGameAppID
		}
	case "default_scaling":
		if config.DefaultScaling != "" {
			return config.DefaultScaling
		}
	case "enable_detailed_progress":
		if config.EnableDetailedProgress != "" {
			return config.EnableDetailedProgress
		}
	case "auto_detect_games":
		if config.AutoDetectGames != "" {
			return config.AutoDetectGames
		}
	case "cache_steam_path":
		if config.CacheSteamPath != "" {
			return config.CacheSteamPath
		}
	}
	
	return defaultValue
}

func Set(key, value string) error {
	if config == nil {
		return fmt.Errorf("config not initialized")
	}
	
	// Update in-memory config
	switch key {
	case "logging_level":
		config.LoggingLevel = value
	case "show_advanced_options":
		config.ShowAdvancedOptions = value
	case "check_updates":
		config.CheckUpdates = value
	case "enable_telemetry":
		config.EnableTelemetry = value
	case "preferred_game_appid":
		config.PreferredGameAppID = value
	case "default_scaling":
		config.DefaultScaling = value
	case "enable_detailed_progress":
		config.EnableDetailedProgress = value
	case "auto_detect_games":
		config.AutoDetectGames = value
	case "cache_steam_path":
		config.CacheSteamPath = value
	default:
		return fmt.Errorf("unknown config key: %s", key)
	}
	
	// Write to file
	return writeConfig()
}

func writeConfig() error {
	file, err := os.Create(configFile)
	if err != nil {
		return err
	}
	defer file.Close()
	
	writer := bufio.NewWriter(file)
	
	// Write header
	fmt.Fprintf(writer, "# NaK Configuration\n")
	fmt.Fprintf(writer, "# Updated: %s\n", time.Now().Format("2006-01-02 15:04:05"))
	fmt.Fprintf(writer, "\n")
	
	// Write all config values
	fmt.Fprintf(writer, "logging_level=%s\n", config.LoggingLevel)
	fmt.Fprintf(writer, "show_advanced_options=%s\n", config.ShowAdvancedOptions)
	fmt.Fprintf(writer, "check_updates=%s\n", config.CheckUpdates)
	fmt.Fprintf(writer, "enable_telemetry=%s\n", config.EnableTelemetry)
	fmt.Fprintf(writer, "preferred_game_appid=%s\n", config.PreferredGameAppID)
	fmt.Fprintf(writer, "default_scaling=%s\n", config.DefaultScaling)
	fmt.Fprintf(writer, "enable_detailed_progress=%s\n", config.EnableDetailedProgress)
	fmt.Fprintf(writer, "auto_detect_games=%s\n", config.AutoDetectGames)
	fmt.Fprintf(writer, "cache_steam_path=%s\n", config.CacheSteamPath)
	
	return writer.Flush()
} 