import os
import sqlite3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Tuple, Optional
from config import CONFIG
from src.logger import global_logger as logger

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)


def _validate_sqlserver(sql: str) -> Tuple[list, list, Optional[str]]:
    import pyodbc

    db_cfg = CONFIG.get("DATABASE", {}).get("SQLSERVER", {})
    conn_str = (
        f"DRIVER={{{db_cfg.get('DRIVER', 'SQL Server')}}};"
        f"SERVER={db_cfg.get('SERVER', '')};"
        f"DATABASE={db_cfg.get('DATABASE', '')};"
        f"Trusted_Connection={db_cfg.get('TRUSTED_CONNECTION', 'yes')};"
    )

    logger.log("Validator Start", f"Connecting to SQL Server at {db_cfg.get('SERVER', '')}")
    conn = pyodbc.connect(conn_str, timeout=10)
    conn.timeout = 60
    cursor = conn.cursor()

    logger.log("SQL Executed", sql)
    cursor.execute(sql)
    rows = cursor.fetchall()
    column_names = [desc[0] for desc in cursor.description]
    conn.close()
    return rows, column_names, None


def _validate_sqlite(sql: str) -> Tuple[list, list, Optional[str]]:
    db_path = CONFIG.get("DATABASE", {}).get("SQLITE_PATH")
    if not db_path:
        raise RuntimeError("SQLITE_PATH is not configured. Set DB_SQLITE_PATH or CONFIG['DATABASE']['SQLITE_PATH'].")

    db_path = os.path.abspath(db_path)
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"SQLite database file not found at {db_path}")

    logger.log("Validator Start", f"Connecting to SQLite at {db_path}")
    conn = sqlite3.connect(db_path, timeout=60)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    logger.log("SQL Executed", sql)
    cursor.execute(sql)
    rows = cursor.fetchall()
    column_names = [col[0] for col in cursor.description] if cursor.description else []
    conn.close()
    return rows, column_names, None


def _validate_logic(sql: str) -> Tuple[list, list, Optional[str]]:
    dialect = CONFIG.get("DATABASE", {}).get("DIALECT", "sqlite").lower()

    if dialect == "sqlserver":
        return _validate_sqlserver(sql)
    if dialect == "sqlite":
        return _validate_sqlite(sql)

    raise ValueError(f"Unsupported database dialect: {dialect}")


def validate_sql(sql: str) -> Tuple[Optional[list], Optional[list], Optional[str]]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_validate_logic, sql)
            rows, columns, feedback = future.result(timeout=60)

        logger.log("Validation Status", "SUCCESS")
        logger.log("Validator Result Rows", "\n".join(str(r) for r in rows[:10]))
        logger.save()

        if rows:
            if not logger.log_file.endswith("__SUCCESS.txt"):
                success_path = logger.log_file.replace(".txt", "__SUCCESS.txt")
                if not os.path.exists(success_path):
                    os.rename(logger.log_file, success_path)
                    logger.log_file = success_path
                else:
                    logger.log("Validator Log Note", f"Log already exists: {success_path}")

        return rows, columns, None

    except FutureTimeout:
        msg = "[VALIDATOR TIMEOUT] SQL execution exceeded 60 seconds."
        logger.log("Validation Status", "TIMEOUT")
        logger.log("Validator Feedback", msg)
        logger.save()

        failed_path = logger.log_file.replace(".txt", "__FAILED.txt")
        if not logger.log_file.endswith("__FAILED.txt") and os.path.exists(logger.log_file):
            os.rename(logger.log_file, failed_path)
            logger.log_file = failed_path

        return None, None, msg

    except Exception as e:
        feedback = f"[VALIDATOR ERROR]\nQuery:\n{sql}\n\nError:\n{str(e)}"
        logger.log("Validation Status", "FAILURE")
        logger.log("Validator Feedback", feedback)
        logger.log("Validator Exception", str(e))
        logger.save()

        failed_path = logger.log_file.replace(".txt", "__FAILED.txt")
        if not logger.log_file.endswith("__FAILED.txt") and os.path.exists(logger.log_file):
            os.rename(logger.log_file, failed_path)
            logger.log_file = failed_path

        return None, None, feedback

def log_feedback(tag: str, content: str, timestamp: str):
    feedback_path = os.path.join(LOG_DIR, f"{tag}_{timestamp}.txt")
    with open(feedback_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Feedback saved to {feedback_path}")
