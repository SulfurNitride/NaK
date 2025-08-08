package ui

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/chzyer/readline"
	"github.com/fatih/color"
	"github.com/manifoldco/promptui"
	"golang.org/x/term"
)

type MenuItem struct {
	ID          int
	Title       string
	Description string
	Action      func() error
}

type Menu struct {
	Title    string
	Items    []MenuItem
	ExitText string
}

var (
	// Color functions
	Red    = color.New(color.FgRed).SprintFunc()
	Green  = color.New(color.FgGreen).SprintFunc()
	Yellow = color.New(color.FgYellow).SprintFunc()
	Blue   = color.New(color.FgBlue).SprintFunc()
	Cyan   = color.New(color.FgCyan).SprintFunc()
	White  = color.New(color.FgWhite).SprintFunc()
	Bold   = color.New(color.Bold).SprintFunc()
)

func PrintHeader(version, date string) {
	ClearScreen()
	fmt.Println()

	// Calculate center alignment
	title := "NaK - Linux Modding Helper"
	versionLine := fmt.Sprintf("Version: %s | Date: %s", version, date)
	repoLine := "Project repository: https://github.com/SulfurNitride/NaK"

	// Get terminal width (default to 80 if we can't determine)
	width := 80
	if w, _, err := term.GetSize(int(os.Stdout.Fd())); err == nil {
		width = w
	}

	// Create centered box
	boxWidth := 70
	if boxWidth > width-4 {
		boxWidth = width - 4
	}

	// Top border
	fmt.Println(Cyan("┌" + strings.Repeat("─", boxWidth) + "┐"))

	// Title line (centered)
	titlePadding := (boxWidth - len(title)) / 2
	if titlePadding < 0 {
		titlePadding = 0
	}
	fmt.Println(Cyan("│") + strings.Repeat(" ", titlePadding) + Bold(title) + strings.Repeat(" ", boxWidth-len(title)-titlePadding) + Cyan("│"))

	// Empty line
	fmt.Println(Cyan("│") + strings.Repeat(" ", boxWidth) + Cyan("│"))

	// Version line (centered)
	versionPadding := (boxWidth - len(versionLine)) / 2
	if versionPadding < 0 {
		versionPadding = 0
	}
	fmt.Println(Cyan("│") + strings.Repeat(" ", versionPadding) + versionLine + strings.Repeat(" ", boxWidth-len(versionLine)-versionPadding) + Cyan("│"))

	// Repository line (centered)
	repoPadding := (boxWidth - len(repoLine)) / 2
	if repoPadding < 0 {
		repoPadding = 0
	}
	fmt.Println(Cyan("│") + strings.Repeat(" ", repoPadding) + repoLine + strings.Repeat(" ", boxWidth-len(repoLine)-repoPadding) + Cyan("│"))

	// Bottom border
	fmt.Println(Cyan("└" + strings.Repeat("─", boxWidth) + "┘"))
	fmt.Println()
}

func PrintSection(title string) {
	fmt.Println()
	fmt.Println(Bold(Cyan("=== " + title + " ===")))
	fmt.Println()
}

func PrintInfo(message string) {
	fmt.Println(Blue("ℹ ") + message)
}

func PrintSuccess(message string) {
	fmt.Println(Green("✓ ") + message)
}

func PrintWarning(message string) {
	fmt.Println(Yellow("⚠ ") + message)
}

func PrintError(message string) {
	fmt.Println(Red("✗ ") + message)
}

func DisplayMenu(menu Menu) (int, error) {
	for {
		fmt.Println()

		// Don't display the menu title to avoid the "Main Menu" text
		// The menu items are self-explanatory

		// Create prompt items
		var items []string
		for i, item := range menu.Items {
			items = append(items, fmt.Sprintf("%d. %s - %s", i+1, item.Title, item.Description))
		}

		if menu.ExitText != "" {
			items = append(items, fmt.Sprintf("%d. %s", len(menu.Items)+1, menu.ExitText))
		}

		// Use a simple prompt instead of promptui to avoid help text issues
		fmt.Println("Select an option:")
		for _, item := range items {
			fmt.Printf("  %s\n", item)
		}
		fmt.Println()

		// Get user input
		input, err := GetInput("Enter your choice (1-"+strconv.Itoa(len(items))+")", "")
		if err != nil {
			return -1, err
		}

		// Handle empty input gracefully
		if strings.TrimSpace(input) == "" {
			fmt.Println("Please enter a valid choice.")
			continue
		}

		choice, err := strconv.Atoi(input)
		if err != nil {
			fmt.Printf("Invalid choice '%s'. Please enter a number between 1 and %d.\n", input, len(items))
			continue
		}

		if choice < 1 || choice > len(items) {
			fmt.Printf("Choice %d is out of range. Please enter a number between 1 and %d.\n", choice, len(items))
			continue
		}

		return choice, nil
	}
}

func ConfirmAction(message string) (bool, error) {
	prompt := promptui.Prompt{
		Label: message + " (y/N)",
		Validate: func(input string) error {
			input = strings.ToLower(strings.TrimSpace(input))
			if input == "" || input == "n" || input == "no" || input == "y" || input == "yes" {
				return nil
			}
			return fmt.Errorf("please enter y/yes or n/no")
		},
	}

	result, err := prompt.Run()
	if err != nil {
		return false, err
	}

	input := strings.ToLower(strings.TrimSpace(result))
	return input == "y" || input == "yes", nil
}

func GetInput(prompt string, defaultVal string) (string, error) {
	p := promptui.Prompt{
		Label:     prompt,
		AllowEdit: true,
		Validate: func(input string) error {
			// Allow empty input for optional fields
			return nil
		},
	}

	if defaultVal != "" {
		p.Default = defaultVal
	}

	return p.Run()
}

// GetInputWithTabCompletion provides input with tab completion for file paths
func GetInputWithTabCompletion(prompt string, defaultVal string) (string, error) {
	// Create readline instance with conservative tab completion
	rl, err := readline.NewEx(&readline.Config{
		Prompt:          prompt + " ",
		HistoryFile:     "/tmp/nak.tmp",
		AutoComplete:    getConservativeCompleter(),
		InterruptPrompt: "^C",
		EOFPrompt:       "exit",
	})
	if err != nil {
		return "", err
	}
	defer rl.Close()

	// Show instructions
	fmt.Println("Tip: Use Tab for path completion, ~ for home directory (e.g., ~/Games/MO2)")

	// Set default value if provided
	if defaultVal != "" {
		rl.SetPrompt(prompt + " [" + defaultVal + "] ")
	}

	line, err := rl.Readline()
	if err != nil {
		return "", err
	}

	// Use default if empty
	if line == "" && defaultVal != "" {
		return defaultVal, nil
	}

	return line, nil
}

// getConservativeCompleter creates a conservative tab completion function
func getConservativeCompleter() readline.AutoCompleter {
	return &conservativeCompleter{}
}

// conservativeCompleter implements conservative file path completion
type conservativeCompleter struct{}

func (c *conservativeCompleter) Do(line []rune, pos int) (newLine [][]rune, length int) {
	// Convert runes to string
	input := string(line[:pos])

	// Find the last word (the part we want to complete)
	words := strings.Fields(input)
	if len(words) == 0 {
		return [][]rune{}, 0
	}

	lastWord := words[len(words)-1]

	// Handle special cases
	if lastWord == "~" {
		// Complete home directory
		homeDir, err := os.UserHomeDir()
		if err == nil {
			return [][]rune{[]rune(input + homeDir[1:])}, len(homeDir) - 1
		}
		return [][]rune{}, 0
	}

	// Handle absolute paths properly
	if strings.HasPrefix(lastWord, "/") {
		// For absolute paths, we need to handle the path differently
		pathParts := strings.Split(lastWord, "/")
		if len(pathParts) < 2 {
			return [][]rune{}, 0
		}

		// Reconstruct the directory path (everything except the last part)
		dirPath := strings.Join(pathParts[:len(pathParts)-1], "/")
		if dirPath == "" {
			dirPath = "/"
		}

		prefix := pathParts[len(pathParts)-1]

		// Read directory contents
		files, err := os.ReadDir(dirPath)
		if err != nil {
			return [][]rune{}, 0
		}

		// Find matching files/directories (case-insensitive)
		var matches []string
		for _, file := range files {
			name := file.Name()
			if strings.HasPrefix(strings.ToLower(name), strings.ToLower(prefix)) {
				matches = append(matches, name)
			}
		}

		if len(matches) == 0 {
			return [][]rune{}, 0
		}

		// Find the common prefix of all matches
		commonPrefix := findCommonPrefix(matches)
		if commonPrefix == "" || commonPrefix == prefix {
			// No common prefix or same as current prefix, show all matches
			fmt.Println("\nPossible completions:")
			for _, match := range matches {
				fmt.Printf("  %s\n", match)
			}
			return [][]rune{}, 0
		}

		// Replace the last word with the completed path
		// Find the position of the last word in the input
		lastWordStart := strings.LastIndex(input, lastWord)
		if lastWordStart == -1 {
			return [][]rune{}, 0
		}

		// For absolute paths, we need to be more careful about the replacement
		// The issue is that readline might be appending instead of replacing
		// Let's try a different approach - return just the completion part

		// Calculate what should be added to complete the current word
		completionSuffix := strings.TrimPrefix(commonPrefix, prefix)
		if completionSuffix == "" {
			// No completion possible, show options
			fmt.Println("\nPossible completions:")
			for _, match := range matches {
				fmt.Printf("  %s\n", match)
			}
			return [][]rune{}, 0
		}

		// Return just the suffix that should be added
		// If there's only one match and it's a directory, add trailing slash
		if len(matches) == 1 {
			matchPath := filepath.Join(dirPath, matches[0])
			if info, err := os.Stat(matchPath); err == nil && info.IsDir() {
				completionSuffix += "/"
			}
		}

		return [][]rune{[]rune(completionSuffix)}, len(completionSuffix)
	}

	// Handle relative paths (existing logic)
	dir, prefix := filepath.Split(lastWord)
	if dir == "" {
		dir = "."
	}

	// Expand ~ to home directory
	if strings.HasPrefix(dir, "~") {
		homeDir, err := os.UserHomeDir()
		if err == nil {
			dir = filepath.Join(homeDir, dir[1:])
		}
	}

	// Read directory contents
	files, err := os.ReadDir(dir)
	if err != nil {
		return [][]rune{}, 0
	}

	// Find matching files/directories (case-insensitive)
	var matches []string
	for _, file := range files {
		name := file.Name()
		if strings.HasPrefix(strings.ToLower(name), strings.ToLower(prefix)) {
			matches = append(matches, name)
		}
	}

	if len(matches) == 0 {
		return [][]rune{}, 0
	}

	// Find the common prefix of all matches
	commonPrefix := findCommonPrefix(matches)
	if commonPrefix == "" || commonPrefix == prefix {
		// No common prefix or same as current prefix, show all matches
		fmt.Println("\nPossible completions:")
		for _, match := range matches {
			fmt.Printf("  %s\n", match)
		}
		return [][]rune{}, 0
	}

	// Complete to the common prefix
	newInput := strings.TrimSuffix(input, lastWord) + commonPrefix

	// If there's only one match and it's a directory, add trailing slash
	if len(matches) == 1 {
		matchPath := filepath.Join(dir, matches[0])
		if info, err := os.Stat(matchPath); err == nil && info.IsDir() {
			newInput += "/"
		}
	}

	return [][]rune{[]rune(newInput)}, len(commonPrefix)
}

// findCommonPrefix finds the common prefix of a list of strings
func findCommonPrefix(strs []string) string {
	if len(strs) == 0 {
		return ""
	}

	prefix := strs[0]
	for _, str := range strs[1:] {
		prefix = commonPrefix(prefix, str)
		if prefix == "" {
			break
		}
	}

	return prefix
}

// commonPrefix finds the common prefix of two strings
func commonPrefix(a, b string) string {
	minLen := len(a)
	if len(b) < minLen {
		minLen = len(b)
	}

	for i := 0; i < minLen; i++ {
		if a[i] != b[i] {
			return a[:i]
		}
	}

	return a[:minLen]
}

// getCompleter creates a tab completion function for file paths
func getCompleter() readline.AutoCompleter {
	return &filePathCompleter{}
}

// filePathCompleter implements readline.AutoCompleter for file path completion
type filePathCompleter struct{}

func (f *filePathCompleter) Do(line []rune, pos int) (newLine [][]rune, length int) {
	// Convert runes to string
	input := string(line[:pos])

	// Find the last word (the part we want to complete)
	words := strings.Fields(input)
	if len(words) == 0 {
		return [][]rune{}, 0
	}

	lastWord := words[len(words)-1]

	// Handle special cases
	if lastWord == "~" {
		// Complete home directory
		homeDir, err := os.UserHomeDir()
		if err == nil {
			return [][]rune{[]rune(input + homeDir[1:])}, len(homeDir) - 1
		}
		return [][]rune{}, 0
	}

	// Get directory and prefix for file completion
	dir, prefix := filepath.Split(lastWord)
	if dir == "" {
		dir = "."
	}

	// Expand ~ to home directory
	if strings.HasPrefix(dir, "~") {
		homeDir, err := os.UserHomeDir()
		if err == nil {
			dir = filepath.Join(homeDir, dir[1:])
		}
	}

	// Read directory contents
	files, err := os.ReadDir(dir)
	if err != nil {
		return [][]rune{}, 0
	}

	// Find matching files/directories
	var matches []string
	for _, file := range files {
		name := file.Name()
		if strings.HasPrefix(strings.ToLower(name), strings.ToLower(prefix)) {
			matches = append(matches, name)
		}
	}

	if len(matches) == 0 {
		return [][]rune{}, 0
	}

	if len(matches) == 1 {
		// Single match - complete it
		completion := matches[0]

		// Only add slash for directories that actually exist
		fullPath := filepath.Join(dir, completion)
		if info, err := os.Stat(fullPath); err == nil && info.IsDir() {
			completion += "/"
		}

		// Replace the last word with the completion
		newInput := strings.TrimSuffix(input, lastWord) + completion
		return [][]rune{[]rune(newInput)}, len(completion)
	}

	// Multiple matches - show them
	fmt.Println("\nPossible completions:")
	for _, match := range matches {
		fmt.Printf("  %s\n", match)
	}

	return [][]rune{}, 0
}

func GetInputWithValidation(prompt string, validate func(string) error) (string, error) {
	p := promptui.Prompt{
		Label:    prompt,
		Validate: validate,
	}

	return p.Run()
}

func Pause(message string) {
	fmt.Println()
	fmt.Print(message)
	fmt.Scanln() // Wait for Enter key
}

func ClearScreen() {
	// Clear screen and move cursor to top-left
	fmt.Print("\033[H\033[2J")

	// Also try to clear scrollback buffer on some terminals
	fmt.Print("\033[3J")
}

func ClearScreenAndShowHeader(version, date string) {
	ClearScreen()
	PrintHeader(version, date)
}

func PrintProgressBar(current, total int, message string) {
	width := 50
	progress := float64(current) / float64(total)
	filled := int(float64(width) * progress)

	bar := strings.Repeat("█", filled) + strings.Repeat("░", width-filled)
	percentage := int(progress * 100)

	fmt.Printf("\r%s [%s] %d%%", message, bar, percentage)

	if current == total {
		fmt.Println()
	}
}

func PrintTable(headers []string, rows [][]string) {
	// Calculate column widths
	widths := make([]int, len(headers))
	for i, header := range headers {
		widths[i] = len(header)
	}

	for _, row := range rows {
		for i, cell := range row {
			if i < len(widths) && len(cell) > widths[i] {
				widths[i] = len(cell)
			}
		}
	}

	// Print header
	fmt.Print("│ ")
	for i, header := range headers {
		fmt.Printf("%-*s │ ", widths[i], header)
	}
	fmt.Println()

	// Print separator
	fmt.Print("├─")
	for i, width := range widths {
		fmt.Print(strings.Repeat("─", width))
		if i < len(widths)-1 {
			fmt.Print("─┼─")
		}
	}
	fmt.Println("─┤")

	// Print rows
	for _, row := range rows {
		fmt.Print("│ ")
		for i, cell := range row {
			if i < len(widths) {
				fmt.Printf("%-*s │ ", widths[i], cell)
			}
		}
		fmt.Println()
	}
}

func ValidatePath(input string) error {
	if input == "" {
		return fmt.Errorf("path cannot be empty")
	}

	if _, err := os.Stat(input); os.IsNotExist(err) {
		return fmt.Errorf("path does not exist: %s", input)
	}

	return nil
}

func ValidateNumber(input string) error {
	if input == "" {
		return fmt.Errorf("value cannot be empty")
	}

	if _, err := strconv.Atoi(input); err != nil {
		return fmt.Errorf("must be a valid number")
	}

	return nil
}

// PrintCommand prints a command example with special formatting
func PrintCommand(command string) {
	fmt.Printf("%s\n", Blue(command))
}
