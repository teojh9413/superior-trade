# Superior.Trade Discord Bot

A focused Discord bot for:

- daily market brief posting
- `/briefnow`
- `/trade <asset_name>`
- `/health`

This is not a knowledge-base bot and not a general chat bot.

## Scope

The bot now does only four things:

1. Post a daily market brief at `3:00 PM` in the configured timezone.
2. Generate the same brief on demand with `/briefnow`.
3. Suggest a practical strategy for a single asset with `/trade`.
4. Show basic runtime status with `/health`.

Removed from scope:

- `/ask`
- `/reloadkb`
- markdown knowledge retrieval
- FAQ / SKILL / MARKETING runtime loading
- frontend explanations about ticker mapping

## Commands

- `/health`
- `/briefnow`
- `/trade <asset_name>`

`/trade` only accepts a simple asset name such as:

- `btc`
- `eth`
- `tesla`
- `gold`

If the input is a long sentence or question, the bot replies with:

`My role is to suggest trading strategies, please use /trade + name of desired asset`

## Architecture

Main services:

- `services/news_service.py`
- `services/hyperliquid_service.py`
- `services/prompt_service.py`
- `services/formatter.py`

Other runtime support:

- `bot.py`
- `core/config.py`
- `core/scheduler.py`
- `core/logging.py`

## News Retrieval

The bot uses the DDGS CLI news flow:

- DuckDuckGo news search through subprocess execution
- strict filtering to the last 24 hours
- deduplication of similar headlines
- preference for major / reputable sources
- selection of exactly:
  - 2 crypto headlines
  - 1 tradfi headline

The brief contains:

- headline
- concise summary
- three short strategy prompts

## Hyperliquid Ticker Validation

`/trade` and the brief prompts validate markets using the official Hyperliquid `info` endpoint.

The bot:

- fetches live market metadata from Hyperliquid
- resolves simple asset inputs to current official markets
- uses the official ticker directly in frontend output
- does not expose internal mapping language to users

If no valid Hyperliquid market exists, the bot says so clearly.

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env`.
4. Fill in the required values.
5. Run a dry-run:

```bash
python bot.py --dry-run
```

6. Start the bot:

```bash
python bot.py
```

## Environment Variables

Required:

- `DISCORD_BOT_TOKEN`
- `DAILY_POST_CHANNEL_ID`

Runtime:

- `DRY_RUN`
- `TIMEZONE`
- `DAILY_BRIEF_HOUR`
- `DAILY_BRIEF_MINUTE`
- `LOG_LEVEL`

Optional:

- `DDGS_CLI_PATH`
- `HYPERLIQUID_INFO_URL`

Defaults:

- `TIMEZONE=Asia/Singapore`
- `DAILY_BRIEF_HOUR=15`
- `DAILY_BRIEF_MINUTE=0`
- `HYPERLIQUID_INFO_URL=https://api.hyperliquid.xyz/info`

## Local Validation

Dry-run:

```bash
python bot.py --dry-run
```

Tests:

```bash
pytest -q
```

## Deployment Notes

- This bot is a background worker, not a web service.
- It should run on a process/worker host or server.
- It should not be deployed to static website hosting.
- The DDGS CLI must be available in the runtime environment, either on `PATH` or via `DDGS_CLI_PATH`.

## Files To Check First

- `bot.py`
- `services/news_service.py`
- `services/hyperliquid_service.py`
- `services/prompt_service.py`
- `services/formatter.py`
- `.env.example`
