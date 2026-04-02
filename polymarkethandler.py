from marketholder import MarketHolder
from orderbook import Orderbook

def process_poly_message(market, data):
    # book event type means a trade was executed or it's the initial snapshot
    # either way, the full book needs to be refreshed

    if data['event_type'] == "book":
        new_book = Orderbook()
        bids = data['bids']
        asks = data['asks']
        ticker = data['asset_id']

        for b in bids:
            new_book.process_bid(float(b['price']), float(b['size']))

        for a in asks:
            new_book.process_ask(float(a['price']), float(a['size']))

        market.poly_orderbooks[ticker] = new_book

        # Remove later
        print(f"[POLY BOOK SNAPSHOT] Ticker: {ticker} Best Bid: " + str(new_book.best_bid()) + " Best Ask: " + str(new_book.best_ask()))


    elif data['event_type'] == "price_change":

        for change in data['price_changes']:
            asset_id = change['asset_id']

            if asset_id in market.poly_orderbooks:
                book = market.poly_orderbooks[asset_id]
                price = float(change['price'])
                size = float(change['size'])

                # change correct side of the book
                if change['side'] == 'BUY':
                    book.process_bid(price, size)

                elif change['side'] == 'SELL':
                    book.process_ask(price, size)

                print(f"[POLY] {asset_id} | Best Bid: {book.best_bid()} | Best Ask: {book.best_ask()}")

def get_poly_market_subscription_message(market):
    # Goes through each asset in the market and adds it to initial polymarket message
    assetIds = []
    for i in market.poly_orderbooks.keys():
        assetIds.append(str(i))
    print(assetIds)
    message = {
        "assets_ids": assetIds,
        "type": "market",
        "custom_feature_enabled": False
    }
    return message