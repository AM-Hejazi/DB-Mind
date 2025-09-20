import time
import csv
import os
from datetime import datetime
from src.retrieval import retrieve_schema_with_llm
from src.query_generator import generate_sql_query, extract_final_sql, extract_explanation
from src.validator import validate_sql
from src.analyzer import analyze_failure
from src.logger import global_logger as logger
from config import CONFIG
from translator import run_translator_agent
import sys

# Parse optional start index from CLI
start_index = 0
if len(sys.argv) > 1:
    try:
        start_index = int(sys.argv[1])
    except ValueError:
        print("Invalid start index. Using 0.")


EVAL_INPUT_PATH = "Evaluation/Evaluation_Questions.csv"
LOG_OUTPUT_DIR = "Evaluation/ev_logs"
os.makedirs(LOG_OUTPUT_DIR, exist_ok=True)


def read_questions(filepath):
    with open(filepath, newline='', encoding='ISO-8859-1') as csvfile:
        reader = csv.DictReader(csvfile)
        questions = [
            (
                row["By"].strip(),
                row["Category"].strip(),
                row["Complexity"].strip(),
                row["Question"].strip(),
            )
            for row in reader
        ]
    return questions

def run_llm_match_score_with_schema(original: str, translated: str, selected_schema: dict) -> float:
    from src.llm_client import LLMClient
    from src.query_generator import format_schema_block, build_schema_struct_from_json

    # Build context block
    schema_struct = build_schema_struct_from_json(
        selected_schema.get("tables", []),
        selected_schema.get("columns", [])
    )
    schema_block = format_schema_block(schema_struct)

    prompt = f"""
You are an evaluation agent comparing two questions based on their meaning in the context of a database schema.

Below is a schema block showing the relevant database structure:

{schema_block.strip()}

Now compare the following two questions semantically:

Q1: {original.strip()}
Q2: {translated.strip()}

Give a single float score between 0 and 1, where:
- 1 = identical meaning
- 0 = completely unrelated

Only return a float (no explanation).
"""

    client = LLMClient()
    response = client.chat(messages=[
        {"role": "system", "content": "You are a schema-aware semantic similarity evaluator."},
        {"role": "user", "content": prompt}
    ])

    try:
        raw = response.choices[0].message.content.strip()
        score = float(raw.split()[0])
        return round(score, 4)
    except Exception:
        return 0.0


def save_evaluation_result(row_data, csv_path="Evaluation/results/evaluation_metrics.csv"):
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    write_header = not os.path.exists(csv_path)

    with open(csv_path, mode="a", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row_data.keys())
        if write_header:
            writer.writeheader()
        writer.writerow(row_data)

def run_pipeline(by, category, original_complexity, question):
    logger.lines = []  # reset logger buffer
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_q = question[:50].replace(" ", "_").replace("/", "-").replace("?", "")
    logger.log_file = os.path.join(LOG_OUTPUT_DIR, f"{timestamp}__{safe_q}.txt")

    start_time = time.time()

    logger.log("BY", by)
    logger.log("Category", category)
    logger.log("QUESTION", question)
    logger.log("CSV-Complexity", original_complexity)
    logger.log("CONFIG Snapshot", str(CONFIG))


    timings = {}

    # === Step 1: Schema Retriever ===
    t0 = time.time()
    schema_result = retrieve_schema_with_llm(question)
    timings['SchemaRetriever'] = round(time.time() - t0, 2)

    logger.log("SR explanation", schema_result.get("explanation", ""))
    logger.log("Selected Schema", schema_result.get("selected_schema", ""))
    logger.log("SR Complexity", schema_result.get("complexity", ""))

    # carry SR complexity forward
    complexity = schema_result.get("complexity", original_complexity)

    if "Table" not in schema_result.get("selected_schema", ""):
        logger.log("Schema Error", "No valid table selected. Skipping question.")
        return

    # === Step 2: Candidate Generator ===
    t1 = time.time()
    CONFIG["LLM"]["CG_MODEL"] = {
        "Simple": "deepseek-coder",
        "Difficult": "deepseek-coder",
        "Very Difficult": "deepseek-reasoner"
    }.get(complexity, "deepseek-coder")

    cg_response = generate_sql_query(
        question,
        schema_result["selected"],
        complexity
    )
    timings['CandidateGenerator'] = round(time.time() - t1, 2)

    explanation = extract_explanation(cg_response)
    final_sql = extract_final_sql(cg_response)
    logger.log("CG explanation", explanation or "<None>")
    logger.log("CG SQL query", final_sql or "<None>")

    # === Step 3: Validator ===
    t2 = time.time()
    rows, columns, feedback = validate_sql(final_sql)
    timings['Validator'] = round(time.time() - t2, 2)

    #logger.log("Validator Result", str(rows[:10] if rows else "<no rows>"))
    logger.log("Validator result Columns", str(columns))
    logger.log("Validator Time", f"{timings['Validator']} s")

    def _is_empty(val):
        """Return True for None, 0, 0.0, '', 'NULL', 'None', or '0'."""
        if val is None:
            return True
        if isinstance(val, (int, float)) and val == 0:
            return True
        if isinstance(val, str) and val.strip().lower() in {"", "null", "none", "0"}:
            return True
        return False

    # === Step 4: Analyzer (if no results) ===
    if (not rows) or all(_is_empty(v) for row in rows for v in row):
        t3 = time.time()
        corrected_sql, analyzer_expl = analyze_failure(
            question=question,
            selected_schema=schema_result["selected"],
            sql_query=final_sql,
            error_message=feedback or "No results returned"
        )
        timings['Analyzer'] = round(time.time() - t3, 2)

        # Run corrected SQL again if available
        if corrected_sql:
            t4 = time.time()
            rows2, columns2, feedback2 = validate_sql(corrected_sql)
            timings['Validator_AnalyzerFix'] = round(time.time() - t4, 2)
            logger.log("Validator (After Analyzer) Result", str(rows2[:10] if rows2 else "<no rows>"))
            logger.log("Validator (After Analyzer) Columns", str(columns2))

    total_time = round(time.time() - start_time, 2)
    timings['TotalTime'] = total_time
    logger.log("Timings", str(timings))

    # Save log to file
    logger.save()

    # Use corrected_sql if Analyzer was triggered
    sql_to_translate = corrected_sql if 'corrected_sql' in locals() and corrected_sql else final_sql
    translated_question = run_translator_agent(schema_result["selected"], sql_to_translate)

    match_score = run_llm_match_score_with_schema(
        question,
        translated_question,
        schema_result["selected"]
    )

    # Evaluation output structure
    eval_row = {
        "By": by,
        "Category": category,
        "Original Complexity": original_complexity,
        "Question": question,
        "Translated Question": translated_question,  # Optional: fill later via TR agent
        "Complexity (SR)": schema_result.get("complexity"),
        "SR-time": timings.get("SchemaRetriever"),
        "CG-time": timings.get("CandidateGenerator"),
        "Val.1-time": timings.get("Validator"),
        "Val.1 results": bool(rows),
        "AN triggered?": 'Analyzer' in timings,
        "AN-time": timings.get("Analyzer", ""),
        "Val2-time": timings.get("Validator_AnalyzerFix", ""),
        "Val2 results": bool('rows2' in locals() and rows2),
        "total-time": timings.get("TotalTime"),
        "Match-score": match_score,  # Optional: will be filled after TR-agent comparison
    }
    save_evaluation_result(eval_row)




if __name__ == "__main__":
    questions = read_questions(EVAL_INPUT_PATH)
    for by, category, complexity, question in questions:
        run_pipeline(by, category, complexity, question)

# if __name__ == "__main__":
#     questions = read_questions(EVAL_INPUT_PATH)
#
#     # Allow resume via CLI argument: python main1.py 18
#     start_index = 0
#     if len(sys.argv) > 1:
#         try:
#             start_index = int(sys.argv[1])
#             print(f"Resuming from question index: {start_index}")
#         except ValueError:
#             print("Invalid start index. Starting from 0.")
#
#     for i, (by, category, complexity, question) in enumerate(questions):
#         if i < start_index:
#             continue
#         print(f"\n=== Running question {i+1} ===")
#         run_pipeline(by, category, complexity, question)


