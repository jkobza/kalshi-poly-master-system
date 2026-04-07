# Kalshi/Polymarket Arbitrage System

---

## Overview

This is a system designed to track polymarket and kalshi orderbooks
and execute trades when books tracking the same event create an arbitrage opportunity (net of fees). 

## File/Object Descriptions

---
### `data/matchedtable.csv`

This is where matched orderbooks are listed so that they can be tracked. 
The columns are as follows:

| market_id                        |poly_id|kalshi_id| market_desc                   |
|----------------------------------|---|---|-------------------------------|
| 0-indexed id of matched markets  | Polymarket event token id|Kalshi market ticker| Description of matched market |
I don't really know why I put in the market ID? Maybe will delete later. 

In the future, I want (need) a way to programmatically detect/fill this spreadsheet with many markets
### Marketholder

The MarketHolder class defines an object that contains all the market pairs in the `data/matchedtable.csv`
It is a singleton which can be accessed by simply calling MarketHolder(). The MarketHolder contains 4 instance variables
that hold the information from matchedTable:
 - `kalshi_orderbooks = {}` This dictionary maps a kalshi market ticker to its `Orderbook()` object. 
 - `poly_orderbooks = {}` This dictionary maps a polymarket token id to its `Orderbook()` object. 
 - `k_to_p_map = defaultdict(list)` This defaultdict maps a kalshi market ticker to its matched polymarket token id.
 - `p_to_k_map = defaultdict(list)`This defaultdict maps a polymarket token id to its matched kalshi market ticker.

Note the respective k-to-p and p-to-k dictionaries are defaultdicts that support one to many mappings. (In case one
a book on one platform has multiple identical ones on the other platform)

### Orderbook

` i9`
