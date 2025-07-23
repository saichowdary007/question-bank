import os
import logging
from typing import Optional

import requests
import aiohttp

# Connection‑pool & retry helpers
from tenacity import retry, stop_after_attempt, wait_exponential  # pip install tenacity

# ---------------------------------------------------------------------------
# Ollama endpoint configuration
# ---------------------------------------------------------------------------

# ``OLLAMA_HOST`` may be provided in **two** forms:
#   1. Bare hostname (e.g. ``ollama`` or ``localhost``)
#   2. Full URL including scheme/port (e.g. ``http://ollama:11434``)
#
# The previous implementation blindly prefixed the value with ``http://`` and
# appended the default port which resulted in invalid URLs like
# ``http://http://ollama:11434:11434`` when the full form was provided via
# environment variables. The helper below normalises the input to build a
# valid ``/api/generate`` endpoint irrespective of the supplied format.

def _build_ollama_url() -> str:
    host_env = os.getenv("OLLAMA_HOST", "localhost").rstrip("/")

    # If scheme is already present we assume the host contains the correct
    # network location (hostname *and* optional port).
    if host_env.startswith(("http://", "https://")):
        base = host_env  # full URL provided
    else:
        base = f"http://{host_env}:11434"

    return f"{base}/api/generate"


# Expose for other modules (mainly for debug/logging convenience)
OLLAMA_URL = _build_ollama_url()

# Timeout (in seconds) for requests to the Ollama server. Can be overridden
# at runtime with the environment variable `OLLAMA_REQUEST_TIMEOUT` so that
# deployments with slower hardware (e.g. Docker Desktop on laptops) can use
# higher values without modifying the source code.
OLLAMA_REQUEST_TIMEOUT = int(os.getenv("OLLAMA_REQUEST_TIMEOUT", "120"))

# ---------------------------------------------------------------------------
# Re‑use a single requests.Session so synchronous calls benefit from HTTP
# keep‑alive.  This avoids ~50 ms TCP/TLS setup cost on every request.
# ---------------------------------------------------------------------------
_sync_session: Optional[requests.Session] = None


def _get_sync_session() -> requests.Session:
    """Return a lazily‑initialised shared ``requests`` session."""
    global _sync_session
    if _sync_session is None:
        _sync_session = requests.Session()
        # Slightly enlarge the default pool size for bursty workloads
        _sync_session.mount("http://", requests.adapters.HTTPAdapter(pool_maxsize=20))
        _sync_session.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=20))
    return _sync_session

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def call_ollama_mistral(prompt: str):
    try:
        session = _get_sync_session()
        response = session.post(
            OLLAMA_URL,
            json={"model": "mistral", "prompt": prompt, "stream": False},
            timeout=OLLAMA_REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Error calling ollama at {OLLAMA_URL}: {e}")
        raise


# ---------------------------------------------------------------------------
# Shared aiohttp session – Step-1 optimisation
# ---------------------------------------------------------------------------

_aio_session: Optional[aiohttp.ClientSession] = None


async def _get_session() -> aiohttp.ClientSession:
    """Return a (lazily-initialised) shared ``aiohttp`` session."""
    global _aio_session
    if _aio_session is None or _aio_session.closed:
        _aio_session = aiohttp.ClientSession()
    return _aio_session


async def close_async_session() -> None:  # used on FastAPI shutdown
    global _aio_session
    if _aio_session and not _aio_session.closed:
        await _aio_session.close()


async def call_ollama_mistral_async(prompt: str):
    """Asynchronously call the Ollama endpoint using a shared HTTP session."""
    try:
        session = await _get_session()
        async with session.post(
            OLLAMA_URL,
            json={"model": "mistral", "prompt": prompt, "stream": False},
            timeout=aiohttp.ClientTimeout(total=OLLAMA_REQUEST_TIMEOUT),
        ) as response:
            response.raise_for_status()
            data = await response.json()
            return data.get("response", "").strip()
    except Exception as e:
        logging.error(f"❌ Error calling ollama async at {OLLAMA_URL}: {e}")
        raise

# ---------------------------------------------------------------------------
# Optional cleanup for unit tests / graceful shutdown
# ---------------------------------------------------------------------------
def close_sync_session() -> None:
    """Close the shared ``requests`` session if it exists."""
    global _sync_session
    if _sync_session is not None:
        _sync_session.close()
        _sync_session = None