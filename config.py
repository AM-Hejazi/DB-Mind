import os
from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).resolve().parent

def _resolve_path(value: Optional[str]) -> str:
    if not value:
        return ""
    path = Path(value)
    if not path.is_absolute():
        path = BASE_DIR / path
    return str(path)

def _detect_schema_json() -> str:
    env_path = os.getenv("DB_SCHEMA_JSON")
    if env_path:
        return _resolve_path(env_path)

    database_dir = BASE_DIR / "data" / "database"
    candidates = list(database_dir.glob("*.json")) if database_dir.exists() else []

    # Prefer maintenance/demo schemas when available
    candidates.sort(key=lambda p: ("maintenance" not in p.stem.lower(), p.name.lower()))

    if candidates:
        return str(candidates[0])

    fallback = database_dir / "FULL_SCHEMA_DataWarehouse.json"
    return str(fallback)

def _detect_schema_text() -> str:
    env_path = os.getenv("DB_SCHEMA_TEXT")
    if env_path:
        return _resolve_path(env_path)

    database_dir = BASE_DIR / "data" / "database"
    candidates = list(database_dir.glob("*.txt")) if database_dir.exists() else []
    candidates.sort(key=lambda p: ("maintenance" not in p.stem.lower(), p.name.lower()))

    return str(candidates[0]) if candidates else ""

def _detect_sqlite_path() -> str:
    env_path = os.getenv("DB_SQLITE_PATH")
    if env_path:
        return _resolve_path(env_path)

    search_roots = [BASE_DIR / "data" / "database", BASE_DIR / "data", BASE_DIR]
    for root in search_roots:
        if not root.exists():
            continue
        candidates = list(root.glob("*.sqlite*")) or list(root.glob("*.db"))
        candidates.sort(key=lambda p: ("maintenance" not in p.stem.lower(), p.name.lower()))
        if candidates:
            return str(candidates[0])
    return ""


SQLITE_PATH = _detect_sqlite_path()
SCHEMA_JSON_PATH = _detect_schema_json()
SCHEMA_TEXT_PATH = _detect_schema_text()

dialect_env = os.getenv("DB_DIALECT")
if dialect_env:
    default_dialect = dialect_env.strip().lower()
elif SQLITE_PATH:
    default_dialect = "sqlite"
else:
    default_dialect = "sqlserver"


# Model configurations for each provider
# Deepseek: Uses specialized models for reasoning tasks vs fast/accurate tasks
DEEPSEEK_MODELS = {
    "CG_MODEL": "deepseek-reasoner",          # Clarifier: needs reasoning for question understanding
    "SR_MODEL": "deepseek-chat",              # Schema Retrieval: fast schema selection
    "AN_MODEL": "deepseek-reasoner",          # Analyzer: needs reasoning for failure analysis
    "FA_MODEL": "deepseek-chat",              # Feedback: fast feedback generation
    "TR_MODEL": "deepseek-chat",              # Translator: fast SQL translation
    "EV_MODEL": "deepseek-reasoner",          # Evaluator: needs reasoning for evaluation
}

# OpenAI: Uses latest models (gpt-4o for balanced, o1 for reasoning, gpt-4o-mini for fast tasks)
OPENAI_MODELS = {
    "CG_MODEL": "gpt-4o",                     # Clarifier: needs reasoning for question understanding
    "SR_MODEL": "gpt-4o-mini",                # Schema Retrieval: fast schema selection, lightweight
    "AN_MODEL": "gpt-4o",                     # Analyzer: needs reasoning for failure analysis
    "FA_MODEL": "gpt-4o-mini",                # Feedback: fast feedback generation, lightweight
    "TR_MODEL": "gpt-4o-mini",                # Translator: fast SQL translation, lightweight
    "EV_MODEL": "gpt-4o",                     # Evaluator: needs reasoning for evaluation
}

CONFIG = {
    "LLM": {
        "CG_MODEL": "deepseek_reasoner",
        "SR_MODEL": "deepseek-chat",
        "AN_MODEL": "deepseek-reasoner",
        "FA_MODEL": "deepseek-chat",
        "TR_MODEL": "deepseek-chat",
        "EV_MODEL": "o3-pro",
    },
    "DATABASE": {
        "DIALECT": default_dialect,
        "SCHEMA_JSON": SCHEMA_JSON_PATH,
        "SCHEMA_TEXT": SCHEMA_TEXT_PATH,
        "SQLITE_PATH": SQLITE_PATH,
        "SQLSERVER": {
            "DRIVER": os.getenv("DB_DRIVER", "SQL Server"),
            "SERVER": os.getenv("DB_SERVER", "pe-sql-whs230.parts.lokal"),
            "DATABASE": os.getenv("DB_NAME", "DataWarehouse"),
            "TRUSTED_CONNECTION": os.getenv("DB_TRUSTED_CONNECTION", "yes"),
        },
    },
    "FLAGS": {
        "ENABLE_DEBUG_LOGGING": True,
        "USE_GPT_FALLBACK_FOR_CG": True
    }
}

def set_models_for_provider(provider: str) -> None:
    """Update CONFIG models based on the selected provider (OpenAI or Deepseek)."""
    if provider == "OpenAI":
        CONFIG["LLM"].update(OPENAI_MODELS)
    elif provider == "Deepseek":
        CONFIG["LLM"].update(DEEPSEEK_MODELS)
    # If provider is invalid or None, keep existing models
