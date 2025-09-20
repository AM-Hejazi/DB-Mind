# src/llm_client.py
import os
from dotenv import load_dotenv
from config import CONFIG

load_dotenv()

class LLMClient:
    def __init__(self, model_name: str | None = None):
        model_aliases = {
            "deepseek_reasoner": "deepseek-chat","deepseek-coder"
            "gpt_reasoner": "gpt-4-turbo",
        }
        self.model_name = model_aliases.get(CONFIG["LLM"]["CG_MODEL"], CONFIG["LLM"]["CG_MODEL"])
        model_aliases = {
      # DeepSeek
                "deepseek_reasoner": "deepseek-chat",
                "deepseek_coder": "deepseek-coder",

      # OpenAI
                "gpt_reasoner": "gpt-4-turbo",
                "gpt-4o-mini": "gpt-4o-mini",  # NEW – lets SR use the lighter 4-o model
                "gpt4o-mini": "gpt-4o-mini",  # alt spelling for safety
        }

        raw_name = model_name or CONFIG["LLM"]["CG_MODEL"]
        self.model_name = model_aliases.get(raw_name, raw_name)

        if self.model_name.startswith("gpt-"):
            from openai import OpenAI
            self.client_type = "openai"
            self.client = OpenAI(api_key=os.getenv("O3_API_KEY"))

        else:
            from openai import OpenAI  # deepseek-compatible
            self.client_type = "deepseek"
            self.client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")

    def chat(self, messages, temperature=0.2):
        if self.client_type == "openai":
            return self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature
            )
        else:
            return self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature
            )
