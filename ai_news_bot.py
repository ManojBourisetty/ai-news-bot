"""
AI News Daily — GitHub Actions Edition
=======================================
Fetches the latest global AI news via Gemini (Google Search grounding)
and posts a digest to Slack. Designed to be triggered by
GitHub Actions cron schedule — no persistent process needed.

Usage:
    python ai_news_bot.py --once morning
    python ai_news_bot.py --once evening

Environment Variables (set as GitHub Actions Secrets):
    GEMINI_API_KEY    - Google AI Studio API key (free at aistudio.google.com)
    SLACK_BOT_TOKEN   - Slack Bot OAuth token (xoxb-...)
    SLACK_CHANNEL_ID  - Slack channel ID (e.g. C0B8HAB6589)
"""

import os
import sys
import logging
import argparse
from datetime import datetime
import pytz

from google import genai
from google.genai import types
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
GEMINI_API_KEY   = os.environ["GEMINI_API_KEY"]
SLACK_BOT_TOKEN  = os.environ["SLACK_BOT_TOKEN"]
SLACK_CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]
TIMEZONE         = "America/Chicago"
MODEL            = "gemini-2.0-flash"


# ── Gemini: Fetch & Summarize ─────────────────────────────────────────────────
def fetch_digest(edition: str) -> str:
    client   = genai.Client(api_key=GEMINI_API_KEY)
    tz       = pytz.timezone(TIMEZONE)
    date_str = datetime.now(tz).strftime("%B %d, %Y")

    if edition == "morning":
        prompt = f"""You are an AI news analyst. Today is {date_str}.

Search the web for the LATEST global AI news from the past 18 hours and write a morning briefing for Slack.

Format EXACTLY like this (use Slack mrkdwn):

🌅 *Good Morning! AI News Digest — {date_str}*

*🔥 Top Stories*
• [Story — 1-2 sentences, factual, no bias]
• [Story]
• [Story]
• [Story]
• [Story]

*💰 Business & Funding*
• [Item if any]

*🤖 Model & Tech Releases*
• [Item if any]

*⚖️ Policy & Regulation*
• [Item if any]

*🌍 Global & Geopolitical AI*
• [Item if any]

*⚠️ Safety & Ethics Watch*
• [Item if any]

---
_Sources searched live • Morning Edition • 8 AM CST_

Rules: factual and unbiased, 1-2 sentences per bullet, skip sections with no news, respond with ONLY the Slack message."""

    else:
        prompt = f"""You are an AI news analyst. Today is {date_str}.

Search the web for the LATEST global AI news from the past 10 hours and write an evening update for Slack.

Format EXACTLY like this (use Slack mrkdwn):

🌆 *Evening AI Update — {date_str}*

*🔥 What Broke Today*
• [Story — 1-2 sentences, factual, no bias]
• [Story]
• [Story]

*📈 Market & Business Moves*
• [Item if any]

*🧪 Research & Releases*
• [Item if any]

*🌍 Global Developments*
• [Item if any]

*🗣️ Notable Quote / Take*
• [One notable quote or reaction if available]

---
_Sources searched live • Evening Edition • 6 PM CST_

Rules: factual and unbiased, 1-2 sentences per bullet, skip sections with no news, respond with ONLY the Slack message."""

    log.info(f"Fetching {edition} digest from Gemini with Google Search...")

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )

    return response.text.strip()


# ── Slack: Post ────────────────────────────────────────────────────────────────
def post_to_slack(message: str) -> bool:
    client = WebClient(token=SLACK_BOT_TOKEN)
    try:
        result = client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            text=message,
            mrkdwn=True,
        )
        log.info(f"✅ Posted to Slack (ts={result['ts']})")
        return True
    except SlackApiError as e:
        log.error(f"❌ Slack error: {e.response['error']}")
        return False


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--once",
        choices=["morning", "evening"],
        required=True,
        help="Which edition to send",
    )
    args = parser.parse_args()

    digest = fetch_digest(args.once)
    if not digest:
        log.error("Empty digest returned — aborting.")
        sys.exit(1)

    success = post_to_slack(digest)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
