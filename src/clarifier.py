import os
from openai import OpenAI
from dotenv import load_dotenv
import time
from src.logger import global_logger as logger
from config import CONFIG

load_dotenv()
api_key = os.getenv("DEEPSEEK_API_KEY")
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

def load_prompt_template():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prompt_path = os.path.join(base_dir, "prompts", "QC.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

def build_prompt(user_question, schema_context):
    template = load_prompt_template()
    return template.replace("{QUESTION}", user_question).replace("{DATABASE_SCHEMA}", schema_context or "No schema available.")

def clarify_question(user_question, schema_context=None):
    full_prompt = build_prompt(user_question, schema_context)

    start_time = time.time()
    response = client.chat.completions.create(
        model=CONFIG["LLM"]["QC_MODEL"],
        messages=[
            {"role": "system", "content": "You are a strict schema-aware assistant for clarifying SQL-related questions."},
            {"role": "user", "content": full_prompt}
        ],
        temperature=0.3
    )
    end_time = time.time()
    duration = round(end_time - start_time, 2)
    logger.log("QC Model", "deepseek-chat")
    logger.log("QC Response Time", f"{duration} seconds")

    full_text = response.choices[0].message.content.strip()
    logger.log("Clarifier Output", full_text)

    is_clear = "<YES>" in full_text and "<NO>" not in full_text
    return full_text, is_clear

if __name__ == "__main__":
    example_question = "Show me the latest updates"
    fake_schema = """
- Table: ART
  - Columns: ARTBEZ, HIST_AEZEIT
"""
    result = clarify_question(example_question, fake_schema)
    print(result)
