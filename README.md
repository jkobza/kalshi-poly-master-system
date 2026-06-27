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
| `src/kalshi_modules/` | Kalshi credentials, WebSocket listener, subscription payloads, and orderbook message handling. |
| `src/polymarket_modules/` | Polymarket credentials, WebSocket listener, subscription payloads, balance fetches, and orderbook message handling. |
| `src/util/enums.py` | Shared enums for exchanges, order sides, order status, and position status. |
| `demos/` | Small manual WebSocket/API experiments. These are not part of the main bot loop. |
| `logs/` | Runtime logs and trade CSV output. |
| `secrets/` | Local credentials. This directory is ignored by git. |

## Matched Markets

`data/matchedtable.csv` is the source of truth for markets the bot watches. `MarketHolder` loads it once at startup and creates one empty `Orderbook` per listed Kalshi ticker and Polymarket token ID.

| Column | Meaning |
| --- | --- |
| `market_id` | Local identifier for the matched row. It is currently informational. |
| `poly_id` | Polymarket CLOB token ID to subscribe to and trade. |
| `kalshi_id` | Kalshi market ticker to subscribe to and trade. |
| `market_desc` | Human-readable description of the match. |

The lookup maps support one-to-many matches, though the current strategy uses the first match returned for an update.

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

The source also imports `kalshi_python_async` and `py_clob_client_v2`. Make sure those exchange client packages are available in the environment if they are not installed by your local requirements flow.

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

From the project root, activate the environment and run the module entrypoint:

```bash
source .venv/bin/activate
python -m src.trading_engine
```

The bot writes operational logs to `logs/bot.log` and trade attempts to `logs/trades.csv`.

## Notes And Limitations

- The strategy is currently hard-coded for opening buy/buy arbitrage only.
- Closing logic for healthy open positions is still a TODO; only one-legged execution failure unwinds are attempted.
- Position state is in memory. Restarting the process loses open-position tracking unless reconciled manually.
- User order streams are scaffolded but not wired into the main loop.
- Fee coefficients, spread threshold, max size, and minimum size live in `StrategyEngine` rather than a config file.
- `requirements.txt` contains many unrelated packages from the development environment; it is not a minimal production dependency list.
