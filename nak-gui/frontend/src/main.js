import './style.css'
import { ScanGames, CheckDependencies, InstallMO2, InstallMO2WithDirectory, LaunchMO2, BrowseForMO2Folder, SelectDirectory, TestInstallMO2, SetupExistingMO2, ConfigureNXMHandler, RemoveNXMHandlers } from '../wailsjs/go/main/App'

// Test if the module is loading
console.log('Main.js loaded successfully');

// Page navigation
window.showPage = function(pageId) {
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    document.getElementById(pageId).classList.add('active');
}

// Scan for games
window.scanGames = async function() {
    const gamesList = document.getElementById('gamesList');
    const gameCount = document.getElementById('gameCount');
    
    gamesList.innerHTML = '<p style="text-align: center; color: #7dd3fc;">Scanning for games...</p>';
    
    try {
        const result = await ScanGames();
        
        if (result.success) {
            gameCount.textContent = result.count;
            
            if (result.games && result.games.length > 0) {
                gamesList.innerHTML = result.games.map(game => `
                    <div class="game-card">
                        <h3>${escapeHtml(game.name)}</h3>
                        <p>${escapeHtml(game.platform)}</p>
                    </div>
                `).join('');
            } else {
                gamesList.innerHTML = '<p style="text-align: center; color: #cbd5e1;">No games found. Make sure Steam or other game launchers are installed.</p>';
            }
        } else {
            gamesList.innerHTML = `<p style="text-align: center; color: #ef4444;">Error: ${escapeHtml(result.error || 'Unknown error')}</p>`;
        }
    } catch (error) {
        gamesList.innerHTML = `<p style="text-align: center; color: #ef4444;">Error: ${escapeHtml(error.message)}</p>`;
    }
}

// Download MO2
window.downloadMO2 = async function() {
    console.log('Download MO2 button clicked');
    
    let installDir;
    try {
        // Show directory selection dialog
        console.log('Opening directory selection dialog...');
        installDir = await SelectDirectory();
        console.log('Directory selection result:', installDir);
        
        if (!installDir) {
            // User cancelled or no directory selected
            console.log('No directory selected, cancelling');
            return;
        }
        
        console.log('Directory selected, proceeding with installation...');
    } catch (error) {
        console.error('Error in directory selection:', error);
        alert('Error opening directory selection dialog: ' + error.message);
        return;
    }
    
    // Navigate to installation progress page
    showPage('installationProgress');
    
    // Initialize the installation progress page
    initializeInstallationProgress(installDir);
}

// Initialize installation progress page
function initializeInstallationProgress(installDir) {
    // Update page elements
    document.getElementById('targetDirectory').textContent = installDir;
    document.getElementById('installationStatus').textContent = 'Starting installation...';
    document.getElementById('installationStatus').style.color = '#fbbf24';
    
    // Reset progress
    updateProgress(0, 'Preparing installation...');
    
    // Clear and initialize terminal
    const terminalOutput = document.getElementById('terminalOutput');
    terminalOutput.innerHTML = `
        <div class="terminal-line">
            <span class="terminal-prompt">$</span>
            <span class="terminal-text">Starting Mod Organizer 2 installation process...</span>
        </div>
        <div class="terminal-line">
            <span class="terminal-prompt">$</span>
            <span class="terminal-text info">Target directory: ${escapeHtml(installDir)}</span>
        </div>
        <div class="terminal-line">
            <span class="terminal-prompt">$</span>
            <span class="terminal-text">Initializing backend connection...</span>
        </div>
    `;
    
    // Show cancel button, hide others
    document.getElementById('cancelButton').style.display = 'inline-block';
    document.getElementById('backButton').style.display = 'none';
    document.getElementById('continueButton').style.display = 'none';
    
    // Start the installation process
    startMO2Installation(installDir);
}

// Start MO2 installation process
async function startMO2Installation(installDir) {
    try {
        addTerminalLine('Connecting to backend...', 'info');
        updateProgress(5, 'Connecting to backend...');
        
        addTerminalLine('Calling InstallMO2WithDirectory...', 'info');
        updateProgress(10, 'Starting installation...');
        
        console.log('About to call InstallMO2WithDirectory with:', installDir);

        // Use the real MO2 installation function
        const result = await InstallMO2WithDirectory(installDir);

        console.log('InstallMO2WithDirectory result:', result);
        
        // Parse the streaming result
        parseStreamingResult(result);
        
    } catch (error) {
        updateProgress(0, 'Installation failed');
        document.getElementById('installationStatus').textContent = 'Installation failed';
        document.getElementById('installationStatus').style.color = '#ef4444';
        
        addTerminalLine(`Error: ${error.message}`, 'error');
        console.error('Installation error:', error);
        
        // Show back button, hide cancel
        document.getElementById('cancelButton').style.display = 'none';
        document.getElementById('backButton').style.display = 'inline-block';
    }
}

// Parse streaming result from backend
function parseStreamingResult(result) {
    const lines = result.trim().split('\n');
    let finalResult = null;
    let progressPercentage = 10;
    
    for (const line of lines) {
        if (line.trim()) {
            // Check if it's a progress line
            if (line.startsWith('PROGRESS: ')) {
                const message = line.substring(10); // Remove 'PROGRESS: ' prefix
                addTerminalLine(message, 'info');
                
                // Update progress bar based on message content
                if (message.includes('Fetching latest')) {
                    progressPercentage = 20;
                } else if (message.includes('Found latest version')) {
                    progressPercentage = 30;
                } else if (message.includes('Downloading')) {
                    progressPercentage = 50;
                } else if (message.includes('Extracting')) {
                    progressPercentage = 60;
                } else if (message.includes('Adding to Steam')) {
                    progressPercentage = 70;
                } else if (message.includes('Creating prefix')) {
                    progressPercentage = 80;
                } else if (message.includes('Installing dependencies')) {
                    progressPercentage = 90;
                }
                
                updateProgress(progressPercentage, message);
                
            } else {
                // Try to parse as JSON (final result)
                try {
                    const data = JSON.parse(line);
                    if (data.success !== undefined) {
                        finalResult = data;
                    }
                } catch (parseError) {
                    // If it's not JSON, treat as regular output
                    addTerminalLine(line, '');
                }
            }
        }
    }
    
    // Process final result
    if (finalResult) {
        addTerminalLine('Backend execution completed', 'success');
        updateProgress(95, 'Processing results...');
        
        if (finalResult.success) {
            updateProgress(100, 'Installation complete!');
            document.getElementById('installationStatus').textContent = 'Installation successful';
            document.getElementById('installationStatus').style.color = '#10b981';
            
            addTerminalLine(`Installation completed successfully!`, 'success');
            
            if (finalResult.message) {
                addTerminalLine(`Message: ${finalResult.message}`, 'success');
            }
            if (finalResult.install_dir) {
                addTerminalLine(`Installed to: ${finalResult.install_dir}`, 'info');
            }
            if (finalResult.app_id) {
                addTerminalLine(`Steam AppID: ${finalResult.app_id}`, 'info');
            }
            if (finalResult.version) {
                addTerminalLine(`MO2 Version: ${finalResult.version}`, 'info');
            }
            
            // Show continue button, hide cancel
            document.getElementById('cancelButton').style.display = 'none';
            document.getElementById('continueButton').style.display = 'inline-block';
            
        } else {
            updateProgress(0, 'Installation failed');
            document.getElementById('installationStatus').textContent = 'Installation failed';
            document.getElementById('installationStatus').style.color = '#ef4444';
            
            addTerminalLine(`Installation failed: ${finalResult.error || 'Unknown error occurred'}`, 'error');
            
            // Show back button, hide cancel
            document.getElementById('cancelButton').style.display = 'none';
            document.getElementById('backButton').style.display = 'inline-block';
        }
    } else {
        // Fallback: treat the entire result as a simple response
        updateProgress(100, 'Installation complete!');
        document.getElementById('installationStatus').textContent = 'Installation completed';
        document.getElementById('installationStatus').style.color = '#10b981';
        
        addTerminalLine(`Installation completed: ${result}`, 'success');
        
        // Show continue button, hide cancel
        document.getElementById('cancelButton').style.display = 'none';
        document.getElementById('continueButton').style.display = 'inline-block';
    }
}

// Update progress bar and text
function updateProgress(percentage, step) {
    const progressBar = document.getElementById('installationProgressBar');
    const progressPercentage = document.getElementById('progressPercentage');
    const progressStep = document.getElementById('progressStep');
    
    progressBar.style.width = `${percentage}%`;
    progressPercentage.textContent = `${percentage}%`;
    progressStep.textContent = step;
}

// Add a line to the terminal output
function addTerminalLine(text, type = '') {
    const terminalOutput = document.getElementById('terminalOutput');
    const line = document.createElement('div');
    line.className = 'terminal-line';
    
    const prompt = document.createElement('span');
    prompt.className = 'terminal-prompt';
    prompt.textContent = '$';
    
    const textSpan = document.createElement('span');
    textSpan.className = `terminal-text ${type}`;
    textSpan.textContent = text;
    
    line.appendChild(prompt);
    line.appendChild(textSpan);
    terminalOutput.appendChild(line);
    
    // Auto-scroll to bottom
    terminalOutput.scrollTop = terminalOutput.scrollHeight;
}

// Cancel installation (placeholder)
window.cancelInstallation = function() {
    addTerminalLine('Installation cancelled by user', 'warning');
    document.getElementById('installationStatus').textContent = 'Installation cancelled';
    document.getElementById('installationStatus').style.color = '#fbbf24';
    
    // Show back button, hide cancel
    document.getElementById('cancelButton').style.display = 'none';
    document.getElementById('backButton').style.display = 'inline-block';
}

// Install dependencies
window.installDependencies = async function() {
    const progressSection = document.getElementById('progressSection');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const progressLog = document.getElementById('progressLog');
    const progressTitle = document.getElementById('progressTitle');
    
    progressTitle.textContent = 'Installing MO2 Dependencies';
    progressSection.style.display = 'block';
    progressBar.style.width = '0%';
    progressText.textContent = '0% - Checking dependencies...';
    progressLog.innerHTML = '<div>Checking system dependencies...</div>';
    
    try {
        const result = await CheckDependencies();
        
        if (result.success) {
            progressLog.innerHTML += '<div>[INFO] Dependencies checked:</div>';
            
            for (const [name, info] of Object.entries(result.dependencies)) {
                const status = info.installed ? '✓' : '✗';
                const color = info.installed ? '#10b981' : '#ef4444';
                progressLog.innerHTML += `<div style="color: ${color};">[${status}] ${name}: ${info.status}</div>`;
            }
            
            progressLog.scrollTop = progressLog.scrollHeight;
            
            // Simulate installation progress
            let progress = 0;
            const interval = setInterval(() => {
                progress += 5;
                if (progress <= 100) {
                    progressBar.style.width = progress + '%';
                    progressText.textContent = `${progress}% - Installing dependencies...`;
                } else {
                    clearInterval(interval);
                    progressText.textContent = '100% - Dependencies check complete!';
                }
            }, 200);
        } else {
            progressLog.innerHTML += `<div style="color: #ef4444;">[ERROR] ${escapeHtml(result.error)}</div>`;
        }
    } catch (error) {
        progressLog.innerHTML += `<div style="color: #ef4444;">[ERROR] ${escapeHtml(error.message)}</div>`;
        progressLog.scrollTop = progressLog.scrollHeight;
    }
}

// Utility function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Browse for MO2 folder
window.browseMO2Folder = async function() {
    try {
        const result = await BrowseForMO2Folder();
        const data = JSON.parse(result);
        
        if (data.success && data.path) {
            // Show the selected path
            document.getElementById('selectedPathDisplay').textContent = data.path;
            document.getElementById('mo2SelectedPath').style.display = 'block';
            
            // Store the path for later use
            window.selectedMO2Path = data.path;
            
            // Set default name based on folder name
            const folderName = data.path.split('/').pop();
            document.getElementById('mo2InstallationName').value = folderName || 'Mod Organizer 2';
        } else {
            console.log('No folder selected or error:', data.error);
        }
    } catch (error) {
        alert(`Error browsing for folder: ${error.message}`);
    }
}

// Confirm MO2 setup
window.confirmMO2Setup = function() {
    if (window.selectedMO2Path) {
        // Get the custom name
        const customName = document.getElementById('mo2InstallationName').value.trim() || 'Mod Organizer 2';
        
        // Navigate to installation progress page
        showPage('installationProgress');
        
        // Initialize the installation progress page for existing MO2
        initializeExistingMO2Setup(window.selectedMO2Path, customName);
    }
}

// Initialize existing MO2 setup progress page
function initializeExistingMO2Setup(mo2Path, customName) {
    // Update page elements
    document.getElementById('targetDirectory').textContent = mo2Path;
    document.getElementById('installationStatus').textContent = 'Setting up existing MO2 installation...';
    document.getElementById('installationStatus').style.color = '#fbbf24';
    
    // Reset progress
    updateProgress(0, 'Preparing setup...');
    
    // Clear and initialize terminal
    const terminalOutput = document.getElementById('terminalOutput');
    terminalOutput.innerHTML = `
        <div class="terminal-line">
            <span class="terminal-prompt">$</span>
            <span class="terminal-text">Setting up existing Mod Organizer 2 installation...</span>
        </div>
        <div class="terminal-line">
            <span class="terminal-prompt">$</span>
            <span class="terminal-text info">Target directory: ${escapeHtml(mo2Path)}</span>
        </div>
        <div class="terminal-line">
            <span class="terminal-prompt">$</span>
            <span class="terminal-text info">Custom name: ${escapeHtml(customName)}</span>
        </div>
        <div class="terminal-line">
            <span class="terminal-prompt">$</span>
            <span class="terminal-text">Initializing backend connection...</span>
        </div>
    `;
    
    // Show cancel button, hide others
    document.getElementById('cancelButton').style.display = 'inline-block';
    document.getElementById('backButton').style.display = 'none';
    document.getElementById('continueButton').style.display = 'none';
    
    // Start the setup process
    startExistingMO2Setup(mo2Path, customName);
}

// Start existing MO2 setup process
async function startExistingMO2Setup(mo2Path, customName) {
    try {
        addTerminalLine('Connecting to backend...', 'info');
        updateProgress(5, 'Connecting to backend...');
        
        addTerminalLine('Calling SetupExistingMO2...', 'info');
        updateProgress(10, 'Setting up existing installation...');
        
        console.log('About to call SetupExistingMO2 with:', mo2Path, customName);

        // Use the setup existing MO2 function
        const result = await SetupExistingMO2(mo2Path, customName);

        console.log('SetupExistingMO2 result:', result);
        
        // Parse the result
        parseStreamingResult(result);
        
    } catch (error) {
        updateProgress(0, 'Setup failed');
        document.getElementById('installationStatus').textContent = 'Setup failed';
        document.getElementById('installationStatus').style.color = '#ef4444';
        
        addTerminalLine(`Error: ${error.message}`, 'error');
        console.error('Setup error:', error);
        
        // Show back button, hide cancel
        document.getElementById('cancelButton').style.display = 'none';
        document.getElementById('backButton').style.display = 'inline-block';
    }
}

// Check dependencies on startup
// Setup NXM Handler
window.setupNXMHandler = async function() {
    console.log('Setup NXM Handler clicked');
    
    try {
        // First, get the list of non-Steam games to show the user
        console.log('Calling ScanGames()...');
        const gamesResult = await ScanGames();
        console.log('ScanGames() returned:', gamesResult);
        console.log('ScanGames() type:', typeof gamesResult);
        console.log('ScanGames() success:', gamesResult.success);
        console.log('ScanGames() count:', gamesResult.count);
        console.log('ScanGames() games:', gamesResult.games);
        
        if (!gamesResult.success || !gamesResult.games || gamesResult.games.length === 0) {
            console.log('No games found, showing alert');
            alert(`No non-Steam games found. Please add some games to Steam first.\n\nDebug:\nsuccess: ${gamesResult.success}\ncount: ${gamesResult.count}\ngames: ${JSON.stringify(gamesResult.games)}\nerror: ${gamesResult.error}`);
            return;
        }
        
        // Show the NXM handler setup page
        showPage('nxmHandlerSetup');
        initializeNXMHandlerSetup(gamesResult.games);
        
    } catch (error) {
        console.error('NXM Handler setup error:', error);
        alert('Error setting up NXM handler: ' + error.message);
    }
}

// Initialize NXM Handler Setup
function initializeNXMHandlerSetup(games) {
    console.log('Initializing NXM handler setup with games:', games);
    
    // Update the games list
    const gamesList = document.getElementById('nxmGamesList');
    if (gamesList) {
        gamesList.innerHTML = games.map(game => `
            <div class="game-card" onclick="selectGameForNXM('${game.app_id}', '${escapeHtml(game.name)}')">
                <h3>${escapeHtml(game.name)}</h3>
                <p>AppID: ${game.app_id}</p>
            </div>
        `).join('');
    }
}

// Select game for NXM handler
window.selectGameForNXM = async function(appId, gameName) {
    console.log('Selected game for NXM handler:', appId, gameName);
    
    // Store the selected game
    window.selectedGameForNXM = { appId, gameName };
    
    // Show the NXM handler path selection
    document.getElementById('selectedGameInfo').innerHTML = `
        <div class="selected-game">
            <h3>Selected Game: ${escapeHtml(gameName)}</h3>
            <p>AppID: ${appId}</p>
        </div>
    `;
    document.getElementById('selectedGameInfo').style.display = 'block';
    document.getElementById('nxmHandlerPathSection').style.display = 'block';
}

window.browseForNXMHandler = async function() {
    console.log('Browse for NXM Handler clicked');
    
    try {
        const folderPath = await SelectDirectory();
        console.log('Selected MO2 folder:', folderPath);
        
        if (folderPath) {
            // Store the FOLDER PATH for the backend (backend will auto-detect nxmhandler.exe)
            window.selectedNXMHandlerPath = folderPath;
            
            // Display the folder path (backend will find nxmhandler.exe automatically)
            document.getElementById('nxmHandlerPath').value = folderPath;
            
            // Show the configure button
            document.getElementById('configureNXMButton').style.display = 'inline-block';
        }
    } catch (error) {
        console.error('Error browsing for NXM handler:', error);
        alert('Error selecting directory: ' + error.message);
    }
}

// Configure NXM Handler
window.configureNXMHandler = async function() {
    console.log('Configure NXM Handler clicked');
    
    if (!window.selectedGameForNXM) {
        alert('Please select a game first.');
        return;
    }
    
    const nxmHandlerPath = window.selectedNXMHandlerPath || document.getElementById('nxmHandlerPath').value.trim();
    if (!nxmHandlerPath) {
        alert('Please browse and select the MO2 folder first.');
        return;
    }
    
    try {
        console.log('Configuring NXM handler for:', window.selectedGameForNXM.appId, nxmHandlerPath);
        
        const result = await ConfigureNXMHandler(window.selectedGameForNXM.appId, nxmHandlerPath);
        console.log('NXM Handler configuration result:', result);
        
        const data = JSON.parse(result);
        if (data.success) {
            alert(`NXM handler configured successfully!\n\nGame: ${window.selectedGameForNXM.gameName}\nAppID: ${window.selectedGameForNXM.appId}\nPath: ${nxmHandlerPath}\nMessage: ${data.message}`);
            showPage('mo2Setup'); // Go back to main MO2 setup page
        } else {
            alert('Failed to configure NXM handler: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('NXM Handler configuration error:', error);
        alert('Error configuring NXM handler: ' + error.message);
    }
}

// Remove NXM Handlers
window.removeNXMHandlers = async function() {
    console.log('Remove NXM Handlers clicked');
    
    if (!confirm('Are you sure you want to remove all NXM handlers? This will disable NXM link support.')) {
        return;
    }
    
    try {
        const result = await RemoveNXMHandlers();
        console.log('Remove NXM Handlers result:', result);
        
        const data = JSON.parse(result);
        if (data.success) {
            alert('NXM handlers removed successfully!');
        } else {
            alert('Failed to remove NXM handlers: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Remove NXM Handlers error:', error);
        alert('Error removing NXM handlers: ' + error.message);
    }
}

window.addEventListener('DOMContentLoaded', async () => {
    try {
        const result = await CheckDependencies();
        console.log('Startup dependency check:', result);
    } catch (error) {
        console.error('Failed to check dependencies on startup:', error);
    }
});
