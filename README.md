# Kalshi/Polymarket Arbitrage Bot

## Overview

This repo contains an experimental async trading bot for matched Kalshi and Polymarket event markets. It reads paired markets from `data/matchedtable.csv`, subscribes to both exchanges' orderbook WebSockets, keeps normalized in-memory books, and looks for buy-both-yes arbitrage where the Kalshi ask plus the Polymarket ask is less than 1 after estimated fees.

When the strategy finds enough net spread, it queues an execution event. The execution engine posts fill-or-kill opening orders on both exchanges, records fills as positions, updates in-memory cash balances, and writes trade attempts to `logs/trades.csv`.

This code can place live orders when credentials and funded accounts are configured.

## Current Trading Behavior

- Opens only paired `BUY`/`BUY` yes-side positions: one Kalshi yes contract and one Polymarket outcome token for the matched opposite side.
- Uses the current best ask on both orderbooks.
- Estimates fees with the current strategy coefficients: `0.07 * price * (1 - price)` for Kalshi and `0.03 * price * (1 - price)` for Polymarket.
- Requires net spread greater than `0.01` before queueing execution.
- Sizes entries as `min(int(0.75 * displayed_min_ask_volume), 10)` with a minimum trade size of 1.
- Skips Polymarket orders whose pre-fee notional would be below $1.
- Marks asset IDs active while an execution event is in flight and avoids opening another position on an already-open pair.
- If only one leg fills, attempts to unwind that filled leg by posting the opposite side against the current top of book up to 25 times.
- Does not yet implement normal position closing, expiry redemption, user-stream reconciliation, or persistent position recovery after restart.

## Project Layout

| Path | Purpose |
| --- | --- |
| `src/trading_engine.py` | Main entrypoint. Sets up logging, clients, queues, balances, listeners, strategy, and execution workers. |
| `src/strategy_engine.py` | Consumes orderbook update events, checks matched books for opening opportunities, and queues execution events. |
| `src/execution_engine.py` | Places Kalshi and Polymarket orders, logs trade attempts, updates balances, records positions, and unwinds lone fills. |
| `src/state_classes/market_holder.py` | Singleton registry for matched market IDs, orderbooks, and Kalshi-to-Polymarket lookup maps. |
| `src/state_classes/orderbook.py` | Sorted in-memory bid/ask book with best bid/ask helpers. |
| `src/state_classes/order.py` | Dataclass for one exchange order. |
| `src/state_classes/position.py` | Dataclass for a paired Kalshi/Polymarket position. |
| `src/state_classes/position_manager.py` | Tracks open/closed positions, active asset IDs, balances, and lookup maps. |
| `src/state_classes/events.py` | Queue event dataclasses for orderbook updates and executions. |
| `src/matching/` | Discover sports moneylines on Kalshi/Polymarket, match opposite outcomes, write `matchedtable.csv`. |
| `src/monitoring/` | Modular gap tracking and CSV event logging. No orderbook dependencies; reusable from strategy, notebooks, or other tools. |
| `src/kalshi_modules/` | Kalshi credentials, WebSocket listener, subscription payloads, and orderbook message handling. |
| `src/polymarket_modules/` | Polymarket credentials, WebSocket listener, subscription payloads, balance fetches, and orderbook message handling. |
| `src/util/enums.py` | Shared enums for exchanges, order sides, order status, and position status. |
| `demos/` | Small manual WebSocket/API experiments. These are not part of the main bot loop. |
| `logs/` | Runtime logs and trade CSV output. |
| `secrets/` | Local credentials. This directory is ignored by git. |

## Matched Markets

`data/matchedtable.csv` is the source of truth for markets the bot watches. `MarketHolder` loads it once at startup and creates one empty `Orderbook` per listed ticker. Each row is one complementary arb pair between any two venues (`kalshi`, `poly_global`, or later `poly_us`).

### Refreshing matches

Use the sports market matcher to discover open moneylines and pair opposite outcomes:

```bash
source .venv/bin/activate
python -m src.matching.run_matcher                 # dry-run
python -m src.matching.run_matcher --sport mlb     # optional filter
python -m src.matching.run_matcher --write         # update matchedtable.csv
```

High-confidence pairs are written to `data/matchedtable.csv`. Unsure candidates go to `data/match_review.csv` and are never auto-added. Auto-accept requires the same league, teams, date, and start times within 45 minutes (so same-day doubleheaders do not cross-match). The matcher discovers **Kalshi**, **Polymarket Global**, and **Polymarket US**, then emits opposite-side pairs for every venue combination that clears the scorer. Optional AI verification for ambiguous pairs uses `OPENAI_API_KEY` (or pass `--no-ai` to skip).

Restart the monitor after `--write` so `MarketHolder` reloads the CSV.

| Column | Meaning |
| --- | --- |
| `pair_id` | Local identifier for the matched pair. |
| `exchange_a` / `exchange_b` | Venue tags: `kalshi`, `poly_global`, or `poly_us`. |
| `ticker_a` / `ticker_b` | Venue-native id (Kalshi ticker, Global CLOB token id, or US slug). |
| `side_a` / `side_b` | Outcome team codes bought on each leg (must differ for complementary arb). |
| `market_desc` | Human-readable description of the match. |

Live trading still executes Kalshi ↔ `poly_global` pairs only. Other venue pairs can be logged once present in the CSV.

## Runtime Flow

1. `src.trading_engine.main()` configures logs, creates exchange clients, fetches starting balances, and builds shared queues.
2. `MarketHolder()` loads `data/matchedtable.csv` and initializes empty books for every configured asset.
3. The Kalshi and Polymarket listeners subscribe to market WebSockets and pass messages to their orderbook handlers.
4. The handlers update normalized `Orderbook` instances and enqueue `OrderbookUpdateEvent`s.
5. `StrategyEngine.process_orderbook_updates()` maps each changed asset to its matched asset, skips active/open pairs, and checks opening logic.
6. `ExecutionEngine.process_execution_queue()` posts both opening legs concurrently, creates a `Position` if both fill, or tries to close any lone filled leg.

## Setup

The checked-in virtual environment currently uses Python 3.13.1. For a fresh environment:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` is intentionally limited to direct dependencies imported by `src/` and `demos/`. It includes both the current Polymarket CLOB V2 client used by the bot and the legacy CLOB client still used by `demos/poly_tests.py`.

Create `secrets/.env` and `secrets/kalshi_private_key.txt` before running the live bot. Required environment variables are:

```bash
KALSHI_API_KEY=...

POLY_API_KEY=...
POLY_API_SECRET=...
POLY_API_PASSPHRASE=...
POLY_PRIVATE_KEY=...
POLY_FUNDER_ADDRESS=...
```

Optional variables:

```bash
POLY_SIGNATURE_TYPE=1
POLY_DEFER_EXEC=false
```

`POLY_DEFER_EXEC` is passed through to the Polymarket CLOB client when posting market orders.

## Running

### Opportunity monitor (no orders)

Streams both orderbooks and appends gap lifecycle rows to `logs/opportunities.csv`. Does not place trades. Needs Kalshi credentials for the market WebSocket.

```bash
source .venv/bin/activate
python -m src.monitor_opportunities
```

### Live trading bot

Places live orders when gaps clear the strategy thresholds:

```bash
source .venv/bin/activate
python -m src.trading_engine
```

The bot writes operational logs to `logs/bot.log`, trade attempts to `logs/trades.csv`, and arbitrage gap lifecycle events to `logs/opportunities.csv`.

### Opportunity CSV (`logs/opportunities.csv`)

The monitoring package tracks when a buy-both-yes gap opens, how long it stays open, and when it closes. A gap is logged only when net spread after fees exceeds `0.01` (same threshold as the trading strategy). Rows include:

| Column | Meaning |
| --- | --- |
| `event` | `opened`, `updated`, or `closed` |
| `gap_id` | Stable ID for one open→close episode |
| `pair_id` | Pair id from `matchedtable.csv` |
| `exchange_a` / `exchange_b` | Venue tags for each leg |
| `ticker_a` / `ticker_b` | Venue-native ids |
| `side_a` / `side_b` | Outcome teams |
| `market_desc` | Description from `matchedtable.csv` |
| `game_status` | Kalshi market status (`active`, `closed`, `settled`, …), cached ~60s |
| `ask_a` / `ask_b` | Best ask on each leg |
| `raw_gap` | `1 - ask_a - ask_b` |
| `net_spread` | Gap after estimated fees (Kalshi↔Poly Global fee model when applicable) |
| `potential_win_per_contract` | Net spread (or raw gap if fees unavailable) |
| `potential_win_total` | Per-contract win × available top-of-book volume |
| `duration_seconds` | Seconds since this gap opened |

`src/monitoring/` is intentionally separate from orderbooks: feed it plain `OpportunitySnapshot` values from any source.

## Notes And Limitations

- The strategy is currently hard-coded for opening buy/buy arbitrage only.
- Closing logic for healthy open positions is still a TODO; only one-legged execution failure unwinds are attempted.
- Position state is in memory. Restarting the process loses open-position tracking unless reconciled manually.
- User order streams are scaffolded but not wired into the main loop.
- Fee coefficients, spread threshold, max size, and minimum size live in `StrategyEngine` rather than a config file.
- `requirements.txt` tracks direct imports only; transitive dependencies are resolved by pip when installed.
