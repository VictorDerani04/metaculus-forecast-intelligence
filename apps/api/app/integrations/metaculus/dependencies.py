import os
from collections.abc import Iterator

import httpx

from app.integrations.metaculus.client import MetaculusClient


def get_metaculus_client() -> Iterator[MetaculusClient]:
    with httpx.Client() as http:
        yield MetaculusClient(token=os.getenv('METACULUS_API_TOKEN', ''), http=http)
