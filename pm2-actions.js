#!/usr/bin/env node

const io = require('@pm2/io');
const { exec } = require('child_process');
const path = require('path');
const os = require('os');

console.log('PM2 Custom Actions service starting...');

// Get the home directory path
const homeDir = os.homedir();
const omnispindleDir = path.join(homeDir, 'Omnispindle');

// Custom action for git pull and PM2 restart
io.action('git-pull-restart', (cb) =>
{
    console.log('Executing git pull and PM2 restart...');

    // Command to run: cd ~/Omnispindle && git pull && pm2 restart Omnispindle
    const command = `cd ${omnispindleDir} && git pull && pm2 restart Omnispindle`;

    exec(command, (error, stdout, stderr) =>
    {
        if (error)
        {
            console.error('Error executing git pull and restart:', error);
            return cb({
                success: false,
                error: error.message,
                stderr: stderr
            });
        }

        console.log('Git pull and restart completed successfully');
        console.log('stdout:', stdout);

        return cb({
            success: true,
            message: 'Git pull and PM2 restart completed successfully',
            stdout: stdout,
            stderr: stderr,
            timestamp: new Date().toISOString()
        });
    });
});

// Additional useful custom actions
io.action('git-status', (cb) =>
{
    console.log('Checking git status...');

    const command = `cd ${omnispindleDir} && git status --porcelain`;

    exec(command, (error, stdout, stderr) =>
    {
        if (error)
        {
            console.error('Error checking git status:', error);
            return cb({
                success: false,
                error: error.message,
                stderr: stderr
            });
        }

        return cb({
            success: true,
            message: 'Git status retrieved successfully',
            status: stdout.trim() || 'Working tree clean',
            timestamp: new Date().toISOString()
        });
    });
});

io.action('pm2-status', (cb) =>
{
    console.log('Checking PM2 status...');

    const command = 'pm2 jlist';

    exec(command, (error, stdout, stderr) =>
    {
        if (error)
        {
            console.error('Error checking PM2 status:', error);
            return cb({
                success: false,
                error: error.message,
                stderr: stderr
            });
        }

        try
        {
            const processes = JSON.parse(stdout);
            const omnispindleProcess = processes.find(p => p.name === 'Omnispindle');

            return cb({
                success: true,
                message: 'PM2 status retrieved successfully',
                omnispindle_status: omnispindleProcess ? {
                    name: omnispindleProcess.name,
                    status: omnispindleProcess.pm2_env.status,
                    pid: omnispindleProcess.pid,
                    uptime: omnispindleProcess.pm2_env.pm_uptime,
                    restarts: omnispindleProcess.pm2_env.restart_time
                } : 'Process not found',
                timestamp: new Date().toISOString()
            });
        } catch (parseError)
        {
            return cb({
                success: false,
                error: 'Failed to parse PM2 status',
                raw_output: stdout
            });
        }
    });
});

io.action('restart-omnispindle', (cb) =>
{
    console.log('Restarting Omnispindle...');

    const command = 'pm2 restart Omnispindle';

    exec(command, (error, stdout, stderr) =>
    {
        if (error)
        {
            console.error('Error restarting Omnispindle:', error);
            return cb({
                success: false,
                error: error.message,
                stderr: stderr
            });
        }

        return cb({
            success: true,
            message: 'Omnispindle restarted successfully',
            stdout: stdout,
            timestamp: new Date().toISOString()
        });
    });
});

// Keep the process alive
console.log('PM2 Custom Actions service is running...');
console.log(`Working directory: ${omnispindleDir}`);
console.log('Available actions:');
console.log('- git-pull-restart: Pull latest code and restart Omnispindle');
console.log('- git-status: Check git repository status');
console.log('- pm2-status: Check PM2 process status');
console.log('- restart-omnispindle: Restart only the Omnispindle process'); 
