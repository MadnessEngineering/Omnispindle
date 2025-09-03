import os
import sys
from pathlib import Path
import requests
import json

# Add src to path to allow direct import
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from Omnispindle.auth_flow import ensure_authenticated

def get_user_info(token: str):
    """Get user information from Auth0's /userinfo endpoint."""
    try:
        auth0_domain = os.getenv("AUTH0_DOMAIN")
        userinfo_url = f"https://{auth0_domain}/userinfo"
        headers = {'Authorization': f'Bearer {token}'}

        response = requests.get(userinfo_url, headers=headers)
        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Error getting user info: {e}")
        return None

def main():
    """Test that we can get a token and that it contains the correct user info."""
    print("🚀 Testing User Identity Flow...")

    try:
        token = ensure_authenticated()
        print("✅ Token received.")

        user_info = get_user_info(token)

        if not user_info:
            print("❌ Could not get user info.")
            sys.exit(1)

        print("\n--- User Info ---")
        print(json.dumps(user_info, indent=2))
        print("------------------\n")

        user_id = user_info.get('sub')

        if user_id:
            print(f"✅ User ID (sub): {user_id}")
        else:
            print("❌ User ID (sub) not found!")

    except RuntimeError as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
