# src/llm_client.py
import os
from dotenv import load_dotenv
from config import CONFIG

load_dotenv()

class LLMClient:
    def __init__(self, model_name: str | None = None, provider: str | None = None):
        # Model aliasing map (short name -> provider model name)
        model_aliases = {
            "deepseek_reasoner": "deepseek-chat",
            "deepseek_coder": "deepseek-coder",
            "gpt_reasoner": "gpt-4-turbo",
            "gpt-4o-mini": "gpt-4o-mini",
            "gpt4o-mini": "gpt-4o-mini",
        }

        raw_name = model_name or CONFIG["LLM"].get("CG_MODEL")
        self.model_name = model_aliases.get(raw_name, raw_name)

        # Determine provider: explicit param overrides inference
        if provider:
            prov = provider.lower()
        else:
            # Infer provider by model name prefix
            prov = "openai" if (self.model_name or "").startswith("gpt-") or (self.model_name or "").startswith("o3-") else "deepseek"

        self.client_type = prov

        from openai import OpenAI

        if self.client_type == "openai":
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("O3_API_KEY")
            self.client = OpenAI(api_key=api_key)
        else:
            api_key = os.getenv("DEEPSEEK_API_KEY")
            self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    def chat(self, messages, temperature=0.2):
        return self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
        )
