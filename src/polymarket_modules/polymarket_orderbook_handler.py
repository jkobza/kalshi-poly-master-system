from src.classes.orderbook import Orderbook

def process_poly_orderbook_message(market, data):
    # book event type means a trade was executed or it's the initial snapshot
    # either way, the full book needs to be refreshed

    if data['event_type'] == "book":
        new_book = Orderbook()
        bids = data['bids']
        asks = data['asks']
        asset_id = data['asset_id']

        for b in bids:
            new_book.process_bid(float(b['price']), float(b['size']))

        for a in asks:
            new_book.process_ask(float(a['price']), float(a['size']))

        market.poly_orderbooks[asset_id] = new_book

        # Remove later
        #print(f"[POLY BOOK SNAPSHOT] Ticker: {asset_id} Best Bid: " + str(new_book.best_bid()) + " Best Ask: " + str(new_book.best_ask()))
        return asset_id


    elif data['event_type'] == "price_change":
        last_asset_id = None
        for change in data['price_changes']:
            asset_id = change['asset_id']  # <-- Move back inside the loop
            last_asset_id = asset_id
            if asset_id in market.poly_orderbooks:
                book = market.poly_orderbooks[asset_id]

                prev_best_bid = book.best_bid()
                prev_best_ask = book.best_ask()

                price = float(change['price'])
                size = float(change['size'])

                if change['side'] == 'BUY':
                    book.process_bid(price, size)
                elif change['side'] == 'SELL':
                    book.process_ask(price, size)

                new_best_bid = book.best_bid()
                new_best_ask = book.best_ask()

                # 3. Compare and print
                #if prev_best_bid != new_best_bid:
                    # print(f"[POLY] New Best Bid | {asset_id} | {new_best_bid}")
                #if prev_best_ask != new_best_ask:
                    # print(f"[POLY] New Best Ask | {asset_id} | {new_best_ask}")
        return last_asset_id

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