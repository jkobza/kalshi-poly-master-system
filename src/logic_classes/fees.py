from src.util.enums import Exchange

KALSHI_MAX_FEE_RATE = 0.07
POLYMARKET_GLOBAL_MAX_FEE_RATE = 0.07
POLYMARKET_US_MAX_FEE_RATE = 0.06

def calculate_taker_fee(exchange: Exchange, price):
    if exchange == Exchange.KALSHI:
        fee = fee_formula(fee_rate=KALSHI_MAX_FEE_RATE, price=price)
    if exchange == Exchange.POLYMARKET_GLOBAL: 
        fee = fee_formula(fee_rate=POLYMARKET_GLOBAL_MAX_FEE_RATE, price=price)
    elif exchange == Exchange.POLYMARKET_US:
        fee = fee_formula(fee_rate=POLYMARKET_US_MAX_FEE_RATE, price=price)
    return fee

def calculate_total_taker_fee(exchange: Exchange, price, size):
    return calculate_taker_fee(exchange, price) * size

def calculate_taker_balance_delta(exchange:Exchange, price, size):
    return price * size + calculate_total_taker_fee(exchange, price, size)
def calculate_arb_spread_(kalshi_price, poly_price):
    return
def fee_formula(fee_rate, price):
    return fee_rate * price * (1-price)

def calculate_spread_net_fees(exchange_a: Exchange, exchange_b: Exchange, price_a, price_b):
    return 1 - price_a - price_b - calculate_taker_fee(exchange_a, price_a) - calculate_taker_fee(exchange_b, price_b)