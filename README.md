# Superior.Trade Discord Bot

A focused, command-first Discord bot for Superior.Trade built with `discord.py`.

## Status

Phase 1 complete:

- full repo scaffold
- slash commands and cog structure
- markdown knowledge loading and section retrieval
- curated static pair mapping from `SKILL.md`
- formatting helpers
- daily scheduler skeleton

Phase 2 complete:

- LLM-backed `/ask` and `/trade`
- optional official website and GitHub grounding
- daily brief generation with exact 2 crypto + 1 non-crypto slots
- uncertainty fallback handling

Phase 3 complete:

- pytest coverage for pair mapping, markdown retrieval, and formatting
- prompt refinement
- command error handling and cleaner runtime logging
- Koyeb deployment guidance
- operator handover notes in `HANDOVER.md`

## Project Structure

```text
superior-discord-bot/
  bot.py
  requirements.txt
  .env.example
  README.md
  HANDOVER.md
  cogs/
  core/
  services/
  prompts/
  knowledge/
  tests/
```

## Handover

If another agent or operator will deploy this repository, start with:

- [`HANDOVER.md`](/c:/Users/User/Desktop/superior-discord-bot/HANDOVER.md)

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env`.
4. Fill in your secrets and runtime settings.
5. Run a local dry-run:

```bash
python bot.py --dry-run
```

6. Start the bot:

```bash
python bot.py
```

## Environment Variables

Required for Discord:

- `DISCORD_BOT_TOKEN`

Optional but recommended:

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `DEEPSEEK_API_KEY`
- `OPENAI_API_KEY`
- `NEWS_API_KEY`
- `DAILY_POST_CHANNEL_ID`
- `LOG_LEVEL`
- `DRY_RUN`
- `TIMEZONE`
- `DAILY_BRIEF_HOUR`
- `DAILY_BRIEF_MINUTE`
- `SUPERIOR_WEBSITE_URL`
- `SUPERIOR_GITHUB_ORG`

Provider notes:

- If `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` are set, the bot uses that chat-completions-compatible provider.
- If only `OPENAI_API_KEY` is set, the bot defaults `LLM_BASE_URL` to `https://api.openai.com/v1`.
- If no live LLM provider is configured, `/ask`, `/trade`, and `/briefnow` fall back to safe deterministic output.
- If `NEWS_API_KEY` is missing, the daily brief still returns exactly three slots using explicit fallback headlines.

DeepSeek-style example:

```env
LLM_API_KEY=your_key
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL=your-model-name
```

## Slash Commands

- `/ask <question>`
- `/trade <asset_or_market>`
- `/briefnow`
- `/health`
- `/reloadkb`

## Knowledge Rules

- Load `FAQ.md`, `SKILL.md`, and `MARKETING.md` from `knowledge/`.
- Use `SKILL.md` as the main operational source of truth.
- Use `MARKETING.md` only when it is relevant and subtle.
- Do not invent product features or supported pairs.

## Local Testing

Run the dry-run:

```bash
python bot.py --dry-run
```

Run the test suite:

```bash
pytest -q
```

## Koyeb Deployment

This bot should be deployed to Koyeb as a `Worker` service, not a web service. It does not expose an HTTP port and should run as a background process.

### Koyeb Control Panel

1. Push this repo to GitHub.
2. In Koyeb, create a new app from GitHub.
3. Choose a Python buildpack deployment.
4. Set the service type to `Worker`.
5. Set the run command to:

```bash
python bot.py
```

6. Add environment variables:

```text
DISCORD_BOT_TOKEN=...
DRY_RUN=false
TIMEZONE=Asia/Singapore
DAILY_BRIEF_HOUR=15
DAILY_BRIEF_MINUTE=0
DAILY_POST_CHANNEL_ID=...
LLM_API_KEY=...
LLM_BASE_URL=...
LLM_MODEL=...
NEWS_API_KEY=...
```

7. Deploy the service.

### Koyeb CLI Example

If you use the Koyeb CLI, a worker-style buildpack deployment looks like this:

```bash
koyeb apps init superior-discord-bot \
  --git github.com/<your-org>/<your-repo> \
  --git-branch main \
  --git-builder buildpack \
  --git-buildpack-run-command "python bot.py" \
  --type worker \
  --env DISCORD_BOT_TOKEN=... \
  --env DRY_RUN=false \
  --env TIMEZONE=Asia/Singapore \
  --env DAILY_BRIEF_HOUR=15 \
  --env DAILY_BRIEF_MINUTE=0 \
  --env DAILY_POST_CHANNEL_ID=... \
  --env LLM_API_KEY=... \
  --env LLM_BASE_URL=... \
  --env LLM_MODEL=... \
  --env NEWS_API_KEY=...
```

### Deployment Notes

- Use `python bot.py` on Koyeb because the runtime is Linux-based.
- Keep `DRY_RUN=false` in production.
- The scheduled brief is timezone-aware and defaults to `15:00 Asia/Singapore`, which is GMT+8.
- If you want to pin Python explicitly for the platform, add a `runtime.txt` file later.

## Notes

- `SKILL.md` is the primary operational source of truth.
- The bot is slash-command only.
- Deterministic rules live in code. The model writes only the natural-language output.
