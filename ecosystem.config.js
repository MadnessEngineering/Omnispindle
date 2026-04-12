module.exports = {
    apps: [
    {
        name: 'Omnispindle',
        script: 'python3.13',
        args: '-m src.Omnispindle',
        watch: false,
        instances: 1,
        exec_mode: 'fork',
        // Crash loop protection: stop after 10 rapid failures, backoff between restarts
        max_restarts: 10,
        min_uptime: '10s',
        restart_delay: 5000,
        exp_backoff_restart_delay: 100,
        env: {
            NODE_ENV: 'development',
            OMNISPINDLE_MODE: 'hybrid',
            OMNISPINDLE_TOOL_LOADOUT: 'basic',
            PYTHONPATH: '.'
        },
        env_production: {
            NODE_ENV: 'production',
            OMNISPINDLE_MODE: process.env.OMNISPINDLE_MODE || 'api',
            OMNISPINDLE_TOOL_LOADOUT: process.env.OMNISPINDLE_TOOL_LOADOUT || 'basic',
            MADNESS_AUTH_TOKEN: process.env.MADNESS_AUTH_TOKEN,
            MADNESS_API_URL: process.env.MADNESS_API_URL || 'https://madnessinteractive.cc/api',
            MCP_USER_EMAIL: process.env.MCP_USER_EMAIL,
            PYTHONPATH: '.'
        },
        error_file: './logs/err.log',
        out_file: './logs/out.log',
        log_file: './logs/combined.log'
    },
    {
        name: 'Omnispindle-HTTP',
        script: 'python3.11',
        args: '-m src.Omnispindle.http_server',
        cwd: '/home/ubuntu/Omnispindle',
        watch: false,
        instances: 1,
        exec_mode: 'fork',
        // Crash loop protection: stop after 10 rapid failures, backoff between restarts
        max_restarts: 10,
        min_uptime: '10s',
        restart_delay: 5000,
        exp_backoff_restart_delay: 100,
        env_production: {
            NODE_ENV: 'production',
            OMNISPINDLE_MODE: process.env.OMNISPINDLE_MODE || 'hybrid',
            OMNISPINDLE_TOOL_LOADOUT: process.env.OMNISPINDLE_TOOL_LOADOUT || 'full',
            MADNESS_AUTH_TOKEN: process.env.MADNESS_AUTH_TOKEN,
            MADNESS_API_URL: process.env.MADNESS_API_URL || 'https://madnessinteractive.cc/api',
            PYTHONPATH: '.'
        },
        error_file: './logs/http-err.log',
        out_file: './logs/http-out.log',
        log_file: './logs/http-combined.log'
    }],

    // Deployment now handled via GitHub Actions
    // Legacy deploy configs removed - see .github/workflows/ for CI/CD
    deploy: {
        production: {
            // GitHub Actions will handle deployment
            // Environment variables managed through GitHub Secrets
            // See: .github/workflows/deploy.yml (to be created)
        }
    }
};
