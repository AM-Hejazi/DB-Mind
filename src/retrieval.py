import os
import re
import json
import time
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv
from src.logger import global_logger as logger
from config import CONFIG
from src.llm_client import LLMClient

load_dotenv()


def _ensure_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        base_dir = Path(__file__).resolve().parent.parent
        path = (base_dir / path).resolve()
    return path


def _coerce_iterable(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalise_schema_json(raw_data) -> Dict[str, Dict]:
    """Return schema as table -> metadata dictionary regardless of source format."""
    if isinstance(raw_data, dict):
        return raw_data

    if isinstance(raw_data, list):
        normalised: Dict[str, Dict] = {}
        foreign_keys: List[Dict] = []

        for entry in raw_data:
            if not isinstance(entry, dict):
                continue

            table_name = entry.get("table") or entry.get("name")
            if not table_name:
                continue

            columns_block = {}
            for column in entry.get("columns", []):
                if not isinstance(column, dict):
                    continue
                col_name = column.get("name")
                if not col_name:
                    continue
                columns_block[col_name] = {
                    "type": column.get("type", ""),
                    "description": column.get("description", ""),
                    "samples": column.get("samples", []),
                }

            normalised[table_name] = {
                "description": entry.get("description", ""),
                "columns": columns_block,
            }

            for fk in entry.get("foreign_keys", []):
                if not isinstance(fk, dict):
                    continue
                from_cols = _coerce_iterable(fk.get("from_columns") or fk.get("from_column"))
                to_cols = _coerce_iterable(fk.get("to_columns") or fk.get("reference_column"))
                foreign_keys.append({
                    "from_table": table_name,
                    "from_columns": [c for c in from_cols if c],
                    "to_table": fk.get("to_table") or fk.get("reference_table"),
                    "to_columns": [c for c in to_cols if c],
                })

        if foreign_keys:
            normalised["foreign_keys"] = [
                fk for fk in foreign_keys if fk.get("from_table") and fk.get("to_table")
            ]

        return normalised

    raise ValueError("Unsupported schema JSON format. Expected dict or list.")


def load_schema_dict() -> Dict[str, Dict]:
    db_config = CONFIG.get("DATABASE", {})
    schema_json_path = db_config.get("SCHEMA_JSON", "")
    if not schema_json_path:
        raise FileNotFoundError("No schema JSON configured. Set DB_SCHEMA_JSON or place a schema file in data/database.")

    schema_path = _ensure_path(schema_json_path)
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema JSON file not found at {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    return _normalise_schema_json(raw)


def load_schema_text() -> str:
    schema_json = load_schema_dict()

    lines: List[str] = []
    for table, meta in schema_json.items():
        if table == "foreign_keys":
            continue
        lines.append(f"Table {table} {{")
        columns = meta.get("columns", {}) if isinstance(meta, dict) else {}
        for col, cmeta in columns.items():
            desc = cmeta.get("description", "")
            samples = cmeta.get("samples", [])
            sample_str = f" (e.g., {', '.join(map(str, samples[:3]))})" if samples else ""
            lines.append(f"  {col} {cmeta.get('type', 'string')} // {desc}{sample_str}")
        lines.append("}")

    for fk in schema_json.get("foreign_keys", []):
        from_cols = ", ".join(fk.get("from_columns", []))
        to_cols = ", ".join(fk.get("to_columns", []))
        lines.append(
            f"Ref: {fk.get('from_table')}.({from_cols}) > {fk.get('to_table')}.({to_cols})"
        )

    return "\n".join(lines)


def load_prompt_template():
    base_dir = Path(__file__).resolve().parent.parent
    prompt_path = base_dir / "prompts" / "SR.txt"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

def build_prompt(user_question, schema_text):
    template = load_prompt_template()
    return template.replace("{QUESTION}", user_question).replace("{SCHEMA}", schema_text)

def retrieve_schema_with_llm(user_question, provider: str | None = None):
    schema_text = load_schema_text()
    prompt = build_prompt(user_question, schema_text)

    start_time = time.time()
    sr_llm = LLMClient(CONFIG["LLM"]["SR_MODEL"], provider=provider)
    
    # DeepSeek reasoner models only support temperature=1.0 (default)
    chat_params = {
        "messages": [
            {"role": "system", "content": "You are a SQL schema selector assistant."},
            {"role": "user", "content": prompt}
        ]
    }
    if "reasoner" not in sr_llm.model_name.lower():
        chat_params["temperature"] = 0.0
    
    response = sr_llm.chat(**chat_params)
    duration = round(time.time() - start_time, 2)
    logger.log("SR Model", sr_llm.model_name)
    logger.log("SR Response Time", f"{duration} seconds")

    full_output = response.choices[0].message.content.strip()

    complexity_match = re.search(r"<COMPLEXITY>(.*?)</COMPLEXITY>", full_output, re.DOTALL)
    complexity = complexity_match.group(1).strip() if complexity_match else "Difficult"

    explanation = full_output
    raw_schema_block = ""
    selected_tables: List[str] = []
    selected_columns: List[str] = []

    if "**SELECTED SCHEMA**" in full_output:
        parts = full_output.split("**SELECTED SCHEMA**")
        if parts:
            explanation = parts[0].strip()
        if len(parts) > 1:
            raw_schema_block = parts[1].strip()

        current_table = None
        for line in raw_schema_block.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("//"):
                continue
            if stripped.startswith("Ref:"):
                continue
            if stripped.startswith("**SELECTED SCHEMA**"):
                continue
            if stripped.startswith("<COMPLEXITY>"):
                continue
            if stripped.startswith("}"):
                current_table = None
                continue

            table_match = re.match(r"Table\s+([A-Za-z0-9_.]+)", stripped)
            if table_match:
                current_table = table_match.group(1).strip()
                if current_table not in selected_tables:
                    selected_tables.append(current_table)
                continue

            if current_table:
                column_token = stripped.split("//", 1)[0].strip()
                if not column_token:
                    continue
                column_name = column_token.split()[0]
                full_column = f"{current_table}.{column_name}"
                if full_column not in selected_columns:
                    selected_columns.append(full_column)

    selected_payload = {
        "tables": selected_tables,
        "columns": selected_columns,
        "raw_block": raw_schema_block,
    }

    return {
        "full_output": full_output,
        "explanation": explanation,
        "selected_schema": raw_schema_block,
        "selected": selected_payload,
        "complexity": complexity
    }


if __name__ == "__main__":
    q = "How many customers from Germany ordered at least one item from the AUTO picking area last week?"
    result = retrieve_schema_with_llm(q)

    print("\n--- Full Output ---\n")
    print(result["full_output"])

    print("\n--- Explanation ---\n")
    print(result["explanation"])

    print("\n--- Selected Schema Block ---\n")
    print(result["selected_schema"])
