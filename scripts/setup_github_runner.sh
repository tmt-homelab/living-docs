#!/bin/bash
# GitHub Actions Runner Setup Script for dockp04
# This script sets up a self-hosted GitHub Actions runner for living-docs repo
#
# Usage: ./setup_github_runner.sh
#
# Prerequisites:
# - SSH access to dockp04
# - GitHub PAT with repo scope (or use OAuth)
# - Docker installed (optional, for containerized runner)

set -e

RUNNER_DIR="$HOME/actions-runner"
RUNNER_NAME="dockp04-runner"
REPO_URL="https://github.com/tmt-homelab/living-docs"

echo "=== GitHub Actions Runner Setup ==="
echo "Repository: $REPO_URL"
echo "Runner name: $RUNNER_NAME"
echo "Runner directory: $RUNNER_DIR"
echo ""

# Step 1: Check if runner already exists
if [ -d "$RUNNER_DIR/.runner" ]; then
    echo "Runner already configured at $RUNNER_DIR"
    echo "Do you want to:"
    echo "  1) Restart existing runner"
    echo "  2) Reconfigure runner"
    echo "  3) Remove and setup new runner"
    read -p "Choose option [1-3]: " option
    
    case $option in
        1)
            echo "Restarting runner..."
            cd $RUNNER_DIR
            ./svc.sh restart || ./run.sh &
            exit 0
            ;;
        2)
            echo "Reconfiguring runner..."
            cd $RUNNER_DIR
            ./config.sh remove --token "$(cat .token 2>/dev/null || echo '')"
            ;;
        3)
            echo "Removing existing runner..."
            cd $RUNNER_DIR
            ./config.sh remove --unattended
            rm -rf $RUNNER_DIR
            ;;
        *)
            echo "Invalid option"
            exit 1
            ;;
    esac
fi

# Step 2: Get registration token
echo ""
echo "Getting registration token from GitHub..."
echo "You can get this from:"
echo "  https://github.com/tmt-homelab/living-docs/settings/actions/runners"
echo ""
read -p "Enter registration token: " RUNNER_TOKEN

if [ -z "$RUNNER_TOKEN" ]; then
    echo "ERROR: Token is required"
    exit 1
fi

# Step 3: Create runner directory
echo ""
echo "Creating runner directory..."
mkdir -p $RUNNER_DIR
cd $RUNNER_DIR

# Step 4: Download runner
RUNNER_VERSION="2.310.0"
RUNNER_FILE="actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
RUNNER_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${RUNNER_FILE}"

echo "Downloading runner version ${RUNNER_VERSION}..."
if [ ! -f "$RUNNER_FILE" ]; then
    curl -o $RUNNER_FILE -L $RUNNER_URL
else
    echo "Runner already downloaded, skipping..."
fi

# Step 5: Extract
echo "Extracting runner..."
tar xzf $RUNNER_FILE

# Step 6: Configure
echo "Configuring runner..."
./config.sh --url $REPO_URL \
            --token $RUNNER_TOKEN \
            --name $RUNNER_NAME \
            --labels dockp04 \
            --unattended \
            --work _work

if [ $? -ne 0 ]; then
    echo "ERROR: Configuration failed"
    exit 1
fi

# Step 7: Install as service
echo ""
echo "Installing runner as service..."
./svc.sh install

echo ""
echo "Starting runner service..."
./svc.sh start

# Step 8: Verify
echo ""
echo "Verifying runner status..."
sleep 3
./svc.sh status

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Runner is now running in the background."
echo ""
echo "To manage the runner:"
echo "  Status:  $RUNNER_DIR/svc.sh status"
echo "  Stop:    $RUNNER_DIR/svc.sh stop"
echo "  Start:   $RUNNER_DIR/svc.sh start"
echo "  Restart: $RUNNER_DIR/svc.sh restart"
echo "  Logs:    $RUNNER_DIR/run.log"
echo ""
echo "To view runner in GitHub:"
echo "  https://github.com/tmt-homelab/living-docs/settings/actions/runners"
echo ""
echo "The queued workflow should start automatically!"
