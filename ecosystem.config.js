module.exports = {
    apps: [{
        name: 'Omnispindle',
        script: 'python3.13',
        args: '-m src.Omnispindle',
        watch: false,  // Disable watch in production
        instances: 1,
        exec_mode: 'fork',
        restart_delay: 1000,
        max_restarts: 5,
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
