#!/bin/sh
# Simple wrapper for NaK installer that ensures it runs with bash
# Save this as install-nak.sh and make executable with: chmod +x install-nak.sh

# Download the installer to a temporary file
TMP_FILE=$(mktemp)
curl -s https://raw.githubusercontent.com/SulfurNitride/NaK/refs/heads/main/nak-installer.sh > $TMP_FILE

# Run it with bash explicitly
bash $TMP_FILE

# Clean up
rm $TMP_FILE

exit $?
