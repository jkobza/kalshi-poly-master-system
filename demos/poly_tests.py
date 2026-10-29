import json
import sys

import requests


GAMMA_MARKET_BY_SLUG_URL = "https://gamma-api.polymarket.com/markets/slug/{slug}"
CLOB_MARKET_BY_CONDITION_URL = "https://clob.polymarket.com/clob-markets/{condition_id}"


def parse_json_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return []


def get_polymarket_market(slug="mlb-min-kc-2026-08-05"):
    """
    Fetch a Polymarket market by slug, print CLOB token IDs, and inspect the taker delay flag.
    """
    market_response = requests.get(GAMMA_MARKET_BY_SLUG_URL.format(slug=slug), timeout=10)
    market_response.raise_for_status()
    market = market_response.json()

    question = market["question"]
    condition_id = market["conditionId"]
    outcomes = parse_json_list(market.get("outcomes"))
    token_ids = parse_json_list(market.get("clobTokenIds"))

    clob_response = requests.get(CLOB_MARKET_BY_CONDITION_URL.format(condition_id=condition_id), timeout=10)
    clob_response.raise_for_status()
    clob_market = clob_response.json()

    itode = clob_market.get("itode")
    taker_delay_ms = 250 if itode is True else 0

    print(question)
    print(f"slug: {slug}")
    print(f"condition_id: {condition_id}")
    for outcome, token_id in zip(outcomes, token_ids):
        print(f"{outcome} token: {token_id}")
    print(f"itode: {itode}")
    print(f"taker_delay_ms: {taker_delay_ms}")
    print(f"delay_debug: fd.to={clob_market.get('fd', {}).get('to')} secondsDelay={market.get('secondsDelay')}")


if __name__ == '__main__':
    slug = sys.argv[1] if len(sys.argv) > 1 else "mlb-min-kc-2026-08-05"
    get_polymarket_market(slug)
