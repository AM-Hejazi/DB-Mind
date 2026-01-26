# analyzer.py
import os, time
import re
from src.llm_client import LLMClient
from config import CONFIG
from src.logger import global_logger as logger
from src.query_generator import format_schema_block, build_schema_struct_from_json, _coerce_selected


def analyze_failure(
    question: str,
    selected_schema: dict,
    sql_query: str,
    error_message: str,
) -> tuple[str | None, str | None]:
    if not question:
        logger.log("Analyzer Error", "Missing 'question' input (None received).")
        return None

    # Format subset
    selected_schema = _coerce_selected(selected_schema)
    schema_block = format_schema_block(build_schema_struct_from_json(
        selected_schema.get("tables", []),
        selected_schema.get("columns", [])
    ))

    structured_context = f"""
    === Clarified Question ===
    {question.strip()}

    === Selected Schema Block ===
    {schema_block.strip()}

    === CG-Generated SQL ===
    {sql_query.strip()}

    === SQL Server Error ===
    {(error_message or 'No error message returned from validator.').strip()}
    """

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prompt_template_path = os.path.join(base_dir, "prompts", "AN.txt")
    if not os.path.exists(prompt_template_path):
        return "[ANALYZER ERROR] Prompt file AN.txt not found."

    with open(prompt_template_path, "r", encoding="utf-8") as f:
        template = f.read()

    full_prompt = template.replace("{LOG_CONTENT}", structured_context.strip())

    llm = LLMClient()
    start_time = time.time()
    
    # DeepSeek reasoner models only support temperature=1.0 (default)
    model_name = CONFIG["LLM"].get("AN_MODEL")
    call_params = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a strict schema-aware assistant for fixing SQL-queries."},
            {"role": "user", "content": full_prompt}
        ]
    }
    if "reasoner" not in model_name.lower():
        call_params["temperature"] = 0.0
    
    try:
        response = llm.client.chat.completions.create(**call_params)
    except Exception  as e:
        logger.log("Analyzer LLM Call Failed", str(e))
        return None

    duration = round(time.time() - start_time, 2)
    print(f"Analyzer call took {duration} seconds.")
    if not response or not response.choices:
        logger.log("Analyzer Error", "No choices returned from LLM.")
        return None

    raw_output = response.choices[0].message.content
    if not raw_output:
        logger.log("Analyzer Error", "LLM response content was None.")
        return None

    fixed_sql_raw = raw_output.strip()
    # Strip markdown-like tags
    fixed_sql_raw = fixed_sql_raw.replace("【Analysis】", "").replace("【Corrected SQL】", "").strip()

    logger.log("Analyzer Raw Output", fixed_sql_raw)
    # Extract clean SQL only
    match = re.search(r"<FINAL_ANSWER>(.*?)</FINAL_ANSWER>", fixed_sql_raw or "", re.DOTALL)
    if match:
        fixed_sql = match.group(1).strip()
        analyzer_explanation = fixed_sql_raw.split("<FINAL_ANSWER>")[0].strip()
    else:
        logger.log("Analyzer Warning", "No <FINAL_ANSWER> block found in LLM response.")
        fixed_sql = None
        analyzer_explanation = fixed_sql_raw  # still return raw output for debug

    return fixed_sql, analyzer_explanation


