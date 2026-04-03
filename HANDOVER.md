# Agent Handover

## Repo Status

This repository is production-oriented and currently complete enough to hand to another agent for deployment and operation.

Implemented:

- slash-command-first Discord bot using `discord.py`
- `/ask`, `/trade`, `/briefnow`, `/health`, `/reloadkb`
- scheduled daily brief at configurable time and timezone
- local markdown knowledge retrieval from `knowledge/`
- deterministic pair mapping in code
- optional LLM generation via chat-completions-compatible API
- optional news ingestion via NewsAPI-compatible key
- tests covering pair mapping, knowledge retrieval, and formatting

Current branch on GitHub:

- `main`

GitHub repository:

- `https://github.com/teojh9413/superior-trade`

## Runtime Entry Point

Run the bot with:

```bash
python bot.py
```

For validation without connecting to Discord:

```bash
python bot.py --dry-run
pytest -q
```

## Required Environment Variables

Minimum required to run against Discord:

- `DISCORD_BOT_TOKEN`
- `DAILY_POST_CHANNEL_ID`

Recommended runtime variables:

- `DRY_RUN=false`
- `TIMEZONE=Asia/Singapore`
- `DAILY_BRIEF_HOUR=15`
- `DAILY_BRIEF_MINUTE=0`
- `LOG_LEVEL=INFO`

If live LLM responses are desired:

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`

If live news retrieval is desired:

- `NEWS_API_KEY`

Reference template:

- [`.env.example`](/c:/Users/User/Desktop/superior-discord-bot/.env.example)

## Deployment Notes

- This bot is a background worker, not a web service.
- It does not expose an HTTP port.
- Suitable hosts are worker/process hosts, VPSes, or platforms that support long-running background processes.
- The scheduler is timezone-aware and defaults to `15:00 Asia/Singapore`, which is GMT+8.

## Knowledge and Behavior Rules

- `SKILL.md` is the main operational source of truth.
- `FAQ.md` and `MARKETING.md` are supplementary.
- Deterministic rules should remain in code.
- The model should not invent product features or unsupported pairs.
- If no clear edge exists, the bot should say so.
- If uncertain in `/ask`, the fallback sentence is:

`I’m not fully sure on that. I’ll call on the Superior.Trade team members to assist.`

## Important Security Notes

The following secrets were previously pasted into chat during setup and should be rotated before any real production deployment:

- Discord bot token
- DeepSeek API key

Do not commit secrets to Git.

Expected secret handling:

- keep real values out of the repository
- store them in server environment variables or host-managed secret storage
- keep only placeholder values in `.env.example`

## What The Next Agent Should Check First

1. Confirm the deployed environment has the required secrets set.
2. Run `python bot.py --dry-run` in the target environment.
3. Run `pytest -q`.
4. Start the bot with `python bot.py`.
5. Verify slash commands in Discord:
   - `/health`
   - `/reloadkb`
   - `/ask`
   - `/trade`
   - `/briefnow`
6. Confirm the daily brief channel ID is correct.
7. If using live LLM output, verify `LLM_BASE_URL` and `LLM_MODEL` match the provider.

## Files Most Relevant To Operators

- [`bot.py`](/c:/Users/User/Desktop/superior-discord-bot/bot.py)
- [`README.md`](/c:/Users/User/Desktop/superior-discord-bot/README.md)
- [`services/llm_service.py`](/c:/Users/User/Desktop/superior-discord-bot/services/llm_service.py)
- [`services/news_service.py`](/c:/Users/User/Desktop/superior-discord-bot/services/news_service.py)
- [`services/knowledge_service.py`](/c:/Users/User/Desktop/superior-discord-bot/services/knowledge_service.py)
- [`services/pair_mapper.py`](/c:/Users/User/Desktop/superior-discord-bot/services/pair_mapper.py)
- [`.env.example`](/c:/Users/User/Desktop/superior-discord-bot/.env.example)
