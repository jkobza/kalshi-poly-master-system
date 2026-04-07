# Copied directly from https://docs.polymarket.com/api-reference/authentication
from py_clob_client import PartialCreateOrderOptions
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY
from dotenv import load_dotenv
import os


load_dotenv("../secrets/.env")

client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,  # Polygon mainnet
    key=os.getenv("POLY_PRIVATE_KEY")
)

# Creates new credentials or derives existing ones
credentials = client.create_or_derive_api_creds()

client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=os.getenv("POLY_PRIVATE_KEY"),
    creds=credentials,  # Generated from L1 auth, API credentials enable L2 methods
    signature_type=1,  # signatureType explained below
    funder=os.getenv("POLY_FUNDER_ADDRESS") # funder explained below
)


response = client.create_and_post_order(
    OrderArgs(
        token_id="84007361241758978489330197202827235700289078898880514910472901778979242019662",
        price=0.50,
        size=10,
        side=BUY,
    ),
    PartialCreateOrderOptions(
        tick_size= "0.01",
        neg_risk =False,  # Set to True for multi-outcome markets
)
)

print("Order ID:", response["orderID"])
print("Status:", response["status"])