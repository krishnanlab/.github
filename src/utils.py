import os
from datetime import datetime
from typing import Optional, Tuple

import requests
from requests.exceptions import RequestException


def join_url(*parts: Tuple[str]) -> str:
    return "/".join(parts)


def try_get_json(url: str, session: Optional[requests.Session] = None):
    get = requests.get if session is None else session.get
    with get(url) as r:
        if not r.ok:
            raise RequestException(f"{r!r}: {url}\n{r.text}")
        content = r.json()
    return content


def get_current_time_str(date_only: bool = False) -> str:
    format = "%Y-%m-%d" if date_only else "%Y-%m-%d_%H-%M-%S"
    return datetime.strftime(datetime.now(), format)


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path
