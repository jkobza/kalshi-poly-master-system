# Architecture Refactor Notes

These notes capture the intended direction for modularizing the trading system. The goal is to move from a single arbitrage bot into a strategy-agnostic trading platform where market data, strategy logic, risk checks, execution, and portfolio state have clean boundaries.

## Target Shape

```text
Exchange Ingestors
  Kalshi market data
  Polymarket market data
  User/order streams

        -> normalized events

Market Data Bus / Event Router

        ->

Strategies
  ArbStrategy
  Future strategy A
  Future strategy B

        -> proposed intents

Risk Manager

        -> approved/rejected execution plans

Execution Manager

        -> exchange adapters

Kalshi Adapter / Polymarket Adapter

        -> fills, rejects, balance updates, order state

Portfolio / Position / Order State

        -> normalized execution events

Strategies + Risk Manager + Logs + Monitoring
```

## Core Principle

Strategies should not place orders directly.

A strategy should emit an intent, such as:

```text
I want to buy 10 of Kalshi market X at <= 0.42
and buy 10 of Polymarket token Y at <= 0.55
as one paired arbitrage package
because expected net spread is 0.018.
```

The risk and execution layer decides whether that is allowed, how it should be executed, and what happens if execution is imperfect.

## Core Domain Objects

Use normalized objects that can work across all strategies and exchanges:

```text
MarketDataEvent
Signal
OrderIntent
ExecutionPlan
OrderEvent
PositionEvent
```

Each event should carry enough context to trace it through the system:

```text
strategy_id
correlation_id
exchange
asset_id
market_pair_id
timestamp
```

## Strategy Layer

The arbitrage strategy should own:

- Opportunity detection.
- Spread calculation.
- Strategy-specific desired sizing.
- Emitting paired `OrderIntent`s.
- Reacting to execution results.

It should not own:

- Raw exchange clients.
- Balance mutation.
- CSV logging.
- Final risk approval.
- Order retries.
- Unwind mechanics.
- Global active order locks.

The arb strategy should receive events such as:

```text
ExecutionAccepted
ExecutionRejected
LegFilled
ExecutionFailed
PositionOpened
UnwindStarted
UnwindComplete
```

## Risk Manager

The risk manager should be shared across all strategies.

It should answer questions like:

- Is this strategy allowed to trade this market?
- Is the book fresh enough?
- Is expected edge large enough after fees, slippage, and latency?
- Are balances sufficient?
- Is this pair already active or open?
- Does this exceed max exposure?
- Does this violate per-exchange or per-market limits?
- Does this conflict with another strategy?
- Should this be paper-traded, live-traded, or rejected?

This is where multiple strategies are prevented from fighting each other.

## Execution Manager

The execution manager should own mechanics:

- Convert approved plans into exchange orders.
- Submit legs.
- Track order lifecycle.
- Handle partial fills and lone fills.
- Unwind failed paired trades.
- Emit normalized execution events.
- Keep exchange-specific quirks out of strategies.

Exchange adapters should hide API details behind a consistent interface:

```text
KalshiAdapter.place_order(...)
PolymarketAdapter.place_order(...)
```

Both should return normalized order/execution events.

## Execution State Machine

Paired execution should eventually become an explicit state machine:

```text
SIGNALLED
  -> RISK_APPROVED
  -> SUBMITTING
  -> BOTH_FILLED
  -> OPEN

SUBMITTING
  -> ONE_LEG_FILLED
  -> UNWINDING
  -> FLAT / FAILED

SUBMITTING
  -> REJECTED / KILLED
```

This makes delayed, partial, failed, and restart cases easier to reason about.

## Market Data Delay And Polymarket Sports Markets

Some Polymarket sports markets can have a roughly one-second data delay. Treat that as market data metadata, not as a hard-coded special case inside the arb strategy.

At the market/exchange/asset level, track metadata like:

```text
MarketMetadata
  exchange = POLYMARKET
  asset_id = ...
  category = SPORTS
  market_data_delay_ms = 1000
  is_delayed = true
```

Normalized orderbook updates should carry freshness information:

```text
OrderbookUpdateEvent
  exchange
  asset_id
  best_bid
  best_ask
  received_at
  exchange_event_time
  effective_at
  delay_ms
  category
```

For delayed sports markets:

```text
effective_at ~= received_at - 1000ms
```

The strategy can include latency in its signal:

```text
ArbSignal
  expected_spread = 0.018
  max_leg_delay_ms = 1000
  stale_leg = POLYMARKET
  confidence = LOWER
```

The risk manager should enforce delay-aware policy:

- Require larger edge for delayed markets.
- Reduce size for delayed markets.
- Require deeper top-of-book liquidity.
- Reject if the book is too stale.
- Potentially disable delayed sports markets during high-volatility live-game windows unless explicitly enabled.

The principle:

```text
Latency belongs in market data metadata and risk policy, not hard-coded strategy branching.
```

## Suggested Module Layout

```text
src/
  app/
    runtime.py
    config.py

  domain/
    events.py
    orders.py
    positions.py
    markets.py
    enums.py

  market_data/
    bus.py
    orderbook_store.py
    normalizers.py

  exchanges/
    kalshi/
      market_data.py
      execution.py
      user_stream.py
    polymarket/
      market_data.py
      execution.py
      user_stream.py

  strategies/
    base.py
    arb/
      strategy.py
      models.py

  risk/
    manager.py
    checks.py
    limits.py

  execution/
    manager.py
    planner.py
    state_machine.py

  portfolio/
    position_store.py
    ledger.py
    reconciliation.py

  observability/
    logging.py
    trade_log.py
    metrics.py
```

The exact folders can change. The key dependency direction should stay stable:

```text
exchange adapters -> emit normalized events
strategies -> consume market events and emit intents
risk -> approve/reject intents
execution -> execute approved plans
portfolio -> source of truth for positions, orders, balances
```

## Recommended Refactor Order

1. Extract config, fee, and sizing logic into shared modules.
2. Add tests for orderbook updates, fee math, sizing, and signal generation.
3. Turn the current arb logic into a strategy module that consumes normalized market events and emits `OrderIntent`s.
4. Introduce exchange adapters around existing Kalshi and Polymarket API calls.
5. Split the current market holder into a static market catalog and live market state/orderbook store.
6. Add the shared risk manager.
7. Add a persistent position/order ledger, likely SQLite first.
8. Add startup reconciliation from exchange user/order/position streams.
9. Move paired execution and unwind logic into an explicit execution state machine.
10. Add closing/redeem logic after the core lifecycle is reliable.

