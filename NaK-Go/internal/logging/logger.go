package logging

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"
)

type LogLevel int

const (
	LevelInfo LogLevel = iota
	LevelWarning
	LevelError
)

type Logger struct {
	level LogLevel
}

var (
	logger  *Logger
	logFile *os.File
)

func Init() {
	// Create log directory
	logDir := filepath.Join(os.Getenv("HOME"), ".config", "nak")
	if err := os.MkdirAll(logDir, 0755); err != nil {
		log.Printf("Failed to create log directory: %v", err)
		return
	}

	// Open log file
	logPath := filepath.Join(logDir, "nak.log")
	file, err := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		log.Printf("Failed to open log file: %v", err)
		return
	}

	logFile = file
	logger = &Logger{level: LevelInfo}
}

func GetLogger() *Logger {
	if logger == nil {
		logger = &Logger{level: LevelInfo}
	}
	return logger
}

func (l *Logger) Info(message string) {
	l.log(LevelInfo, "INFO", message)
}

func (l *Logger) Warning(message string) {
	l.log(LevelWarning, "WARNING", message)
}

func (l *Logger) Error(message string) {
	l.log(LevelError, "ERROR", message)
}

func (l *Logger) log(level LogLevel, levelStr, message string) {
	if level < l.level {
		return
	}

	timestamp := time.Now().Format("2006-01-02 15:04:05")
	logMessage := fmt.Sprintf("[%s] %s: %s", timestamp, levelStr, message)

	// Write to log file if available
	if logFile != nil {
		fmt.Fprintln(logFile, logMessage)
		// Force flush to ensure immediate writing
		logFile.Sync()
	}

	// Only print to console for warnings and errors by default
	if level >= LevelWarning {
		fmt.Println(logMessage)
	}
}

func (l *Logger) SetLevel(level LogLevel) {
	l.level = level
}

func Close() {
	if logFile != nil {
		logFile.Close()
	}
}
