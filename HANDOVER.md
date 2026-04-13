# Agent Handover

## Repo

- GitHub: `https://github.com/teojh9413/superior-trade`
- Branch: `main`

## Current Product Scope

This bot is narrowly scoped.

It only supports:

- scheduled daily market brief posting
- `/dailybrief`
- `/trade <asset_name>`
- `/backtest <asset_name>`
- `/health`

It is not a FAQ bot and not a general chat bot.

## Runtime Entry Point

```bash
python bot.py
```

Validation:

```bash
python bot.py --dry-run
pytest -q
```

## Required Environment Variables

- `DISCORD_BOT_TOKEN`
- `DAILY_POST_CHANNEL_ID`
- `DEEPSEEK_API_KEY`
- `SUPERIOR_TRADE_API_KEY`

Recommended runtime values:

- `DRY_RUN=false`
- `TIMEZONE=Asia/Singapore`
- `DAILY_BRIEF_HOUR=15`
- `DAILY_BRIEF_MINUTE=0`
- `LOG_LEVEL=INFO`

Optional:

- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_MODEL`
- `DEEPSEEK_TIMEOUT_SECONDS`
- `DDGS_CLI_PATH`
- `HYPERLIQUID_INFO_URL`
- `SUPERIOR_TRADE_API_URL`
- `BACKTEST_REGISTRY_PATH`
- `BACKTEST_POLL_SECONDS`
- `BACKTEST_TIMEOUT_SECONDS`
- `BACKTEST_DATA_LAG_DAYS`
- `BACKTEST_MAX_ADDITIONAL_LAG_DAYS`

Reference:

- [`.env.example`](/c:/Users/User/Desktop/superior-discord-bot/.env.example)

## Important Behavior Rules

- `/trade` only accepts a simple asset name.
- `/backtest` only accepts a simple asset name.
- `/dailybrief` is the only on-demand brief command.
- Invalid long natural-language `/trade` inputs must reply exactly:

`My role is to suggest trading strategies, please use /trade + name of desired asset`

- Invalid long natural-language `/backtest` inputs must reply exactly:

`My role is to run backtests, please use /backtest + name of desired asset`

- The frontend should not mention mapping logic.
- The frontend should not mention internal ticker mechanics.
- The brief must use only the past 24 hours.
- The brief must contain exactly:
  - 2 crypto headlines
  - 1 tradfi headline
- The brief format is:
  - headline
  - concise summary
  - three short strategy prompts
- `/backtest` must stay deterministic:
  - 7 fixed strategy templates in code
  - sequential execution
  - delete existing backtests before starting a new run
  - cleanup created backtests after the run
  - return only the best single result

## Data Sources

News:

- DDGS CLI news search via subprocess
- DeepSeek for final brief summaries and strategy prompts when configured

Trade generation:

- DeepSeek using the official resolved Hyperliquid ticker when configured

Ticker discovery:

- official Hyperliquid `info` endpoint

Backtesting:

- Superior.Trade API

## Deployment Notes

- This is a worker/process app, not a web app.
- The runtime must have the DDGS CLI available.
- The runtime should provide `DEEPSEEK_API_KEY` for live `/trade` and brief generation.
- `/backtest` requires a valid `SUPERIOR_TRADE_API_KEY`.
- Do not deploy to static/shared website hosting.

## Security Notes

Secrets must not be committed to Git.

Store them in server environment variables or host secret storage only.

## First Checks For The Next Agent

1. Confirm the runtime has `ddgs` available or set `DDGS_CLI_PATH`.
2. Run `python bot.py --dry-run`.
3. Run `pytest -q`.
4. Start `python bot.py`.
5. Verify Discord commands:
   - `/health`
   - `/dailybrief`
   - `/trade btc`
   - `/backtest btc`
6. Confirm the production `DAILY_POST_CHANNEL_ID`.

## Files Most Relevant To Operators

- [`bot.py`](/c:/Users/User/Desktop/superior-discord-bot/bot.py)
- [`README.md`](/c:/Users/User/Desktop/superior-discord-bot/README.md)
- [`services/news_service.py`](/c:/Users/User/Desktop/superior-discord-bot/services/news_service.py)
- [`services/hyperliquid_service.py`](/c:/Users/User/Desktop/superior-discord-bot/services/hyperliquid_service.py)
- [`services/prompt_service.py`](/c:/Users/User/Desktop/superior-discord-bot/services/prompt_service.py)
- [`services/formatter.py`](/c:/Users/User/Desktop/superior-discord-bot/services/formatter.py)
- [`services/backtest_service.py`](/c:/Users/User/Desktop/superior-discord-bot/services/backtest_service.py)
- [`services/superior_api_service.py`](/c:/Users/User/Desktop/superior-discord-bot/services/superior_api_service.py)
- [`services/strategy_templates.py`](/c:/Users/User/Desktop/superior-discord-bot/services/strategy_templates.py)
- [`reference/SKILL.md`](/c:/Users/User/Desktop/superior-discord-bot/reference/SKILL.md)
