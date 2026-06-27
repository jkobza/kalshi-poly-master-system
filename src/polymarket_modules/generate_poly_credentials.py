from py_clob_client_v2 import SignatureTypeV2
from py_clob_client_v2.client import ClobClient
from dotenv import load_dotenv
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / 'secrets' / '.env'

load_dotenv(ENV_PATH)

def get_poly_signature_type():
    """
    Read and validate the configured numeric Polymarket CLOB signature type.
    """
    signature_type = int(os.getenv("POLY_SIGNATURE_TYPE", "1"))
    if signature_type not in {0, 1, 2}:
        raise ValueError(
            f"POLY_SIGNATURE_TYPE must be 0, 1, or 2 for CLOB V2 order posting. Got {signature_type}."
        )
    return signature_type


from py_clob_client_v2 import ClobClient, SignatureTypeV2, ApiCreds
import os


def get_poly_client():
    """
    Build a Polymarket CLOB V2 client from environment API credentials and wallet settings.
    """
    creds = ApiCreds(
        api_key=os.getenv("POLY_API_KEY"),
        api_secret=os.getenv("POLY_API_SECRET"),
        api_passphrase=os.getenv("POLY_API_PASSPHRASE")
    )

    client = ClobClient(
        host="https://clob.polymarket.com",
        chain_id=137,
        key=os.getenv("POLY_PRIVATE_KEY"),
        creds=creds,
        signature_type=SignatureTypeV2.POLY_1271,
        funder=os.getenv("POLY_FUNDER_ADDRESS")
    )

    return client
