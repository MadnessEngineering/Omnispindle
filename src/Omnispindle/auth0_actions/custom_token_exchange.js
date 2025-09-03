/**
 * Auth0 Custom Token Exchange Action for Omnispindle
 * 
 * This action handles the exchange of locally-generated tokens for Auth0 tokens.
 * It validates the token format and creates/links users based on the local machine identity.
 * 
 * To deploy:
 * 1. Create a new Action in Auth0 Dashboard with Custom Token Exchange trigger
 * 2. Copy this code into the Action editor
 * 3. Deploy the Action
 * 4. Create a Custom Token Exchange Profile with subject_token_type: "urn:omnispindle:local-auth"
 */

/**
 * Handler to be executed while executing a custom token exchange request
 * @param {Event} event - Details about the incoming token exchange request.
 * @param {CustomTokenExchangeAPI} api - Methods and utilities to define token exchange process.
 */
exports.onExecuteCustomTokenExchange = async (event, api) => {
  const subjectToken = event.transaction.subject_token;
  
  // Validate token format: local.{username}.{timestamp}.{hash}
  const tokenParts = subjectToken.split('.');
  
  if (tokenParts.length !== 4 || tokenParts[0] !== 'local') {
    api.access.rejectInvalidSubjectToken('Invalid token format');
    return;
  }
  
  const [_, username, timestamp, hash] = tokenParts;
  
  // Validate timestamp (not older than 5 minutes)
  const tokenTime = parseInt(timestamp);
  const currentTime = Math.floor(Date.now() / 1000);
  const maxAge = 300; // 5 minutes
  
  if (isNaN(tokenTime) || currentTime - tokenTime > maxAge) {
    api.access.rejectInvalidSubjectToken('Token expired');
    return;
  }
  
  // Validate hash format (should be 64 hex chars for SHA256)
  if (!/^[a-f0-9]{64}$/i.test(hash)) {
    api.access.rejectInvalidSubjectToken('Invalid token hash');
    return;
  }
  
  // Create a unique user ID based on the machine identity
  // We use the hash as it contains machine-specific information
  const userId = `local_${username}_${hash.substring(0, 12)}`;
  
  // Set the user in Auth0
  // This will create the user if they don't exist, or link to existing
  api.authentication.setUserByConnection(
    'Username-Password-Authentication', // Your database connection name
    {
      user_id: userId,
      email: `${username}@local.omnispindle`,
      username: username,
      name: username,
      user_metadata: {
        auth_method: 'local_token_exchange',
        machine_hash: hash.substring(0, 12),
        last_exchange: new Date().toISOString()
      }
    },
    {
      creationBehavior: 'setUserIdIfNotExists',
      updateBehavior: 'update_user_metadata'
    }
  );
  
  // Add custom claims to the token
  api.accessToken.setCustomClaim('auth_method', 'local_token_exchange');
  api.accessToken.setCustomClaim('local_user', username);
  api.idToken.setCustomClaim('auth_method', 'local_token_exchange');
  api.idToken.setCustomClaim('local_user', username);
}; 
