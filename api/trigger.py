"""
Vercel serverless function — triggered by vercel.json crons.
Runs the AI news bot directly in-process.

Required Vercel environment variables:
    GROQ_API_KEY       - Groq API key
    SLACK_BOT_TOKEN    - Slack bot OAuth token (xoxb-...)
    SLACK_CHANNEL_ID   - Target Slack channel ID
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_news_bot import fetch_digest, load_cache, post_to_slack, save_cache

log = logging.getLogger(__name__)


CRON_SECRET = os.environ.get("CRON_SECRET", "")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)

        # Vercel passes CRON_SECRET as Authorization: Bearer <secret> on cron requests.
        # When set, reject any request that doesn't carry the right token so manual
        # curls can't accidentally fire a duplicate send.
        if CRON_SECRET:
            auth = self.headers.get("Authorization", "")
            if auth != f"Bearer {CRON_SECRET}":
                self._respond(401, {"error": "unauthorized"})
                return

        edition = qs.get("edition", ["morning"])[0]
        if edition not in ("morning", "evening", "weekly"):
            self._respond(400, {"error": f"unknown edition: {edition}"})
            return

        # Respond immediately so Vercel doesn't retry the slow request
        self._respond(202, {"accepted": True, "edition": edition})

        try:
            seen, last_runs = load_cache()
            digest, new_hashes = fetch_digest(edition, seen)

            if not digest:
                log.error("Empty digest — aborting.")
                return

            success = post_to_slack(digest)

            if success:
                last_runs[edition] = datetime.now(timezone.utc).isoformat()
                save_cache(seen, [] if edition == "weekly" else new_hashes, last_runs)
        except Exception as exc:
            log.exception("Bot error")

    def _respond(self, code: int, body: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, *args):
        pass
