# PM2 Custom Actions for Omnispindle

This setup provides PM2 custom actions for automating common deployment and management tasks for the Omnispindle application.

## Setup

1. **Install Node.js dependencies:**

   ```bash
   npm install
   ```

2. **Start the ecosystem with custom actions:**

   ```bash
   pm2 start ecosystem.config.js
   ```

## Available Custom Actions

### 1. `git-pull-restart`

**Purpose:** Pull latest code from git and restart the Omnispindle process
**Command executed:** `cd ~/Omnispindle && git pull && pm2 restart Omnispindle`

This is the main action you requested - it changes to the Omnispindle directory, pulls the latest code, and restarts the PM2 process.

### 2. `git-status`

**Purpose:** Check the current git repository status
**Command executed:** `cd ~/Omnispindle && git status --porcelain`

Useful for checking if there are uncommitted changes before pulling.

### 3. `pm2-status`

**Purpose:** Get detailed status of the Omnispindle PM2 process
**Command executed:** `pm2 jlist` (parsed to show Omnispindle-specific info)

Shows process status, PID, uptime, and restart count.

### 4. `restart-omnispindle`

**Purpose:** Restart only the Omnispindle process
**Command executed:** `pm2 restart Omnispindle`

Simple restart without git operations.

## Usage

### From PM2 Plus Dashboard

1. Go to your PM2 Plus dashboard at <https://app.pm2.io>
2. Navigate to the "Actions Center" section
3. You'll see all available custom actions
4. Click on `git-pull-restart` to execute your requested command
5. View the output and success/failure status

### From Command Line (Testing)

You can test the actions locally:

```bash
# Start the custom actions service
pm2 start pm2-actions.js --name "Omnispindle-Actions"

# Check PM2 logs to see available actions
pm2 logs Omnispindle-Actions
```

## Architecture

- **pm2-actions.js**: Main Node.js service that defines the custom actions
- **package.json**: Defines the `@pm2/io` dependency
- **ecosystem.config.js**: Updated to include the custom actions service as a second app

## Security Notes

- The custom actions run with the same permissions as the PM2 process
- Commands are executed in the shell, so ensure your environment is secure
- Git operations assume SSH key authentication is properly configured

## Troubleshooting

1. **Custom actions not showing in dashboard:**
   - Ensure `@pm2/io` is properly installed: `npm install`
   - Check that the Omnispindle-Actions process is running: `pm2 status`
   - Review logs: `pm2 logs Omnispindle-Actions`

2. **Git pull failing:**
   - Verify SSH keys are configured for git access
   - Check that the ~/Omnispindle directory exists and is a git repository
   - Ensure no uncommitted changes conflict with the pull

3. **PM2 restart failing:**
   - Verify the Omnispindle process is registered with PM2
   - Check PM2 process list: `pm2 list`

## Integration with Existing Workflow

This setup integrates with your existing ecosystem.config.js deployment workflow. The `post-deploy` hooks have been updated to:

- Install npm dependencies
- Restart both the main Omnispindle app and the custom actions service

Your Makefile commands for remote deployment will continue to work as before, with the added benefit of having the custom actions available through the PM2 Plus dashboard.
