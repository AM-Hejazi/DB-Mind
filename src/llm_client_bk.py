# src/llm_client.py
import os
from dotenv import load_dotenv
from config import CONFIG
from openai import OpenAI

load_dotenv()

class LLMClient:
    def __init__(self):
        model_aliases = {
            "deepseek_reasoner": "deepseek-chat",
            "gpt_reasoner": "gpt-4-turbo",
            "deepseek-coder": "deepseek-coder",
            "o3-pro": "o3-pro"  # must match your provider's expected model name
        }

        self.model_name = model_aliases.get(CONFIG["LLM"]["EV_MODEL"], CONFIG["LLM"]["CG_MODEL"])

        if self.model_name == "o3-pro":
            self.client_type = "o3"
            self.client = OpenAI(
                api_key=os.getenv("O3_API_KEY"),
            )

        elif self.model_name.startswith("gpt-"):
            self.client_type = "openai"
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        else:
            self.client_type = "deepseek"
            self.client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com"
            )

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
