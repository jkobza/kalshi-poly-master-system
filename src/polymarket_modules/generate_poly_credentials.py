from dotenv import load_dotenv
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / 'secrets' / '.env'

load_dotenv(ENV_PATH)


def _required_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required to create a Polymarket client.")
    return value


def _legacy_api_credentials():
    """
    Build unified SDK credentials from the previous CLOB environment variables when present.
    """
    api_key = os.getenv("POLYMARKET_GLOBAL_API_KEY")
    api_secret = os.getenv("POLYMARKET_GLOBAL_API_SECRET")
    api_passphrase = os.getenv("POLYMARKET_GLOBAL_API_PASSPHRASE")
    values = [api_key, api_secret, api_passphrase]

    if not any(values):
        return None
    if not all(values):
        raise ValueError(
            "POLYMARKET_GLOBAL_API_KEY, POLYMARKET_GLOBAL_API_SECRET, and "
            "POLYMARKET_GLOBAL_API_PASSPHRASE must be set together."
        )

    from polymarket import ApiKeyCreds

    return ApiKeyCreds(
        key=api_key,
        secret=api_secret,
        passphrase=api_passphrase,
    )


async def get_poly_client():
    """
    Build a unified Polymarket secure client from environment wallet settings.
    """
    from polymarket import AsyncSecureClient

    wallet = (
        os.getenv("POLYMARKET_GLOBAL_WALLET_ADDRESS")
        or os.getenv("POLYMARKET_GLOBAL_FUNDER_ADDRESS")
    )

    return await AsyncSecureClient.create(
        private_key=_required_env("POLYMARKET_GLOBAL_PRIVATE_KEY"),
        wallet=wallet,
        credentials=_legacy_api_credentials(),
    )
