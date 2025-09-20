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
    path = os.path.join(base_dir, "prompts", "QF.txt")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def build_prompt(original_q, feedback, user_rewrite):
    template = load_prompt_template()
    return (template
            .replace("{ORIGINAL_QUESTION}", original_q)
            .replace("{FEEDBACK}", feedback)
            .replace("{USER_REWRITE}", user_rewrite))

def finalize_question(original_q, feedback, user_rewrite) -> (str, str):
    prompt = build_prompt(original_q, feedback, user_rewrite)

    start_time = time.time()
    response = client.chat.completions.create(
        model=CONFIG["LLM"]["QF_MODEL"],
        messages=[
            {"role": "system", "content": "You are a clarification finalizer for SQL question rephrasing."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    end_time = time.time()
    duration = round(end_time - start_time, 2)
    logger.log("QF Model", "deepseek-chat")
    logger.log("QF Response Time", f"{duration} seconds")

    content = response.choices[0].message.content.strip()

    # Extract clarified question
    clarified = None
    if "<CLARIFIED>" in content and "</CLARIFIED>" in content:
        start = content.find("<CLARIFIED>") + len("<CLARIFIED>")
        end = content.find("</CLARIFIED>")
        clarified = content[start:end].strip()

    # Extract complexity label
    complexity = None
    if "<COMPLEXITY>" in content and "</COMPLEXITY>" in content:
        c_start = content.find("<COMPLEXITY>") + len("<COMPLEXITY>")
        c_end = content.find("</COMPLEXITY>")
        complexity = content[c_start:c_end].strip()

    # If we got both, return them; otherwise, fallback to original behavior
    if clarified and complexity:
        return clarified, complexity

    # If no tags found, return content as question and default to "Difficult"
    return content, "Difficult"


# Test
if __name__ == "__main__":
    o_q = "Show me the latest updates"
    feedback = """
- The term 'updates' is vague. Likely means recent changes to something.
- Clarify if this means product descriptions or order statuses.
- Consider defining what 'latest' means.
"""
    user_rewrite = "Show me the recent product changes including their names and timestamps."
    print(finalize_question(o_q, feedback, user_rewrite))
