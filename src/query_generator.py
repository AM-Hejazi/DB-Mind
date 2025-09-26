import re
import time
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv
from config import CONFIG
from src.llm_client import LLMClient
from src.logger import global_logger as logger
from src.retrieval import load_schema_dict

load_dotenv()


def _ensure_path(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        base_dir = Path(__file__).resolve().parent.parent
        path = (base_dir / path).resolve()
    return path


def _coerce_selected(selected_schema) -> Dict[str, List[str]]:
    if isinstance(selected_schema, dict):
        return selected_schema
    if isinstance(selected_schema, str):
        return {"tables": [], "columns": [], "raw_block": selected_schema}
    if isinstance(selected_schema, list):
        if all(isinstance(item, str) for item in selected_schema):
            return {"tables": selected_schema, "columns": [], "raw_block": ""}
        if selected_schema and isinstance(selected_schema[0], dict):
            tables: List[str] = []
            columns: List[str] = []
            for entry in selected_schema:
                if not isinstance(entry, dict):
                    continue
                table = entry.get("table") or entry.get("name")
                if table and table not in tables:
                    tables.append(table)
                for col in entry.get("columns") or []:
                    if not isinstance(col, dict):
                        continue
                    col_name = col.get("name")
                    if table and col_name:
                        columns.append(f"{table}.{col_name}")
            return {"tables": tables, "columns": columns, "raw_block": ""}
    return {"tables": [], "columns": [], "raw_block": ""}

def convert_to_create_table_format(selected_schema_block: str, column_descriptions: Dict[str, Dict]) -> str:
    output: List[str] = []
    current_table = None
    columns: List[str] = []
    normalized_desc = {k.lower(): v for k, v in column_descriptions.items()}

    for line in selected_schema_block.splitlines():
        line = line.strip()
        table_match = re.match(r"Table\s+([A-Za-z0-9_.]+)", line)
        if table_match:
            if current_table and columns:
                output.append(f"CREATE TABLE {current_table} (\n  " + ",\n  ".join(columns) + "\n);\n")
            current_table = table_match.group(1).strip()
            columns = []
            continue

        if line.startswith("}"):
            if current_table and columns:
                output.append(f"CREATE TABLE {current_table} (\n  " + ",\n  ".join(columns) + "\n);\n")
            current_table = None
            columns = []
            continue

        if not current_table or not line or line.startswith("Ref:"):
            continue

        raw_col = line.split("//", 1)[0].strip()
        if not raw_col:
            continue
        col_name = raw_col.split()[0]
        lookup_id = f"{current_table}.{col_name}".lower()
        col_meta = normalized_desc.get(lookup_id, {})
        comment = col_meta.get("description", "No description available")
        dtype = "TEXT" if any(token in col_name.lower() for token in ("name", "code", "desc")) else "INTEGER"
        columns.append(f"{col_name} {dtype} -- {comment}")

    if current_table and columns:
        output.append(f"CREATE TABLE {current_table} (\n  " + ",\n  ".join(columns) + "\n);\n")

    return "\n".join(output)


def load_prompt_template() -> str:
    base_dir = Path(__file__).resolve().parent.parent
    prompt_path = base_dir / "prompts" / "CG.txt"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def _apply_dialect_overrides(prompt: str) -> str:
    dialect = CONFIG.get("DATABASE", {}).get("DIALECT", "sqlserver").lower()
    if dialect != "sqlite":
        return prompt

    replacements = {
        "SQL Server": "SQLite",
        "SQL server": "SQLite",
        "SQL server Functions Only": "SQLite Functions Only",
        "SQL Server functions": "SQLite functions",
        "GETDATE(), DATEADD(), and DATEDIFF()": "SQLite date functions such as DATE('now'), DATE('now', '-7 day'), and STRFTIME('%Y-%m', column)",
        "GETDATE()": "DATE('now')",
        "DATEADD()": "DATE",
        "DATEDIFF()": "JULIANDAY()",
        "TOP": "LIMIT",
    }
    for old, new in replacements.items():
        prompt = prompt.replace(old, new)

    prompt += (
        "\n\nAdditional SQLite guidance:"\
        "\n- Use LIMIT instead of TOP."\
        "\n- Prefer DATE('now') and STRFTIME for date arithmetic."\
        "\n- Avoid SQL Server specific keywords (e.g., WITH (NOLOCK), NVARCHAR)."\
        "\n- SQLite uses || for concatenation; CAST and COALESCE are available."\
    )
    return prompt


def build_prompt(final_question: str, schema_block: str) -> str:
    template = load_prompt_template()
    prompt = (
        template
        .replace("{QUESTION}", final_question)
        .replace("{SCHEMA}", schema_block.strip())
    )
    return _apply_dialect_overrides(prompt)


def _normalise_table_name(name: str) -> str:
    return name.strip().lower()


def _group_selected_columns(columns: List[str], canonical_tables: List[str]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = {}
    sorted_tables = sorted(canonical_tables, key=len, reverse=True)
    for ref in columns:
        if not ref:
            continue
        ref_lower = ref.lower()
        matched_table = None
        for table in sorted_tables:
            if ref_lower.startswith(table.lower() + "."):
                matched_table = table
                break
        if not matched_table and "." in ref:
            head = ref.split(".", 1)[0]
            for table in sorted_tables:
                if table.lower().endswith(head.lower()):
                    matched_table = table
                    break
        if not matched_table:
            continue
        column_name = ref[len(matched_table) + 1:]
        grouped.setdefault(matched_table, []).append(column_name)
    return grouped


def build_schema_struct_from_json(selected_tables: List[str], selected_columns: List[str]) -> Dict:
    schema_json = load_schema_dict()

    table_lookup = {
        _normalise_table_name(name): name
        for name in schema_json.keys()
        if name != "foreign_keys"
    }

    canonical_tables: List[str] = []
    missing_tables: List[str] = []
    for table in selected_tables:
        key = _normalise_table_name(table)
        canonical = table_lookup.get(key)
        if canonical:
            canonical_tables.append(canonical)
        else:
            missing_tables.append(table)

    if missing_tables:
        logger.log("Schema Selection Missing Tables", ", ".join(missing_tables))

    grouped_columns = _group_selected_columns(selected_columns, canonical_tables)

    subset: Dict[str, Dict] = {}
    for table in canonical_tables:
        table_meta = schema_json.get(table, {})
        subset[table] = {
            "description": table_meta.get("description", ""),
            "columns": {}
        }
        column_lookup = {
            _normalise_table_name(col): col
            for col in table_meta.get("columns", {}).keys()
        }
        selected_for_table = grouped_columns.get(table, [])
        if not selected_for_table:
            subset[table]["columns"] = table_meta.get("columns", {})
            continue
        for ref in selected_for_table:
            column_key = _normalise_table_name(ref)
            canonical_column = column_lookup.get(column_key)
            if canonical_column:
                subset[table]["columns"][canonical_column] = table_meta["columns"][canonical_column]
            else:
                logger.log("Schema Selection Missing Column", f"{table}.{ref}")

    foreign_keys = []
    for fk in schema_json.get("foreign_keys", []):
        from_table = fk.get("from_table")
        to_table = fk.get("to_table")
        if from_table in canonical_tables and to_table in canonical_tables:
            foreign_keys.append(fk)
    if foreign_keys:
        subset["foreign_keys"] = foreign_keys

    return subset


def format_schema_block(schema_json_subset: Dict) -> str:
    lines: List[str] = []
    for table, meta in schema_json_subset.items():
        if table == "foreign_keys":
            continue
        lines.append(f"Table {table} {{")
        for col, cmeta in meta.get("columns", {}).items():
            desc = cmeta.get("description", "")
            samples = cmeta.get("samples", [])
            sample_str = f" (e.g., {', '.join(map(str, samples[:3]))})" if samples else ""
            lines.append(f"  {col} {cmeta.get('type', 'string')} // {desc}{sample_str}")
        lines.append("}")

    for fk in schema_json_subset.get("foreign_keys", []):
        lines.append(
            f"Ref: {fk['from_table']}.({', '.join(fk['from_columns'])}) > {fk['to_table']}.({', '.join(fk['to_columns'])})"
        )
    return "\n".join(lines)


def generate_sql_query(final_question: str, selected_schema: Dict | list | str, complexity: str) -> str:
    selected_schema = _coerce_selected(selected_schema)
    if complexity == "Simple":
        CONFIG["LLM"]["CG_MODEL"] = "deepseek-chat"
    elif complexity == "Difficult":
        CONFIG["LLM"]["CG_MODEL"] = "deepseek-chat"
    else:
        CONFIG["LLM"]["CG_MODEL"] = "deepseek-reasoner"

    selected_tables = selected_schema.get("tables", [])
    selected_columns = selected_schema.get("columns", [])
    subset = build_schema_struct_from_json(selected_tables, selected_columns)
    schema_block = format_schema_block(subset) if subset else ""

    if not schema_block.strip():
        schema_block = selected_schema.get("raw_block", "")

    prompt = build_prompt(final_question, schema_block)

    llm = LLMClient(CONFIG["LLM"].get("CG_MODEL"))
    dialect = CONFIG.get("DATABASE", {}).get("DIALECT", "sqlserver").lower()
    if dialect == "sqlite":
        system_content = "You are an expert SQL query generator for SQLite. Use valid SQLite syntax."
    else:
        system_content = "You are an expert SQL query generator for SQL Server. Use valid T-SQL syntax."

    start_time = time.time()
    response = llm.chat(
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0
    )
    duration = round(time.time() - start_time, 2)

    logger.log("CG Model", llm.model_name)
    logger.log("CG Time", f"{duration} seconds")

    return response.choices[0].message.content.strip()


def extract_final_sql(response: str) -> str | None:
    match = re.search(r"<FINAL_ANSWER>(.*?)</FINAL_ANSWER>", response, re.DOTALL)
    return match.group(1).strip() if match else None


def extract_explanation(response: str) -> str | None:
    match = re.search(r"<EXPLANATION>(.*?)</EXPLANATION>", response, re.DOTALL)
    return match.group(1).strip() if match else None


def preview_prompt(final_question: str, selected_schema: Dict | list | str) -> str:
    selected_schema = _coerce_selected(selected_schema)
    subset = build_schema_struct_from_json(
        selected_schema.get("tables", []),
        selected_schema.get("columns", [])
    )
    schema_block = format_schema_block(subset) if subset else selected_schema.get("raw_block", "")
    return build_prompt(final_question, schema_block)


if __name__ == "__main__":
    selected_schema = {
        "tables": ["equipment", "maintenance_logs"],
        "columns": [
            "equipment.equipment_id",
            "equipment.name",
            "maintenance_logs.log_id",
            "maintenance_logs.equipment_id"
        ],
        "raw_block": ""
    }

    final_question = "How many maintenance logs exist per equipment?"

    print("\n=== PROMPT ===")
    prompt = preview_prompt(final_question, selected_schema)
    print(prompt)

    print("\n=== GENERATING SQL ===")
    response = generate_sql_query(final_question, selected_schema, complexity="Difficult")
    print(response)

    print("\n=== FINAL SQL ===")
    print(extract_final_sql(response))

    print("\n=== EXPLANATION ===")
    print(extract_explanation(response))


