import requests
import aiohttp
import os
import logging

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")
OLLAMA_URL = f"http://{OLLAMA_HOST}:11434/api/generate"

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