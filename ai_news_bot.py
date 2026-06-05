"""
AI News Daily — GitHub Actions Edition
=======================================
Fetches the latest global AI news via Claude (web search)
and posts a digest to Slack. Designed to be triggered by
GitHub Actions cron schedule — no persistent process needed.

Usage:
    python ai_news_bot.py --once morning
    python ai_news_bot.py --once evening

Environment Variables (set as GitHub Actions Secrets):
    ANTHROPIC_API_KEY   - Anthropic API key
    SLACK_BOT_TOKEN     - Slack Bot OAuth token (xoxb-...)
    SLACK_CHANNEL_ID    - Slack channel ID (e.g. C0B8HAB6589)
"""

import os
import sys
import logging
import argparse
from datetime import datetime
import pytz

import anthropic
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SLACK_BOT_TOKEN   = os.environ["SLACK_BOT_TOKEN"]
SLACK_CHANNEL_ID  = os.environ["SLACK_CHANNEL_ID"]
TIMEZONE          = "America/Chicago"


# ── Claude: Fetch & Summarize ──────────────────────────────────────────────────
def fetch_digest(edition: str) -> str:
    client   = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
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

    log.info(f"Fetching {edition} digest from Claude with web search...")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    return "".join(b.text for b in response.content if b.type == "text").strip()


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
