# Privacy & Security Notice

## ⚠️ Private Configuration Repository

**This repository contains sensitive production configurations and should not be used directly without modification.**

### Sensitive Information Included:
- **Auth0 credentials** - Client IDs, secrets, and domain configurations
- **Database connections** - MongoDB URIs and collection structures  
- **API endpoints** - Internal service URLs and authentication tokens
- **Infrastructure identifiers** - Cloudflare account/zone IDs
- **Business logic** - Proprietary MCP tool implementations

### For Production Use:
1. **Fork this repository** to your own private organization
2. **Replace all authentication providers** with your own Auth0/OAuth setup
3. **Update domain configurations** for your own SSL certificates
4. **Review MCP tool permissions** and modify as needed for your use case
5. **Configure your own database** and MQTT infrastructure
6. **Update Terraform variables** with your Cloudflare account details

### Not Suitable For:
- Direct deployment without configuration changes
- Public sharing without removing sensitive data
- Use with production data without proper security review
- Educational purposes without understanding the security implications

### If You Found This Publicly:
This repository may have been accidentally made public. Please:
- Do not use the included credentials for any purpose
- Report the exposure responsibly if you believe it's unintentional
- Understand this represents a working production system

---

**Intended Use:** This serves as a reference implementation and starting point for organizations building similar MCP-based AI tool management systems. Adapt responsibly for your own infrastructure.