import requests
import aiohttp
import os
import logging

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

def call_ollama_mistral(prompt: str):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": "mistral", "prompt": prompt, "stream": False},
            timeout=OLLAMA_REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Error calling ollama at {OLLAMA_URL}: {e}")
        raise


async def call_ollama_mistral_async(prompt: str):
    try:
        async with aiohttp.ClientSession() as session:
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