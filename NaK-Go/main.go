package main

import (
	"embed"
	"fmt"
	"os"

	"github.com/sulfurnitride/nak/internal/app"
	"github.com/sulfurnitride/nak/internal/logging"
	"github.com/sulfurnitride/nak/internal/utils"
)

const (
	Version = "2.0.3"
	Date    = "2025-08-22"
)

//go:embed portable_stl
var embeddedSTL embed.FS

//go:embed internal/utils/wine_settings.reg
var embeddedWineSettings embed.FS

func main() {
	// Initialize logging
	logging.Init()
	logger := logging.GetLogger()
	logger.Info("Starting NaK - Linux Modding Helper")

	// Create and run the application
	application := app.NewApp(Version, Date)

	// Set the embedded STL for the app and utils to use
	application.SetEmbeddedSTL(embeddedSTL)
	utils.SetEmbeddedSTL(embeddedSTL)
	utils.SetEmbeddedWineSettings(embeddedWineSettings)

	if err := application.Run(); err != nil {
		logger.Error("Application error: " + err.Error())
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	// Close logging when done
	logging.Close()
}
