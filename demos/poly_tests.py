import requests
import json
from py_clob_client.client import ClobClient


def get_polymarket_market():
    # 1. Add headers to bypass the block
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    # 2. Add a timeout so it fails immediately if blocked again
    response = requests.get(
        "https://gamma-api.polymarket.com/markets/slug/mlb-atl-laa-2026-04-06",
        headers=headers,
        timeout=10
    )
    market = response.json()
    print(market)
    print(market["question"])

    clob_tokens = json.loads(market["clobTokenIds"])
    market_outcomes = json.loads(market["outcomes"])
    yes = clob_tokens[0]

    # 3. Use the parsed list, not the raw JSON string
    no = clob_tokens[1]
    print(f"{market_outcomes[0]} token: {clob_tokens[0]}")
    print(f"{market_outcomes[1]} token: {clob_tokens[1]}")

    client = ClobClient("https://clob.polymarket.com", chain_id=137)
    book = client.get_order_book(no)
    print("Best bid:", book.bids[-1])
    print("Best ask:", book.asks[-1])
    print("Tick size:", book.tick_size)


if __name__ == '__main__':
    get_polymarket_market()