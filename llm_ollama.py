import requests
import aiohttp

def call_ollama_mistral(prompt: str):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": "mistral", "prompt": prompt, "stream": False},
        timeout=30
    )
    return response.json().get("response", "").strip()


async def call_ollama_mistral_async(prompt: str):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:11434/api/generate",
            json={"model": "mistral", "prompt": prompt, "stream": False},
            timeout=120,  # Increased timeout for async calls
        ) as response:
            response.raise_for_status()
            data = await response.json()
            return data.get("response", "").strip()