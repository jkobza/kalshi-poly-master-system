from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.state_classes.orderbook import Orderbook
from src.util.enums import Exchange


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MATCHED_TABLE_PATH = PROJECT_ROOT / "data" / "matchedtable.csv"

# CSV exchange tags → runtime Exchange enum used by orderbook update events.
CSV_EXCHANGE_TO_ENUM = {
    "kalshi": Exchange.KALSHI,
    "poly_global": Exchange.POLYMARKET,
    "polymarket": Exchange.POLYMARKET,  # legacy alias
    # poly_us will get its own enum/books when the US listener lands
    "poly_us": Exchange.POLYMARKET,
}


@dataclass(frozen=True)
class MatchedPair:
    """One complementary arb pair loaded from matchedtable.csv."""

    pair_id: str
    exchange_a: str
    exchange_b: str
    ticker_a: str
    ticker_b: str
    side_a: str
    side_b: str
    market_desc: str = ""

    def other_leg(self, exchange: str, ticker: str) -> tuple[str, str] | None:
        """Return (exchange, ticker) for the opposite leg, or None if this pair doesn't contain the given leg."""
        if exchange == self.exchange_a and ticker == self.ticker_a:
            return self.exchange_b, self.ticker_b
        if exchange == self.exchange_b and ticker == self.ticker_b:
            return self.exchange_a, self.ticker_a
        return None

    def contains(self, exchange: str, ticker: str) -> bool:
        return (
            (exchange == self.exchange_a and ticker == self.ticker_a)
            or (exchange == self.exchange_b and ticker == self.ticker_b)
        )

    @property
    def is_kalshi_poly_global(self) -> bool:
        venues = {self.exchange_a, self.exchange_b}
        return "kalshi" in venues and ("poly_global" in venues or "polymarket" in venues)

    def kalshi_ticker(self) -> str | None:
        if self.exchange_a == "kalshi":
            return self.ticker_a
        if self.exchange_b == "kalshi":
            return self.ticker_b
        return None

    def poly_ticker(self) -> str | None:
        for ex, ticker in ((self.exchange_a, self.ticker_a), (self.exchange_b, self.ticker_b)):
            if ex in {"poly_global", "polymarket", "poly_us"}:
                return ticker
        return None


class MarketHolder:
    _instance = None
    _initialized = False

    def __new__(self, *args, **kwargs):
        """
        Return the shared MarketHolder instance so all components see the same books and mappings.
        """
        if self._instance is None:
            self._instance = super(MarketHolder, self).__new__(self)
        return self._instance

    def __init__(self):
        """
        Load matched markets once and initialize empty Kalshi/Polymarket orderbooks plus lookup maps.
        """
        if self._initialized:
            return
        self.kalshi_orderbooks: dict[str, Orderbook] = {}
        self.poly_orderbooks: dict[str, Orderbook] = {}
        self.pairs: list[MatchedPair] = []
        # (exchange_tag, ticker) -> pairs that include this leg
        self.pairs_by_leg: defaultdict[tuple[str, str], list[MatchedPair]] = defaultdict(list)
        # Back-compat maps for callers that still expect kalshi ↔ poly id lists
        self.p_to_k_map: defaultdict[str, list[str]] = defaultdict(list)
        self.k_to_p_map: defaultdict[str, list[str]] = defaultdict(list)
        self.pair_descriptions: dict[tuple[str, str], str] = {}

        df = pd.read_csv(MATCHED_TABLE_PATH)
        print(df)
        for _, row in df.iterrows():
            pair = self._row_to_pair(row)
            if pair is None:
                continue
            self.pairs.append(pair)
            self._register_pair(pair)
        self._initialized = True

    @staticmethod
    def _normalize_exchange(value: str) -> str:
        tag = str(value or "").strip().lower()
        if tag == "polymarket":
            return "poly_global"
        return tag

    def _row_to_pair(self, row) -> MatchedPair | None:
        """
        Support the new venue-aware schema and the legacy poly_id/kalshi_id schema.
        """
        columns = {str(c).strip().lower() for c in row.index}

        if {"exchange_a", "exchange_b", "ticker_a", "ticker_b"} <= columns:
            exchange_a = self._normalize_exchange(row["exchange_a"])
            exchange_b = self._normalize_exchange(row["exchange_b"])
            ticker_a = str(row["ticker_a"]).strip()
            ticker_b = str(row["ticker_b"]).strip()
            if not ticker_a or not ticker_b or ticker_a == "nan" or ticker_b == "nan":
                return None
            return MatchedPair(
                pair_id=str(row.get("pair_id", row.get("market_id", "")) or "").strip(),
                exchange_a=exchange_a,
                exchange_b=exchange_b,
                ticker_a=ticker_a,
                ticker_b=ticker_b,
                side_a=str(row.get("side_a", "") or "").strip(),
                side_b=str(row.get("side_b", "") or "").strip(),
                market_desc=str(row.get("market_desc", "") or "").strip(),
            )

        # Legacy: market_id,poly_id,kalshi_id,market_desc
        if {"poly_id", "kalshi_id"} <= columns:
            poly_id = str(row["poly_id"]).strip()
            kalshi_id = str(row["kalshi_id"]).strip()
            if not poly_id or not kalshi_id or poly_id == "nan" or kalshi_id == "nan":
                return None
            desc = str(row.get("market_desc", "") or "").strip()
            side_poly, side_kalshi = "", ""
            # Best-effort parse: "SD Polymarket - TOR Kalshi (...)"
            if " - " in desc:
                left, right = desc.split(" - ", 1)
                side_poly = left.split()[0] if left.split() else ""
                side_kalshi = right.split()[0] if right.split() else ""
            return MatchedPair(
                pair_id=str(row.get("market_id", "") or "").strip(),
                exchange_a="kalshi",
                exchange_b="poly_global",
                ticker_a=kalshi_id,
                ticker_b=poly_id,
                side_a=side_kalshi,
                side_b=side_poly,
                market_desc=desc,
            )

        return None

    def _register_pair(self, pair: MatchedPair) -> None:
        self._ensure_book(pair.exchange_a, pair.ticker_a)
        self._ensure_book(pair.exchange_b, pair.ticker_b)
        self.pairs_by_leg[(pair.exchange_a, pair.ticker_a)].append(pair)
        self.pairs_by_leg[(pair.exchange_b, pair.ticker_b)].append(pair)

        kalshi_id = pair.kalshi_ticker()
        poly_id = pair.poly_ticker()
        if kalshi_id and poly_id:
            self.k_to_p_map[kalshi_id].append(poly_id)
            self.p_to_k_map[poly_id].append(kalshi_id)
            self.pair_descriptions[(kalshi_id, poly_id)] = pair.market_desc

    def _ensure_book(self, exchange: str, ticker: str) -> None:
        if exchange == "kalshi":
            if ticker not in self.kalshi_orderbooks:
                self.kalshi_orderbooks[ticker] = Orderbook()
            return
        # poly_global / poly_us / legacy polymarket share the poly book map for now
        if ticker not in self.poly_orderbooks:
            self.poly_orderbooks[ticker] = Orderbook()

    def pairs_for(self, exchange: Exchange | str, ticker: str) -> list[MatchedPair]:
        """Return every matched pair that includes this exchange/ticker leg."""
        if isinstance(exchange, Exchange):
            if exchange == Exchange.KALSHI:
                tags = ["kalshi"]
            else:
                tags = ["poly_global", "polymarket", "poly_us"]
        else:
            tags = [self._normalize_exchange(exchange)]
        out: list[MatchedPair] = []
        seen: set[str] = set()
        for tag in tags:
            for pair in self.pairs_by_leg.get((tag, ticker), []):
                if pair.pair_id in seen:
                    continue
                seen.add(pair.pair_id)
                out.append(pair)
        return out

    def get_pair_description(self, kalshi_id: str, poly_id: str) -> str:
        """
        Return the matchedtable description for a Kalshi/Polymarket pair, or an empty string.
        """
        return self.pair_descriptions.get((kalshi_id, poly_id), "")

    def get_orderbook(self, exchange: Exchange | str, asset_id: str) -> Orderbook | None:
        """
        Return the stored orderbook for an exchange/asset pair, or None for an unsupported exchange.
        """
        if isinstance(exchange, str):
            exchange = CSV_EXCHANGE_TO_ENUM.get(self._normalize_exchange(exchange), Exchange.POLYMARKET)
        if exchange == Exchange.KALSHI:
            return self.kalshi_orderbooks.get(asset_id)
        if exchange == Exchange.POLYMARKET:
            return self.poly_orderbooks.get(asset_id)
        return None
