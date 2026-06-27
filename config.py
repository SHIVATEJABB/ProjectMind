import os
from openai import OpenAI

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

print("API Key exists:", OPENROUTER_API_KEY is not None)
print("API Key length:", len(OPENROUTER_API_KEY) if OPENROUTER_API_KEY else 0)
print("First 10 chars:", OPENROUTER_API_KEY[:10] if OPENROUTER_API_KEY else "None")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

MODEL_NAME = "google/gemini-2.5-flash"
