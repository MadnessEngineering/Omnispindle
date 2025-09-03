# Setting Up Auth0 Custom Token Exchange for Omnispindle

This guide walks through configuring Auth0's Custom Token Exchange feature to enable the one-liner authentication for Omnispindle MCP clients.

## Prerequisites

- Auth0 Enterprise account (Custom Token Exchange is an Early Access feature for Enterprise customers)
- Admin access to your Auth0 tenant
- Management API access token

## Step 1: Enable Custom Token Exchange on Your Application

First, update your Omnispindle application in Auth0 to allow Custom Token Exchange:

```bash
curl -X PATCH "https://YOUR_TENANT.auth0.com/api/v2/clients/YOUR_CLIENT_ID" \
  -H "Authorization: Bearer YOUR_MGMT_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "token_exchange": {
      "allow_any_profile_of_type": ["custom_authentication"]
    }
  }'
```

## Step 2: Create the Custom Token Exchange Action

1. Navigate to **Auth0 Dashboard > Actions > Library**
2. Click **Create Action > Build from Scratch**
3. Name: `Omnispindle Token Exchange`
4. Trigger: **Custom Token Exchange**
5. Click **Create**

6. Copy the code from `src/Omnispindle/auth0_actions/custom_token_exchange.js` into the Action editor

7. Update the connection name in the code if needed (default is `Username-Password-Authentication`)

8. Click **Deploy**

9. Note the Action ID from the URL (it's the last part of the URL)

## Step 3: Create the Custom Token Exchange Profile

Create a profile that maps the local token type to your Action:

```bash
curl -X POST "https://YOUR_TENANT.auth0.com/api/v2/token-exchange-profiles" \
  -H "Authorization: Bearer YOUR_MGMT_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "omnispindle-local-auth",
    "subject_token_type": "urn:omnispindle:local-auth",
    "action_id": "YOUR_ACTION_ID",
    "type": "custom_authentication"
  }'
```

## Step 4: Configure Application Settings

Ensure your Auth0 application has the correct settings:

1. **First-Party Application**: Dashboard > Applications > YOUR_APP > Settings > Application Properties > Application Type
2. **OIDC Conformant**: Dashboard > Applications > YOUR_APP > Advanced Settings > OAuth > OIDC Conformant (toggle ON)
3. **Database Connection**: Dashboard > Applications > YOUR_APP > Connections > Database (enable your connection)

## Step 5: Update Omnispindle Configuration

Update the Auth0 configuration in `src/Omnispindle/token_exchange.py`:

```python
AUTH0_DOMAIN = "your-tenant.auth0.com"
AUTH0_CLIENT_ID = "your_client_id"
AUTH0_AUDIENCE = "https://your-api-audience"
SUBJECT_TOKEN_TYPE = "urn:omnispindle:local-auth"  # Must match the profile
```

## Step 6: Test the Setup

Run the token exchange locally:

```bash
python -m src.Omnispindle.token_exchange
```

You should see:
- ✅ Successfully obtained Auth0 token!
- Configuration saved to your MCP client config
- The token printed to stdout

## Troubleshooting

### "Consent required" Error

Enable **Allow Skipping User Consent** for your API:
1. Dashboard > APIs > YOUR_API > Settings
2. Toggle ON "Allow Skipping User Consent"

### "Invalid grant type" Error

Ensure Custom Token Exchange is enabled for your application (Step 1)

### "Profile not found" Error

Verify the `subject_token_type` matches between:
- The Custom Token Exchange Profile
- The `token_exchange.py` configuration
- The Action expects this type

### Rate Limits

Custom Token Exchange is rate-limited at 10% of your Authentication API limit:
- Enterprise: 10 RPS
- Private Cloud Basic: 10 RPS
- Private Cloud Performance (5x): 50 RPS

Plan accordingly for large-scale deployments.

## Security Considerations

1. **Token Expiration**: Local tokens expire after 5 minutes to prevent replay attacks
2. **Machine Identity**: Tokens include machine-specific information for added security
3. **User Isolation**: Each machine/user combination gets a unique Auth0 user
4. **Audit Trail**: All token exchanges are logged in Auth0 for security monitoring

## Next Steps

Once configured, users can authenticate with a single command:

```bash
python -m src.Omnispindle.token_exchange
```

This provides a seamless, secure authentication experience for MCP clients without manual token management. 
