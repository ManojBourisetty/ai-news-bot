"""
Vercel serverless function — triggered by vercel.json crons.
Dispatches the GitHub Actions workflow for the requested edition.
All heavy lifting (RSS fetch, Groq, Slack) stays in GitHub Actions
so there's no Vercel timeout concern.
"""
import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

REPO     = "ManojBourisetty/ai-news-bot"
WORKFLOW = "ai_news_digest.yml"


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs      = parse_qs(urlparse(self.path).query)
        edition = qs.get("edition", ["morning"])[0]
        if edition not in ("morning", "evening", "weekly"):
            self._respond(400, {"error": f"unknown edition: {edition}"})
            return

        token = os.environ.get("GH_TOKEN", "")
        if not token:
            self._respond(500, {"error": "GH_TOKEN env var not set"})
            return

        payload = json.dumps({"ref": "main", "inputs": {"edition": edition}}).encode()
        req = Request(
            f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches",
            data=payload,
            headers={
                "Authorization":  f"Bearer {token}",
                "Accept":         "application/vnd.github.v3+json",
                "Content-Type":   "application/json",
                "User-Agent":     "ai-news-bot-vercel/1.0",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=8) as resp:
                gh_status = resp.status
        except URLError as exc:
            self._respond(500, {"error": str(exc)})
            return

        self._respond(200, {"triggered": edition, "github_status": gh_status})

    def _respond(self, code: int, body: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, *args):
        pass  # suppress default access logging
