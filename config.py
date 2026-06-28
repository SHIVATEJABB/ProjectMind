import os
from openai import OpenAI
from dotenv import load_dotenv

# Load local environment variables from .env if present
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Fallback to Streamlit secrets if not found in environment variables
if not OPENROUTER_API_KEY:
    try:
        import streamlit as st
        if "OPENROUTER_API_KEY" in st.secrets:
            OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
    except Exception:
        pass

# Ensure API key is present
if not OPENROUTER_API_KEY:
    raise RuntimeError(
        "OPENROUTER_API_KEY is missing. Please provide it in a .env file locally "
        "or define it in Streamlit Secrets for cloud deployment."
    )

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

MODEL_NAME = "google/gemini-2.5-flash"
