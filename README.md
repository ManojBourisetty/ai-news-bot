# 🤖 AI News Daily — Slack Bot

Automated twice-daily AI news digest delivered to Slack, powered by **Claude** (live web search) + **GitHub Actions**.

| Edition | Time | Coverage |
|---|---|---|
| 🌅 Morning | 8:00 AM CST | Last 18 hours of global AI news |
| 🌆 Evening | 6:00 PM CST | Last 10 hours — what broke today |

---

## 🚀 Quick Setup (5 minutes)

### 1. Fork / clone this repo

### 2. Add GitHub Secrets

Go to your repo → Settings → Secrets and variables → Actions → New repository secret

Add these three secrets:

| Secret Name | Where to get it |
|---|---|
| ANTHROPIC_API_KEY | https://console.anthropic.com |
| SLACK_BOT_TOKEN | https://api.slack.com/apps → your app → OAuth & Permissions |
| SLACK_CHANNEL_ID | Your #ai-news-daily channel ID (e.g. C0B8HAB6589) |

### 3. Create a Slack Bot (if you haven't)

1. Go to https://api.slack.com/apps → Create New App
2. Add Bot Token Scopes: `chat:write`, `chat:write.public`
3. Install to workspace → copy the `xoxb-...` token
4. Invite bot to your channel: `/invite @YourBotName`

### 4. Enable GitHub Actions

Push to main — the workflow activates automatically on the cron schedule.
To test immediately: Actions tab → AI News Daily Digest → Run workflow → Choose edition

---

## 📁 Project Structure

```
ai-news-bot/
├── .github/
│   └── workflows/
│       └── ai_news_digest.yml
├── ai_news_bot.py
├── requirements.txt
└── README.md
```

---

## ⏰ Cron Schedule

```yaml
- cron: "0 14 * * *"   # 8 AM CST (14:00 UTC)
- cron: "0 0 * * *"    # 6 PM CST (00:00 UTC)
```

GitHub Actions uses UTC. CST = UTC−6 (winter) / CDT = UTC−5 (summer).

---

## 🛠️ Manual Trigger

1. Go to Actions → AI News Daily Digest
2. Click **Run workflow**
3. Select `morning` or `evening`
4. Click **Run workflow** ✅

---

## 💰 Cost

| Resource | Cost |
|---|---|
| GitHub Actions | Free (2,000 min/month on free tier — ~2 min/day) |
| Anthropic API | ~$0.01–0.03 per digest (Sonnet with web search) |
| Slack API | Free |

Estimated total: ~$1–2/month
