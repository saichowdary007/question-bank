import requests
import aiohttp
import os
import logging

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")
OLLAMA_URL = f"http://{OLLAMA_HOST}:11434/api/generate"

def call_ollama_mistral(prompt: str):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": "mistral", "prompt": prompt, "stream": False},
            timeout=30
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
                timeout=120,  # Increased timeout for async calls
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("response", "").strip()
    except Exception as e:
        logging.error(f"❌ Error calling ollama async at {OLLAMA_URL}: {e}")
        raise