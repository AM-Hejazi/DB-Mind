import re
import os
import json
import pyodbc
from collections import defaultdict
from tqdm import tqdm


# === Paths ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_TXT_PATH = os.path.join(BASE_DIR, "data", "database", "FULL_SCHEMA_MaintenanceDemo.txt")
OUTPUT_JSON_PATH = os.path.join(BASE_DIR, "data", "database", "FULL_SCHEMA_MaintenanceDemo.json")

# === Connect to SQL Server ===
conn = pyodbc.connect(
    r'DRIVER={SQL Server};SERVER=pe-sql-whs230.parts.lokal;DATABASE=DataWarehouse;Trusted_Connection=yes;'
)
cursor = conn.cursor()

# === Step 1: Parse schema for tables, columns, and descriptions ===
schema = defaultdict(lambda: {"description": "", "columns": {}})
current_table = None
inside_table = False
ref_lines = []

with open(SCHEMA_TXT_PATH, "r", encoding="utf-8") as f:
    for line in f:
        raw = line.strip()

        # Capture global Ref lines separately
        if raw.startswith("Ref:"):
            ref_lines.append(raw)
            continue

        # Match table header
        table_match = re.match(r"Table\s+(wamas\.\w+)\s*{", raw)
        if table_match:
            current_table = table_match.group(1)
            inside_table = True
            continue

        if inside_table and raw.startswith("//") and schema[current_table]["description"] == "":
            schema[current_table]["description"] = raw.lstrip("//").strip()
            continue

        if inside_table and raw == "}":
            inside_table = False
            current_table = None
            continue

        if inside_table and "//" in raw and current_table:
            col_def, comment = raw.split("//", 1)
            parts = col_def.strip().split()
            if len(parts) >= 2:
                col_name = parts[0]
                col_type = parts[1]
                col_desc = comment.strip().rstrip(",")
                schema[current_table]["columns"][col_name] = {
                    "type": col_type,
                    "description": col_desc,
                    "samples": []
                }

# === Step 2: Sample values from DB ===
total_cols = sum(len(tbl["columns"]) for tbl in schema.values())
with tqdm(total=total_cols, desc="Sampling DB values") as pbar:
    for table, table_meta in schema.items():
        for col in table_meta["columns"].keys():
            try:
                sql = f"""
                    SELECT DISTINCT TOP 5 [{col}]
                    FROM {table}
                    WHERE [{col}] IS NOT NULL
                """
                cursor.execute(sql)
                values = [str(row[0]) for row in cursor.fetchall()]
                schema[table]["columns"][col]["samples"] = values
            except Exception as e:
                print(f"⚠️ {table}.{col} → {e}")
                schema[table]["columns"][col]["samples"] = ["<ERROR>"]
            pbar.update(1)

# === Step 3: Parse and extract foreign keys from global ref_lines ===
foreign_keys = []
ref_pattern = re.compile(
    r"Ref:\s*(wamas\.\w+)\.\(?([\w_ ,]+)\)?\s*>\s*(wamas\.\w+|\w+)\.\(?([\w_ ,]+)\)?",
    re.IGNORECASE
)

for ref in ref_lines:
    match = ref_pattern.match(ref)
    if match:
        from_table, from_cols, to_table, to_cols = match.groups()
        from_cols = [c.strip() for c in from_cols.split(",")]
        to_cols = [c.strip() for c in to_cols.split(",")]
        # Normalize to_table name if missing prefix
        if not to_table.startswith("wamas."):
            to_table = f"wamas.{to_table}"
        foreign_keys.append({
            "from_table": from_table,
            "from_columns": from_cols,
            "to_table": to_table,
            "to_columns": to_cols
        })

# === Step 4: Write final schema JSON with top-level foreign_keys ===
schema_output = dict(schema)
schema_output["foreign_keys"] = foreign_keys

with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
    json.dump(schema_output, f, indent=2, ensure_ascii=False)

print(f"✅ Enhanced schema written to {OUTPUT_JSON_PATH} with {len(foreign_keys)} foreign keys.")

