"""
Run this once to get your Google Calendar refresh token.
Usage:
    python get_refresh_token.py
"""
import urllib.parse
import urllib.request
import json

CLIENT_ID = input("Paste your Client ID: ").strip()
CLIENT_SECRET = input("Paste your Client Secret: ").strip()

SCOPE = "https://www.googleapis.com/auth/calendar"
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"

auth_url = (
    "https://accounts.google.com/o/oauth2/auth"
    f"?client_id={CLIENT_ID}"
    f"&redirect_uri={REDIRECT_URI}"
    f"&response_type=code"
    f"&scope={urllib.parse.quote(SCOPE)}"
    f"&access_type=offline"
    f"&prompt=consent"
)

print("\nOpen this URL in your browser and authorize access:\n")
print(auth_url)
print()

auth_code = input("Paste the authorization code shown after approval: ").strip()

data = urllib.parse.urlencode({
    "code": auth_code,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
    "grant_type": "authorization_code",
}).encode()

req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
with urllib.request.urlopen(req) as resp:
    payload = json.loads(resp.read())

print("\n--- Copy these into your .env ---")
print(f"GOOGLE_CALENDAR_CLIENT_ID={CLIENT_ID}")
print(f"GOOGLE_CALENDAR_CLIENT_SECRET={CLIENT_SECRET}")
print(f"GOOGLE_CALENDAR_REFRESH_TOKEN={payload['refresh_token']}")
