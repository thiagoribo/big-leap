"""Run this ON YOUR COMPUTER (it opens a browser for Google login).

  pip install google-auth-oauthlib
  python scripts/generate_refresh_token.py caminho/para/client_secret.json

Log in with the Google account that has access to the Big Leap Google Ads
account. The script prints the refresh token to put in GOOGLE_ADS_REFRESH_TOKEN.
"""

import sys

from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(
    sys.argv[1], scopes=["https://www.googleapis.com/auth/adwords"]
)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
print("\nGOOGLE_ADS_CLIENT_ID=" + creds.client_id)
print("GOOGLE_ADS_REFRESH_TOKEN=" + creds.refresh_token)
