"""
AI News Daily — GitHub Actions Edition
=======================================
Morning:  Global + India news digest (world, tech, business, politics)
Evening:  AI-specific digest (models, research, funding, policy)
Weekly:   Friday roundup of the week’s biggest AI stories

Usage:
    python ai_news_bot.py --once morning
    python ai_news_bot.py --once evening
    python ai_news_bot.py --once weekly

Environment Variables (set as GitHub Actions Secrets):
    GROQ_API_KEY      - Groq API key (free at console.groq.com)
    SLACK_BOT_TOKEN   - Slack Bot OAuth token (xoxb-...)
    SLACK_CHANNEL_ID  - Slack channel ID (e.g. C0B8HAB6589)
"""

import os
import re
import sys
import json
import hashlib
import logging
import argparse
from collections import Counter
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
CACHE_FILE       = "seen_headlines.json"
CACHE_MAX        = 400

# Global news feeds — morning edition
GLOBAL_FEEDS = [
    ("Reuters",      "https://feeds.reuters.com/reuters/topNews"),
    ("BBC News",     "http://feeds.bbci.co.uk/news/rss.xml"),
    ("The Guardian", "https://www.theguardian.com/world/rss"),
    ("AP News",      "https://rsshub.app/apnews/topics/apf-topnews"),
    ("NPR News",     "https://feeds.npr.org/1001/rss.xml"),
    ("TechCrunch",   "https://techcrunch.com/feed/"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
]

# India news feeds — morning edition (dedicated section)
INDIA_FEEDS = [
    ("The Hindu",        "https://www.thehindu.com/feeder/default.rss"),
    ("NDTV",             "https://feeds.feedburner.com/ndtvnews-top-stories"),
    ("Times of India",   "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"),
    ("Indian Express",   "https://indianexpress.com/feed/"),
    ("Economic Times",   "https://economictimes.indiatimes.com/rssfeedstopstories.cms"),
    ("Hindustan Times",  "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml"),
]

# AI-specific feeds — evening + weekly editions
AI_FEEDS = [
    ("TechCrunch AI",  "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    ("The Verge AI",   "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"),
    ("Wired AI",       "https://www.wired.com/feed/tag/ai/latest/rss"),
    ("MIT Tech Review","https://www.technologyreview.com/topic/artificial-intelligence/feed"),
    ("Ars Technica",   "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("OpenAI Blog",    "https://openai.com/news/rss/"),
    ("Anthropic Blog", "https://www.anthropic.com/rss.xml"),
    ("DeepMind Blog",  "https://deepmind.google/blog/rss.xml"),
    ("HuggingFace",    "https://huggingface.co/blog/feed.xml"),
    ("Hacker News AI", "https://hnrss.org/newest?q=AI+LLM"),
    ("404 Media",      "https://www.404media.co/rss/"),
]

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "will", "would", "could", "should", "may", "might",
    "this", "that", "these", "those", "it", "its", "as", "up", "out", "into",
    "about", "over", "new", "says", "said", "after", "before", "more", "than",
    "how", "why", "what", "who", "which", "when", "where", "not", "can", "do",
    "does", "did", "get", "got", "make", "made", "use", "used", "using", "just",
}


# ── Deduplication Cache ──────────────────────────────────────────────────────
def title_hash(title: str) -> str:
    return hashlib.md5(title.lower().strip().encode()).hexdigest()

def load_cache() -> set:
    try:
        with open(CACHE_FILE) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_cache(existing: set, new_hashes: list):
    combined = list(existing) + new_hashes
    with open(CACHE_FILE, "w") as f:
        json.dump(combined[-CACHE_MAX:], f)


# ── Trending Score ───────────────────────────────────────────────────────────────
def _key_words(title: str) -> set:
    words = re.findall(r"\b[a-zA-Z]{3,}\b", title.lower())
    return {w for w in words if w not in STOP_WORDS}

def rank_by_trending(items: list) -> list:
    """Score each headline by how many other headlines share 2+ keywords."""
    titles = []
    for item in items:
        raw = item.split(" — ")[0]
        raw = re.sub(r"^\[.*?\]\s*", "", raw)
        titles.append(raw)

    item_words = [_key_words(t) for t in titles]
    scores = []
    for i, words_i in enumerate(item_words):
        if not words_i:
            scores.append(0)
            continue
        overlap = sum(
            1 for j, words_j in enumerate(item_words)
            if i != j and len(words_i & words_j) >= 2
        )
        scores.append(overlap)

    ranked = sorted(zip(scores, range(len(items)), items), key=lambda x: x[0], reverse=True)
    result = []
    for score, _, item in ranked:
        result.append(f"[📡 {score + 1} sources] {item}" if score >= 1 else item)

    trending = sum(1 for s, _, _ in ranked if s >= 1)
    log.info(f"Trending scorer: {trending}/{len(items)} headlines covered by 2+ sources")
    return result


# ── RSS: Fetch Headlines ──────────────────────────────────────────────────
def fetch_headlines(feeds: list, hours: int, seen: set, rank: bool = True) -> tuple:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    items, new_hashes = [], []

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
                if not title:
                    continue
                h = title_hash(title)
                if h in seen:
                    continue
                new_hashes.append(h)
                items.append(f"[{source}] {title} — {summary}")
        except Exception as e:
            log.warning(f"Failed to fetch {source}: {e}")

    log.info(f"Fetched {len(items)} new headlines from past {hours}h")
    ranked = rank_by_trending(items) if rank and items else items
    return ("\n".join(ranked) if ranked else "No recent headlines found."), new_hashes


# ── Block Kit Formatter ────────────────────────────────────────────────────
def build_blocks(message: str) -> list:
    blocks = []
    chunk = ""
    for line in message.split("\n"):
        if len(chunk) + len(line) + 1 > 2800 and chunk:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk.strip()}})
            blocks.append({"type": "divider"})
            chunk = line
        else:
            chunk = chunk + "\n" + line if chunk else line
    if chunk.strip():
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk.strip()}})
    return blocks


# ── Groq: Format Digest ──────────────────────────────────────────────────────
def fetch_digest(edition: str, seen: set) -> tuple:
    tz       = pytz.timezone(TIMEZONE)
    date_str = datetime.now(tz).strftime("%B %d, %Y")

    if edition == "morning":
        global_hl, global_hashes = fetch_headlines(GLOBAL_FEEDS, hours=18, seen=seen)
        # Pass seen + global hashes so India fetch doesn’t repeat cross-feed duplicates
        india_seen = seen | set(global_hashes)
        india_hl, india_hashes   = fetch_headlines(INDIA_FEEDS, hours=18, seen=india_seen, rank=False)
        new_hashes = global_hashes + india_hashes

        prompt = f"""You are a world and India news analyst. Today is {date_str}.

GLOBAL headlines (ranked by source coverage — [📡 N sources] = covered by N outlets, prioritise these):
{global_hl}

INDIA headlines:
{india_hl}

Write a rich morning briefing for Slack. Use ONLY the headlines above. Do not invent stories.
Prioritise multi-source global stories in Top Stories. Include a dedicated India News section.

Format EXACTLY like this (use Slack mrkdwn):

🌅 *Good Morning! Daily News Digest — {date_str}*

*🌍 Top Stories*
• [Story — 2 sentences with context and why it matters]
• [Story]
• [Story]
• [Story]
• [Story]
• [Story if available]

*🌇 India News*
• [India story — 2 sentences with context]
• [India story]
• [India story]
• [India story if available]
• [India story if available]

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

_📰 Sources: Reuters • BBC • AP • The Guardian • NPR • The Hindu • NDTV • Times of India • Indian Express • Economic Times • Morning Edition • 8 AM CST_

Rules: factual and unbiased, 2 sentences per bullet, omit sections with no relevant news, respond with ONLY the Slack message."""

    elif edition == "evening":
        headlines, new_hashes = fetch_headlines(AI_FEEDS, hours=10, seen=seen)
        prompt = f"""You are an AI news analyst. Today is {date_str}.

Latest AI headlines (ranked by source coverage — [📡 N sources] = trending, prioritise these):
{headlines}

Write a rich AI evening update for Slack. Use ONLY the headlines above. Do not invent stories.

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

_📰 Sources: TechCrunch • VentureBeat • The Verge • Wired • MIT Tech Review • OpenAI • Anthropic • DeepMind • HN • 404 Media • Evening Edition • 6 PM CST_

Rules: factual and unbiased, 2 sentences per bullet, omit sections with no relevant news, respond with ONLY the Slack message."""

    else:  # weekly — bypass daily dedup for full week picture
        headlines, new_hashes = fetch_headlines(AI_FEEDS, hours=168, seen=set())
        prompt = f"""You are an AI news analyst. This is the week ending {date_str}.

AI headlines from the past 7 days (ranked by source coverage — [📡 N sources] = most covered):
{headlines}

Write a Friday weekly roundup for Slack. Use ONLY the headlines above. Pick only the most significant stories.

Format EXACTLY like this (use Slack mrkdwn):

📅 *AI Week in Review — Week of {date_str}*
_The biggest AI stories you need to know from this week_

*🏆 Story of the Week*
• [The single most important AI development — 3 sentences explaining what happened and why it matters]

*🔥 Top Stories*
• [Story — 2 sentences explaining significance]
• [Story]
• [Story]
• [Story]
• [Story]

*💰 Funding & Business*
• [Biggest funding rounds, acquisitions, or partnerships]
• [Item if available]

*🧪 Models & Research Breakthroughs*
• [Most significant model releases or research papers this week]
• [Item if available]

*⚖️ Policy & Safety*
• [Key regulatory or safety developments]
• [Item if available]

*👀 What to Watch Next Week*
• [1-2 developing stories or trends to follow]

_📰 Weekly Edition • Every Friday 10 AM CST • Sources: TechCrunch • VentureBeat • The Verge • Wired • MIT Tech Review • OpenAI • Anthropic • DeepMind • HN • 404 Media_

Rules: curate only the truly significant stories, 2-3 sentences per bullet for depth, respond with ONLY the Slack message."""

    log.info(f"Formatting {edition} digest with Groq ({MODEL})...")
    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=MODEL,
        max_tokens=2500,
    )
    return response.choices[0].message.content.strip(), new_hashes


# ── Slack: Post ────────────────────────────────────────────────────────────────
def post_to_slack(message: str) -> bool:
    client = WebClient(token=SLACK_BOT_TOKEN)
    try:
        result = client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            text=message,
            blocks=build_blocks(message),
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
        choices=["morning", "evening", "weekly"],
        required=True,
        help="Which edition to send",
    )
    args = parser.parse_args()

    seen               = load_cache()
    digest, new_hashes = fetch_digest(args.once, seen)

    if not digest:
        log.error("Empty digest returned — aborting.")
        sys.exit(1)

    success = post_to_slack(digest)

    if success:
        save_cache(seen, [] if args.once == "weekly" else new_hashes)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
