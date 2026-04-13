# GitHub Actions Runner Setup for dockp04

## Quick Setup (5 minutes)

### Step 1: Get Registration Token

1. Go to: `https://github.com/tmt-homelab/living-docs/settings/actions/runners`
2. Click **"New runner"**
3. Select:
   - **OS**: Linux
   - **Architecture**: x64
4. Copy the **registration token** (it's a long string)

### Step 2: SSH to dockp04 and Run Setup

```bash
ssh dockp04

# Clone the living-docs repo (if not already)
cd ~
git clone https://github.com/tmt-homelab/living-docs.git
cd living-docs/scripts

# Run the setup script
./setup_github_runner.sh
```

When prompted, paste the registration token from Step 1.

### Step 3: Verify

The script will:
1. Download the GitHub Actions runner
2. Configure it with your token
3. Install it as a systemd service
4. Start the service

You should see:
```
=== Setup Complete ===
Runner is now running in the background.
```

### Step 4: Check in GitHub

1. Go to: `https://github.com/tmt-homelab/living-docs/settings/actions/runners`
2. You should see **dockp04-runner** with status **Online**
3. The queued workflow will start automatically!

---

## Manual Setup (If Script Fails)

If you prefer to do it manually:

```bash
ssh dockp04

# Create directory
mkdir -p ~/actions-runner
cd ~/actions-runner

# Download runner (version 2.310.0)
curl -o actions-runner-linux-x64-2.310.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.310.0/actions-runner-linux-x64-2.310.0.tar.gz

# Extract
tar xzf *.tar.gz

# Configure (replace TOKEN with your registration token)
./config.sh --url https://github.com/tmt-homelab/living-docs \
            --token TOKEN \
            --name dockp04-runner \
            --labels dockp04 \
            --unattended

# Install and start as service
./svc.sh install
./svc.sh start

# Verify
./svc.sh status
```

---

## Troubleshooting

### Runner shows "Offline" in GitHub

**Check service status:**
```bash
cd ~/actions-runner
./svc.sh status
```

**Check logs:**
```bash
tail -f ~/actions-runner/run.log
```

**Restart service:**
```bash
./svc.sh restart
```

### Service won't start

**Check for conflicts:**
```bash
sudo systemctl status actions-runner.dockp04-runner
sudo journalctl -u actions-runner.dockp04-runner -n 50
```

**Reinstall service:**
```bash
cd ~/actions-runner
./svc.sh uninstall
./svc.sh install
./svc.sh start
```

### Token expired

Registration tokens expire after 1 hour. If you get "Bad token" error:

1. Go back to GitHub → Settings → Actions → Runners
2. Click **"New runner"** again to get a fresh token
3. Remove old runner:
   ```bash
   cd ~/actions-runner
   ./config.sh remove
   ```
4. Reconfigure with new token

### Runner not picking up jobs

**Verify labels:**
```bash
cd ~/actions-runner
cat .runner
```

Should show: `["dockp04"]`

**Check workflow matches:**
The workflow uses `runs-on: [self-hosted, dockp04]`, so the runner must have the `dockp04` label.

---

## Managing the Runner

### View logs
```bash
tail -f ~/actions-runner/run.log
```

### Stop runner
```bash
cd ~/actions-runner
./svc.sh stop
```

### Start runner
```bash
cd ~/actions-runner
./svc.sh start
```

### Remove runner completely
```bash
cd ~/actions-runner
./config.sh remove
./svc.sh uninstall
rm -rf ~/actions-runner
```

---

## Security Notes

- The runner runs with your user permissions (tmiller)
- It has access to Corvus API (localhost:9420)
- Secrets are injected securely by GitHub Actions
- Runner service runs as your user, not root

---

## Next Steps

Once the runner is online:

1. The queued workflow will start automatically
2. Monitor progress: `https://github.com/tmt-homelab/living-docs/actions`
3. Check logs if it fails
4. Verify site deployment to dockp04

---

*Setup script: `scripts/setup_github_runner.sh`*  
*Runner directory: `~/actions-runner` on dockp04*
