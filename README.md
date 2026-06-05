# 🤖 AI News Daily — Slack Bot

Automated twice-daily AI news digest delivered to Slack, powered by **Groq (Llama 3.3-70B)** + **free RSS feeds** + **Vercel Crons**.

| Edition | Time | Coverage |
|---|---|---|
| 🌅 Morning | 8:00 AM CST (13:00 UTC) | Global + India news — last 18 hours |
| 🌆 Evening | 6:00 PM CST (23:00 UTC) | AI-specific digest — last 10 hours |
| 📅 Weekly (Fri) | 10:00 AM CST (15:00 UTC) | AI week in review |

**News sources:** TechCrunch • VentureBeat • The Verge • Wired • MIT Tech Review • Ars Technica • OpenAI • Anthropic • DeepMind • HuggingFace • Reuters • BBC • AP • The Hindu • NDTV

---

## 🚀 Setup

### 1. Deploy to Vercel

Connect this repo to a Vercel project. Vercel auto-deploys on push to `main`.

### 2. Add Environment Variables in Vercel

Go to your Vercel project → Settings → Environment Variables and add:

| Variable | Where to get it |
|---|---|
| `GROQ_API_KEY` | https://console.groq.com → API Keys → Create API Key (free) |
| `SLACK_BOT_TOKEN` | https://api.slack.com/apps → your app → OAuth & Permissions |
| `SLACK_CHANNEL_ID` | Your Slack channel ID (e.g. C0B8HAB6589) |

### 3. Create a Slack Bot (if you haven't)

1. Go to https://api.slack.com/apps → Create New App
2. Add Bot Token Scopes: `chat:write`, `chat:write.public`
3. Install to workspace → copy the `xoxb-...` token
4. Invite bot to your channel: `/invite @YourBotName`

### 4. Verify Crons Are Active

In Vercel → your project → Settings → Crons — you should see three entries matching `vercel.json`. They fire automatically once deployed.

---

## 📁 Project Structure

```
ai-news-bot/
├── api/
│   └── trigger.py       # Vercel serverless function (cron entry point)
├── ai_news_bot.py        # Core bot logic (RSS → Groq → Slack)
├── requirements.txt
├── vercel.json           # Cron schedule + function config
└── README.md
```

---

## ⏰ Cron Schedule

```json
{ "path": "/api/trigger?edition=morning", "schedule": "0 13 * * *" }   // 8 AM CST
{ "path": "/api/trigger?edition=evening", "schedule": "0 23 * * *" }   // 6 PM CST
{ "path": "/api/trigger?edition=weekly",  "schedule": "0 15 * * 5" }   // 10 AM CST Fri
```

All times in UTC. CST = UTC−6.

---

## 🛠️ Manual Trigger

Hit the function directly from your browser or curl:

```bash
curl "https://your-project.vercel.app/api/trigger?edition=morning"
curl "https://your-project.vercel.app/api/trigger?edition=evening"
curl "https://your-project.vercel.app/api/trigger?edition=weekly"
```

---

## ⚠️ Notes

- **Vercel plan**: Cron jobs and 60s function timeout require the **Pro** plan.
- **Deduplication cache**: Vercel serverless functions are stateless — the seen-headlines cache does not persist across invocations. Headlines may occasionally repeat between editions, but each run fetches and summarises correctly.

---

## 💰 Cost

| Resource | Cost |
|---|---|
| Vercel Pro | $20/month (required for crons + 60s timeout) |
| Groq API (Llama 3.3-70B) | Free tier |
| RSS Feeds | Free |
| Slack API | Free |
