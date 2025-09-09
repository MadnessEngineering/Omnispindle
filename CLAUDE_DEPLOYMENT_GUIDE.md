# Critical Deployment Information for Future Work

## 🔧 Troubleshooting Common Issues

**Authentication Problems**:
- Check `~/.omnispindle/` for token cache
- Verify `MCP_USER_EMAIL` is set correctly
- Test API connectivity: `python test_api_client.py`
- For auth setup issues: `python -m src.Omnispindle.auth_setup`

**Docker Issues**:
- Use Python 3.13 base image (updated from 3.11)
- API mode requires `MADNESS_AUTH_TOKEN` environment variable
- Health check endpoint: `http://localhost:8000/health`
- Docker daemon must be running for build scripts

**PM2 Deployment**:
- Updated to Python 3.13 (ecosystem.config.js)
- Use `API` mode for production deployments
- Environment variables externalized for security
- GitHub Actions replaces legacy deployment scripts

**PyPI Publishing**:
- Version in `pyproject.toml` and `src/Omnispindle/__init__.py` must match
- Use `./build-and-publish-pypi.sh` for automated builds
- Test on TestPyPI first: `python -m twine upload --repository testpypi dist/*`
- CLI entry points: `omnispindle`, `omnispindle-server`, `omnispindle-stdio`

## 🔮 Next Development Priorities

**Remaining DEPLOYMENT_MODERNIZATION_PLAN.md Phases**:
- ⏳ **Phase 7**: Cleanup and optimization (remove legacy files, optimize Docker layers)
- ⏳ **Phase 8**: Testing and validation (integration tests, performance benchmarks)  
- ⏳ **Phase 9**: Release preparation (changelog, version tags, final documentation)

**Security Maintenance**:
- Git-secrets is now active - will prevent future credential commits
- Enhanced .gitignore patterns protect sensitive files
- All hardcoded IPs converted to environment variables
- Regular security audits recommended before releases

**Architecture Evolution**:
- API-first is now the recommended production mode
- Hybrid mode provides reliability with fallback
- Consider deprecating local mode in future versions
- Tool loadouts reduce AI agent token consumption

## 🎯 Key Files for Future Modifications

**Core Server Files**:
- `src/Omnispindle/stdio_server.py` - Main MCP server entry point
- `src/Omnispindle/__main__.py` - CLI and web server entry point
- `src/Omnispindle/api_tools.py` - API-first tool implementations

**Configuration**:
- `pyproject.toml` - PyPI package metadata and entry points
- `ecosystem.config.js` - PM2 process management (Python 3.13)
- `Dockerfile` - Containerization (Python 3.13, API-first)
- `MANIFEST.in` - PyPI package file inclusion/exclusion

**Security**:
- `.gitignore` - Enhanced with comprehensive security patterns
- `.git/hooks/` - Git-secrets protection active
- `src/Omnispindle/auth_setup.py` - Zero-config authentication

**Documentation**:
- `README.md` - User-facing documentation (recently updated)
- `CLAUDE.md` - Developer guidance (main file)
- `DEPLOYMENT_MODERNIZATION_PLAN.md` - Deployment roadmap

## 💡 Development Tips

- Always use Python 3.13 for new development
- API mode is preferred for production deployments
- Test with different tool loadouts to optimize performance  
- Commit early and often - deployment uses git hooks
- Use `timeout 15` with pm2 log commands (they run forever)
- Security: Never commit secrets, git-secrets will catch most issues