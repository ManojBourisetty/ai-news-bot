"""
AI News Daily — GitHub Actions Edition
=======================================
Morning: Global news digest (world, tech, business, politics)
Evening: AI-specific digest (models, research, funding, policy)

Usage:
    python ai_news_bot.py --once morning
    python ai_news_bot.py --once evening

Environment Variables (set as GitHub Actions Secrets):
    GROQ_API_KEY      - Groq API key (free at console.groq.com)
    SLACK_BOT_TOKEN   - Slack Bot OAuth token (xoxb-...)
    SLACK_CHANNEL_ID  - Slack channel ID (e.g. C0B8HAB6589)
"""

import os
import sys
import logging
import argparse
from datetime import datetime, timezone, timedelta

import pytz
import feedparser
from groq import Groq
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
GROQ_API_KEY     = os.environ["GROQ_API_KEY"]
SLACK_BOT_TOKEN  = os.environ["SLACK_BOT_TOKEN"]
SLACK_CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]
TIMEZONE         = "America/Chicago"
MODEL            = "llama-3.3-70b-versatile"

# Global news feeds — used for morning edition
GLOBAL_FEEDS = [
    ("Reuters",          "https://feeds.reuters.com/reuters/topNews"),
    ("BBC News",         "http://feeds.bbci.co.uk/news/rss.xml"),
    ("The Guardian",     "https://www.theguardian.com/world/rss"),
    ("AP News",          "https://rsshub.app/apnews/topics/apf-topnews"),
    ("NPR News",         "https://feeds.npr.org/1001/rss.xml"),
    ("TechCrunch",       "https://techcrunch.com/feed/"),
    ("Ars Technica",     "https://feeds.arstechnica.com/arstechnica/index"),
]

# AI-specific feeds — used for evening edition
AI_FEEDS = [
    ("TechCrunch AI",   "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("VentureBeat AI",  "https://venturebeat.com/category/ai/feed/"),
    ("The Verge AI",    "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"),
    ("Wired AI",        "https://www.wired.com/feed/tag/ai/latest/rss"),
    ("MIT Tech Review", "https://www.technologyreview.com/topic/artificial-intelligence/feed"),
    ("Ars Technica",    "https://feeds.arstechnica.com/arstechnica/technology-lab"),
]


# ── RSS: Fetch Headlines ───────────────────────────────────────────────────
def fetch_headlines(feeds: list, hours: int) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    items = []
    for source, url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:25]:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                if published and published < cutoff:
                    continue
                title   = entry.get("title", "").strip()
                summary = entry.get("summary", "")[:300].strip()
                if title:
                    items.append(f"[{source}] {title} — {summary}")
        except Exception as e:
            log.warning(f"Failed to fetch {source}: {e}")
    log.info(f"Fetched {len(items)} headlines from the past {hours} hours")
    return "\n".join(items) if items else "No recent headlines found."


# ── Groq: Format Digest ──────────────────────────────────────────────────────
def fetch_digest(edition: str) -> str:
    tz       = pytz.timezone(TIMEZONE)
    date_str = datetime.now(tz).strftime("%B %d, %Y")

    if edition == "morning":
        headlines = fetch_headlines(GLOBAL_FEEDS, hours=18)
        prompt = f"""You are a world news analyst. Today is {date_str}.

Here are the latest global headlines from the past 18 hours:

{headlines}

Write a rich, detailed morning global news briefing for Slack using ONLY the headlines above. Do not invent stories.
Cover world events, politics, business, technology, and anything significant. Aim for 5-7 top stories.

Format EXACTLY like this (use Slack mrkdwn):

🌅 *Good Morning! Global News Digest — {date_str}*

*🌍 Top Stories*
• [Story — 2 sentences with context and why it matters]
• [Story]
• [Story]
• [Story]
• [Story]
• [Story if available]
• [Story if available]

*💼 Business & Markets*
• [Item — company, market move, or economic development]
• [Item if available]

*🖥️ Tech & Science*
• [Item — notable tech or science development]
• [Item if available]

*⚖️ Politics & Policy*
• [Item if available]

*🔥 Breaking / Developing*
• [Any fast-moving story if available]

―――
_📰 Sources: Reuters • BBC • The Guardian • AP • NPR • TechCrunch • Morning Edition • 8 AM CST_

Rules: factual and unbiased, 2 sentences per bullet with context, omit sections with no relevant news, respond with ONLY the Slack message."""

    else:
        headlines = fetch_headlines(AI_FEEDS, hours=10)
        prompt = f"""You are an AI news analyst. Today is {date_str}.

Here are the latest AI-specific headlines from the past 10 hours:

{headlines}

Write a rich, detailed AI evening update for Slack using ONLY the headlines above. Do not invent stories.
Aim for 4-5 top stories and fill every relevant section with 2-3 bullets.

Format EXACTLY like this (use Slack mrkdwn):

🤖 *Evening AI Update — {date_str}*

*🔥 Top AI Stories*
• [Story — 2 sentences with context and why it matters]
• [Story]
• [Story]
• [Story if available]
• [Story if available]

*💰 Business & Funding*
• [Item — company, deal or funding detail]
• [Item if available]

*🧪 Models & Research*
• [Item — what was released or published and why it’s significant]
• [Item if available]

*⚖️ Policy & Regulation*
• [Item if available]

*⚠️ Safety & Ethics*
• [Item if available]

―――
_📰 Sources: TechCrunch • VentureBeat • The Verge • Wired • MIT Tech Review • Evening Edition • 6 PM CST_

Rules: factual and unbiased, 2 sentences per bullet with context, omit sections with no relevant news, respond with ONLY the Slack message."""

    log.info(f"Formatting {edition} digest with Groq ({MODEL})...")

    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=MODEL,
        max_tokens=2000,
    )

    return response.choices[0].message.content.strip()


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
