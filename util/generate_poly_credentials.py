# Copied directly from https://docs.polymarket.com/api-reference/authentication
from py_clob_client import PartialCreateOrderOptions
from py_clob_client.client import ClobClient
from dotenv import load_dotenv
import os
from pathlib import Path

def get_poly_client():
    BASE_DIR = Path(__file__).resolve().parent.parent
    # Build absolute paths
    ENV_PATH = BASE_DIR / 'secrets' / '.env'
    load_dotenv(ENV_PATH)

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
        funder=os.getenv("POLY_FUNDER_ADDRESS")  # funder explained below
    )
    return client

