#!/bin/bash

# This script downloads, makes executable, and runs the latest NaK release.
# It requires 'curl' and 'jq' to be installed.

# --- Configuration ---
# The GitHub repository owner and name.
REPO_OWNER="SulfurNitride"
REPO_NAME="NaK"
# The desired name for the executable file.
EXECUTABLE_NAME="nak"

# --- Script Logic ---

# Check for required tools
echo "Checking for required tools: curl and jq..."
if ! command -v curl &> /dev/null
then
    echo "Error: 'curl' could not be found. Please install it."
    exit 1
fi

if ! command -v jq &> /dev/null
then
    echo "Error: 'jq' could not be found. Please install it."
    exit 1
fi
echo "Tools found. Proceeding."

# Construct the API URL for the latest release.
API_URL="https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest"

echo "Fetching latest release information from GitHub API..."
# Fetch the latest release JSON data from the GitHub API.
# The jq command now selects the asset with a name that is exactly "nak".
DOWNLOAD_URL=$(curl -s "$API_URL" | jq -r '.assets[] | select(.name == "nak") | .browser_download_url')

# Check if a download URL was found.
if [ -z "$DOWNLOAD_URL" ]; then
    echo "Error: Could not find a download URL for an asset named 'nak' in the latest release."
    echo "API URL: $API_URL"
    exit 1
fi

echo "Found download URL: $DOWNLOAD_URL"

# Check if the executable already exists and remove it to get a fresh copy.
if [ -f "$EXECUTABLE_NAME" ]; then
    echo "Removing old '$EXECUTABLE_NAME' file..."
    rm "$EXECUTABLE_NAME"
fi

echo "Downloading the asset and renaming it to '$EXECUTABLE_NAME'..."
# Use curl to download the file and save it with the specified executable name.
# -L: Follows redirects.
# -o: Specifies the output filename.
curl -L -o "$EXECUTABLE_NAME" "$DOWNLOAD_URL"

# Check the exit status of the curl command.
if [ $? -ne 0 ]; then
    echo "Error: The download failed."
    exit 1
fi

echo "Download completed successfully."

echo "Making '$EXECUTABLE_NAME' executable..."
# Make the downloaded file executable.
chmod +x "$EXECUTABLE_NAME"

# Check if chmod was successful.
if [ $? -ne 0 ]; then
    echo "Error: Failed to make the file executable."
    exit 1
fi

echo "Running the latest release..."
# Execute the newly downloaded program.
"./$EXECUTABLE_NAME"

