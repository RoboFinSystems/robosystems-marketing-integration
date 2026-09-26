"""Mint the read-only Google grant this integration runs on.

One browser consent → one refresh token covering Search Console and
YouTube (Data + Analytics), read-only. Writes GOOGLE_CLIENT_ID /
GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN into .env; nothing is
printed.

    uv run python bin/google-auth.py path/to/client_secret.json

The client file is a Desktop-app OAuth client from Google Cloud
Console. Its project needs the Search Console API, YouTube Data API v3
and YouTube Analytics API enabled, and the account that consents must
see both the Search Console properties and the channel (for a brand
channel, pick the channel on the consent screen).
"""

from __future__ import annotations

import json
import re
import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

SCOPES = [
  "https://www.googleapis.com/auth/webmasters.readonly",
  "https://www.googleapis.com/auth/youtube.readonly",
  "https://www.googleapis.com/auth/yt-analytics.readonly",
]
ENV_PATH = Path(".env")


def _authorize(client_id: str) -> tuple[str, str]:
  """Run the loopback consent flow; return (code, redirect_uri)."""
  state = secrets.token_urlsafe(16)
  result: dict[str, str] = {}

  class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
      query = parse_qs(urlparse(self.path).query)
      if query.get("state", [""])[0] == state and "code" in query:
        result["code"] = query["code"][0]
        body = b"Authorized. You can close this tab."
      else:
        result["error"] = query.get("error", ["state mismatch"])[0]
        body = b"Authorization failed. See the terminal."
      self.send_response(200)
      self.end_headers()
      self.wfile.write(body)

    def log_message(self, *args: object) -> None:
      return

  server = HTTPServer(("127.0.0.1", 0), Handler)
  redirect_uri = f"http://127.0.0.1:{server.server_port}"
  url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
    {
      "client_id": client_id,
      "redirect_uri": redirect_uri,
      "response_type": "code",
      "scope": " ".join(SCOPES),
      "access_type": "offline",
      "prompt": "consent",
      "state": state,
    }
  )
  print("Opening the Google consent screen in your browser…")
  webbrowser.open(url)
  while not result:
    server.handle_request()
  server.server_close()
  if "error" in result:
    raise SystemExit(f"Authorization failed: {result['error']}")
  return result["code"], redirect_uri


def _write_env(values: dict[str, str]) -> None:
  text = ENV_PATH.read_text() if ENV_PATH.is_file() else ""
  for key, value in values.items():
    line = f"{key}={value}"
    if re.search(rf"^{key}=", text, re.M):
      text = re.sub(rf"^{key}=.*$", lambda _: line, text, flags=re.M)
    else:
      text = text.rstrip("\n") + f"\n{line}\n"
  ENV_PATH.write_text(text)


def main() -> None:
  if len(sys.argv) != 2:
    raise SystemExit(__doc__)
  client = json.loads(Path(sys.argv[1]).read_text())
  client = client.get("installed") or client.get("web") or client
  code, redirect_uri = _authorize(client["client_id"])
  response = httpx.post(
    "https://oauth2.googleapis.com/token",
    data={
      "code": code,
      "client_id": client["client_id"],
      "client_secret": client["client_secret"],
      "redirect_uri": redirect_uri,
      "grant_type": "authorization_code",
    },
    timeout=30,
  )
  response.raise_for_status()
  token = response.json()
  if "refresh_token" not in token:
    raise SystemExit("No refresh token returned — revoke the app's access and retry.")
  granted = set(token.get("scope", "").split())
  missing = [scope for scope in SCOPES if scope not in granted]
  if missing:
    raise SystemExit(f"Consent did not grant: {missing}")
  _write_env(
    {
      "GOOGLE_CLIENT_ID": client["client_id"],
      "GOOGLE_CLIENT_SECRET": client["client_secret"],
      "GOOGLE_REFRESH_TOKEN": token["refresh_token"],
    }
  )
  print("Wrote GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN to .env")


if __name__ == "__main__":
  main()
