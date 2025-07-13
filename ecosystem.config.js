module.exports = {
    apps: [{
        name: 'Omnispindle',
        script: 'python3.11',
        args: '-m src.Omnispindle',
        watch: '.',
        env: {
            NODE_ENV: 'development'
        },
        env_production: {
            NODE_ENV: 'production'
        }
    }, {
        script: './service-worker/',
        watch: ['./service-worker']
    }],

    deploy: {
        production: {
            user: 'ubuntu',
            host: process.env.AWSIP || 'ENTER_AWS_IP_HERE',
            ref: 'origin/prod',
            repo: 'git@github.com:danedens/omnispindle.git',
            path: '/home/ubuntu/Omnispindle',
            'pre-deploy-local': 'whoami',
            'post-deploy': 'pm2 restart Omnispindle',
            'pre-setup': ''
        },
        development: {
            user: process.env.USER,
            host: 'localhost',
            repo: 'git@github.com:danedens/omnispindle.git',
            path: '/Users/d.edens/lab/madness_interactive/projects/common/Omnispindle',
            'post-deploy': 'pip install -r requirements.txt && pm2 reload ecosystem.config.js --env development',
            'pre-setup': ''
        }
    }
};
