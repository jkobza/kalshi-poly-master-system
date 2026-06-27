import os
from pathlib import Path
import requests
import datetime
import base64
from urllib.parse import urlparse
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding
from dotenv import load_dotenv
from kalshi_python_async import Configuration, KalshiClient
import asyncio

# Configuration
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Build absolute paths
ENV_PATH = PROJECT_ROOT / 'secrets' / '.env'
PRIVATE_KEY_PATH = PROJECT_ROOT / 'secrets' / 'kalshi_private_key.txt'

load_dotenv(ENV_PATH)
URL = 'https://api.elections.kalshi.com/trade-api/v2/portfolio/balance'  # or 'https://api.elections.kalshi.com/trade-api/v2' for production

def kalshi_load_private_key(key_path):
    """
    Load the PEM private key used to sign authenticated Kalshi requests.
    """
    with open(key_path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())

def kalshi_create_signature(timestamp, method, path):
    """
    Create the base64-encoded PSS/SHA-256 signature Kalshi expects for one request path.
    """
    # Strip query parameters before signing
    path_without_query = path.split('?')[0]
    message = f"{timestamp}{method}{path_without_query}".encode('utf-8')
    signature = kalshi_load_private_key(PRIVATE_KEY_PATH).sign(
        message,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode('utf-8')

def get_kalshi_headers(url, method="GET"):
    """Return the headers needed to authenticate with the Kalshi API."""
    timestamp = str(int(datetime.datetime.now().timestamp() * 1000))
    path = urlparse(url).path
    signature = kalshi_create_signature(timestamp, method.upper(), path)

    headers = {
        'KALSHI-ACCESS-KEY': os.getenv('KALSHI_API_KEY'),
        'KALSHI-ACCESS-SIGNATURE': signature,
        'KALSHI-ACCESS-TIMESTAMP': timestamp
    }
    return headers


def send_auth_kalshi_message(url):
    """
    Send a simple authenticated GET request to Kalshi and return the raw requests response.
    """
    headers = get_kalshi_headers(url)
    return requests.get(url, headers=headers)

def get_kalshi_client():
    """
    Build a KalshiClient configured with the project API key and private key file.
    """

    config = Configuration(
        host="https://api.elections.kalshi.com/trade-api/v2"
    )

    # For authenticated requests
    # Read private key from file
    with open(PRIVATE_KEY_PATH, "r") as f:
        config.private_key_pem = f.read()


    config.api_key_id = os.getenv('KALSHI_API_KEY')


    # Initialize the client
    client = KalshiClient(config)

    return client
