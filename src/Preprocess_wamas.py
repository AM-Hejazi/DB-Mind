import os
import re
import pandas as pd
from typing import Dict, Set, Tuple


class DBHandler:
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.table_csv = os.path.join(base_dir, "data", "embeddings", "tables_vector_db.csv")
        self.column_csv = os.path.join(base_dir, "data", "embeddings", "columns_vector_db.csv")
        self.full_schema_path = os.path.join(base_dir, "data", "schemas", "FULL_SCHEMA_MaintenanceDemo.txt")

        self.table_map: Dict[str, str] = {}  # raw_lower_name → Wamas.RealName
        self.column_set: Set[str] = set()    # P_AUSK.COL style
        self.foreign_keys: Set[str] = set()

        self._load_all()

    def _load_all(self):
        self._load_table_map()
        self._load_column_set()
        self._load_foreign_keys()

    def _load_table_map(self):
        df = pd.read_csv(self.table_csv, encoding="latin1")
        self.table_map.clear()
        for t in df["id"].dropna().unique():
            t_str = t.strip()
            self.table_map[t_str.lower()] = f"wamas.{t_str}"

            # Add fuzzy alias (e.g., ausk → wamas.P_AUSK)
            if "_" in t_str:
                suffix = t_str.split("_")[-1]
                if suffix.lower() not in self.table_map:
                    self.table_map[suffix.lower()] = f"wamas.{t_str}"

    def _load_column_set(self):
        df = pd.read_csv(self.column_csv, encoding="latin1")
        self.column_set = {
            str(row.id).strip()
            for row in df.itertuples()
            if hasattr(row, "id") and row.id
        }

    def _load_foreign_keys(self):
        with open(self.full_schema_path, "r", encoding="utf-8", errors="replace") as f:
            self.foreign_keys = {
                line.strip() for line in f if line.strip().startswith("Ref:")
            }

    def export_normalized_schema_files(self):
        export_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "database")
        os.makedirs(export_dir, exist_ok=True)

        # ✅ Export tables_vector_db.csv
        df_tables = pd.read_csv(self.table_csv, encoding="latin1")
        df_tables["id"] = df_tables["id"].fillna("").apply(lambda t: f"wamas.{t.strip()}")
        df_tables.to_csv(os.path.join(export_dir, "tables_vector_db.csv"), index=False)
        print("✅ Exported normalized tables_vector_db.csv")

        # ✅ Export columns_vector_db.csv
        df_cols = pd.read_csv(self.column_csv, encoding="latin1")
        df_cols["id"] = df_cols["id"].fillna("").apply(lambda c: f"wamas.{c.strip()}")
        df_cols.to_csv(os.path.join(export_dir, "columns_vector_db.csv"), index=False)
        print("✅ Exported normalized columns_vector_db.csv")

        # ✅ Export FULL_SCHEMA_MaintenanceDemo.txt
        with open(self.full_schema_path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()

        updated_lines = []
        table_pattern = re.compile(r'^Table\s+(\w+)\s*{?')
        for line in raw_lines:
            # Prefix Table declarations
            match = table_pattern.match(line)
            if match:
                tbl = match.group(1)
                line = line.replace(f"Table {tbl}", f"Table wamas.{tbl}")

            # ✅ Replace every raw table usage like "ART." with "wamas.ART."
            for raw_table in pd.read_csv(self.table_csv, encoding="latin1")["id"].dropna().unique():
                raw_table = raw_table.strip()
                line = re.sub(
                    rf'(?<!wamas\.)\b{re.escape(raw_table)}\.',
                    f"wamas.{raw_table}.",
                    line
                )

            updated_lines.append(line)

        out_path = os.path.join(export_dir, "FULL_SCHEMA_MaintenanceDemo.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.writelines(updated_lines)

        print("✅ Exported normalized FULL_SCHEMA_MaintenanceDemo.txt")


    def get_tables(self) -> Set[str]:
        return set(self.table_map.values())

    def get_columns(self) -> Set[str]:
        return self.column_set

    def get_foreign_keys(self) -> Set[str]:
        return self.foreign_keys

if __name__ == "__main__":
    db = DBHandler()
    db.export_normalized_schema_files()
