# === frontdesk.py ===
import os
import time
from dotenv import load_dotenv
from config import CONFIG
from src.logger import global_logger as logger
from src.retrieval import load_schema_text
from src.validator import validate_sql
from src.llm_client import LLMClient

load_dotenv()

def load_fd_prompt_template():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prompt_path = os.path.join(base_dir, "prompts", "FD.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

def load_fd_feedback_template():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prompt_path = os.path.join(base_dir, "prompts", "FD_feedback.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

def build_prompt(schema_block, sample_values_block, chat_history_str):
    template = load_fd_prompt_template()
    return (template
            .replace("{SCHEMA_BLOCK}", schema_block or "No schema available.")
            .replace("{SAMPLE_VALUES}", sample_values_block or "No values available.")
            .replace("{HISTORY}", chat_history_str or "None yet.")
            )


def fd_chat_step(chat_history, user_input, schema_block, sample_values_block, provider: str | None = None):
    """
    Runs a single turn of the frontdesk conversation.
    Returns:
        reply: LLM reply (markdown string)
        clarified: str or None — extracted <CLARIFIED> question
        updated_chat: full updated chat history
    """
    # Append user input before sending
    chat_history.append({"role": "user", "content": user_input})

    # Format conversation for prompt
    history_str = ""
    for msg in chat_history:
        prefix = "User" if msg["role"] == "user" else "Assistant"
        history_str += f"{prefix}: {msg['content']}\n"

    # Build prompt
    template = load_fd_prompt_template()
    prompt = (
        template.replace("{SCHEMA_BLOCK}", schema_block or "N/A")
                .replace("{SAMPLE_VALUES}", sample_values_block or "N/A")
                .replace("{HISTORY}", history_str)
    )

    llm = LLMClient(model_name=CONFIG["LLM"]["FA_MODEL"], provider=provider)
    response = llm.chat(
        messages=[{"role": "system", "content": prompt}],
        temperature=0.2,
    )

    reply = response.choices[0].message.content.strip()
    chat_history.append({"role": "assistant", "content": reply})

    # Extract <CLARIFIED> block
    clarified = None
    if "<CLARIFIED>" in reply and "</CLARIFIED>" in reply:
        start = reply.find("<CLARIFIED>") + len("<CLARIFIED>")
        end = reply.find("</CLARIFIED>")
        clarified = reply[start:end].strip()

    return reply, clarified, chat_history


def fd_feedback(chat_history, final_question, sql_query, result_rows, selected_schema, provider: str | None = None):
    """
    Runs a single feedback turn.
    Returns:
        reply: str – model reply
        rating_start: bool – whether to trigger rating stars
        chat_history: updated conversation
    """
    # Format chat history
    history_str = ""
    if not chat_history:
        history_str = "User: (no prior input yet)\n"
    else:
        for msg in chat_history:
            role = msg.get("role")
            content = msg.get("content", "").strip()
            if not content:
                continue
            prefix = "User" if role == "user" else "Assistant"
            history_str += f"{prefix}: {content}\n"

    # Truncate SQL results
    max_rows = 10
    result_preview = "\n".join(str(row) for row in result_rows[:max_rows]) if result_rows else "(no rows returned)"

    # Format schema snippet
    schema_str = ""
    if isinstance(selected_schema, dict):
        all_tables = selected_schema.get("tables", [])
        all_columns = selected_schema.get("columns", [])
        for table_name in all_tables:
            schema_str += f"\nTable {table_name}:\n"
            for full_col in all_columns:
                if full_col.startswith(f"{table_name}."):
                    col_name = full_col.split(".")[-1]
                    schema_str += f"- {col_name}\n"

    # Load and inject prompt
    template = load_fd_feedback_template()
    system_prompt = template.replace("{final_question}", final_question.strip()) \
                            .replace("{sql_query}", sql_query.strip()) \
                            .replace("{result_preview}", result_preview.strip()) \
                            .replace("{Selected Schema}", schema_str.strip()) \
                            .replace("{chat_history_text}", history_str.strip())

    try:
        llm = LLMClient(model_name=CONFIG["LLM"]["FA_MODEL"], provider=provider)
        response = llm.chat(
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0.2,
        )

        reply = response.choices[0].message.content.strip()

        # Default to full reply in UI unless rating is detected later
        ui_reply = reply

        # Check if the agent requested execution
        if "<RUN_SQL>" in reply and "</RUN_SQL>" in reply:
            start = reply.find("<RUN_SQL>") + len("<RUN_SQL>")
            end = reply.find("</RUN_SQL>")
            sql_to_run = reply[start:end].strip()

            try:
                result_rows, column_names, feedback = validate_sql(sql_to_run)

                if result_rows:
                    header = "\t".join(column_names)
                    result_lines = [header] + ["\t".join(map(str, row)) for row in result_rows[:5]]
                    result_preview = "\n".join(result_lines)
                else:
                    result_preview = "(no results)"

                reply += (
                    f"\n\n✅ Executed the query:\n"
                    f"```sql\n{sql_to_run}\n```\n"
                    f"Top results:\n"
                    f"```\n{result_preview}\n```"
                )

                # ui_reply also gets the same (temporarily)
                ui_reply = reply

            except Exception as e:
                reply += f"\n\n❌ Failed to run query:\n{str(e)}"
                ui_reply = reply

        # Rating detection (for log/trigger only — not shown to user)
        rating_start = "Estimated user rating" in reply

        # 💡 Strip rating from UI message if present
        if rating_start:
            ui_reply = reply.split("Estimated user rating")[0].strip()

    except Exception as e:
        logger.log("FD Feedback Model Crash", str(e))
        reply = "❌ Feedback Agent LLM call failed. Please rephrase or retry."
        ui_reply = reply
        rating_start = False

    chat_history.append({"role": "assistant", "content": ui_reply})
    return reply, rating_start, chat_history



if __name__ == "__main__":
    # === TEST FD FEEDBACK AGENT ===
    from src.frontdesk import fd_feedback

    chat = []

    final_question = "was ist die durchschnittliche pickdauer der picks von gestern pro pickbereich(station)?"
    sql_query = """
    SELECT 
        f.STATION_STID,
        AVG(DATEDIFF(SECOND, p.VPLP_PICKSTARTZEIT, p.VPLP_PICKFERTZEIT)) AS Durchschnittliche_Pickdauer_Sekunden
    FROM 
        wamas.P_VPLP p
    INNER JOIN 
        wamas.FESP f ON p.VPLP_KOMPOS_FELDID = f.FELDID
    WHERE 
        p.VPLP_PICKSTARTZEIT >= CAST(GETDATE()-1 AS DATE)
        AND p.VPLP_PICKSTARTZEIT < CAST(GETDATE() AS DATE)
    GROUP BY 
        f.STATION_STID
    """.strip()

    result_rows = [
        (None, 41),
        ('AUTO', 849),
    ]

    # Minimal schema: only table names (matching your UI agent contract)
    selected_schema = {
        "tables": [
            "wamas.P_VPLP",
            "wamas.FESP"
        ],
        "columns": [
            "wamas.P_VPLP.VPLP_PICKSTARTZEIT",
            "wamas.P_VPLP.VPLP_PICKFERTZEIT",
            "wamas.P_VPLP.VPLP_KOMPOS_FELDID",
            "wamas.FESP.STATION_STID",
            "wamas.FESP.FELDID"
        ]
    }

    # First bot turn
    reply, rating, chat = fd_feedback(chat, final_question, sql_query, result_rows, selected_schema)
    print("🤖 Bot:", reply)

    while True:
        user_input = input("🧑 User: ")
        if user_input.strip().lower() in {"exit", "quit"}:
            break
        chat.append({"role": "user", "content": user_input})
        reply, rating, chat = fd_feedback(chat, final_question, sql_query, result_rows, selected_schema)
        print("🤖 Bot:", reply)
        if rating:
            print("⭐️ UI should now trigger rating collection.")
            break



