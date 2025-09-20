# === handlers.py ===
import os, re
import glob
from datetime import datetime
import gradio as gr
from src.frontdesk import fd_chat_step
from src.logger import global_logger as logger
from src.retrieval import retrieve_schema_with_llm
from src.query_generator import generate_sql_query, extract_final_sql, extract_explanation
from src.validator import validate_sql
from src.frontdesk import fd_feedback
from config import CONFIG
from src.retrieval import load_schema_text
from src.analyzer import analyze_failure

welcome_message = (
    "<div style='padding: 12px; border: 1px solid #333; border-radius: 12px; background-color: #1e1e1e; color: #f5f5f5; font-size: 14px;'>"
    "<h3 style='margin-top: 0;'>💡 <b>Welcome / Willkommen</b></h3>"
    "<div style='display: flex; flex-wrap: wrap; gap: 48px; justify-content: space-between;'>"
    "<div style='flex: 1; min-width: 300px;'>"
    "<h4 style='margin: 0;'>English</h4>"
    "<p>This is an intelligent database assistant who can answer your questions about the warehouse processes by generating live SQL Server queries over the DataWarehouse database.</p>"
    "<ul style='margin-top: 6px; padding-left: 20px;'>"
    "<li><b>How to use it:</b></li>"
    "<li>Ask a question in natural language</li>"
    "<li>The bot will clarify your request based on the database schema if needed.</li>"
    "<li>You'll see the generated SQL and live results from the database.</li>"
    "<li>Please submit your feedback at the end.</li>"
    "</ul>"
    "</div>"
    "<div style='flex: 1; min-width: 300px;'>"
    "<h4 style='margin: 0;'>Deutsch</h4>"
    "<p>Dies ist ein intelligenter Datenbank-Assistent, der Ihre Fragen zu Lagerprozessen beantworten kann, indem er Live-SQL-Abfragen über die DataWarehouse-Datenbank generiert.</p>"
    "<ul style='margin-top: 6px; padding-left: 20px;'>"
    "<li><b>So funktioniert es:</b></li>"
    "<li>Stellen Sie Ihre Frage in natürlicher Sprache</li>"
    "<li>Der Bot klärt Ihre Anfrage anhand des Schemas</li>"
    "<li>Sie sehen die generierte SQL-Abfrage und Live-Ergebnisse</li>"
    "<li>Bitte geben Sie am Ende Ihr Feedback ab</li>"
    "</ul>"
    "</div>"
    "</div>"
    "<div style='margin-top: 12px;'>⏳ <i>Waiting for your request ...</i></div>"
    "</div>"
)

# Override welcome message text for Maintenance Demo (SQLite)
welcome_message = (
    "<div style='padding: 12px; border: 1px solid #333; border-radius: 12px; background-color: #1e1e1e; color: #f5f5f5; font-size: 14px;'>"
    "<h3 style='margin-top: 0;'>💡 <b>Welcome / Willkommen</b></h3>"
    "<div style='display: flex; flex-wrap: wrap; gap: 48px; justify-content: space-between;'>"
    "<div style='flex: 1; min-width: 300px;'>"
    "<h4 style='margin: 0;'>English</h4>"
    "<p>This demo uses a read‑only maintenance SQLite database. Ask questions about equipment, sensors, work orders, failures, technicians, or plans. I will generate SQL over the demo database and show the results.</p>"
    "<ul style='margin-top: 6px; padding-left: 20px;'>"
    "<li><b>How to use it:</b></li>"
    "<li>Ask a question in natural language</li>"
    "<li>If needed, I clarify based on the schema</li>"
    "<li>Then I show the generated SQL and a live result preview</li>"
    "<li>Note: demo data only; top results previewed</li>"
    "</ul>"
    "</div>"
    "<div style='flex: 1; min-width: 300px;'>"
    "<h4 style='margin: 0;'>Deutsch</h4>"
    "<p>Diese Demo nutzt eine schreibgeschützte Wartungs‑SQLite‑Datenbank. Stellen Sie Fragen zu Anlagen, Sensoren, Aufträgen, Störungen, Technikern oder Plänen. Ich generiere SQL über die Demo‑Datenbank und zeige die Ergebnisse.</p>"
    "<ul style='margin-top: 6px; padding-left: 20px;'>"
    "<li><b>So funktioniert es:</b></li>"
    "<li>Stellen Sie eine Frage in natürlicher Sprache</li>"
    "<li>Bei Bedarf kläre ich nach dem Schema</li>"
    "<li>Danach zeige ich die SQL‑Abfrage und eine Ergebnisvorschau</li>"
    "<li>Hinweis: Nur Demodaten; Top‑Ergebnisse werden angezeigt</li>"
    "</ul>"
    "</div>"
    "</div>"
    "<div style='margin-top: 12px;'>⏳ <i>Waiting for your request ...</i></div>"
    "</div>"
)

logger.log("CONFIG Snapshot", str(CONFIG))

LIMIT_REACHED_MESSAGE = "You have reached the demo limit of two questions. Please come back later."

def get_latest_log():
    log_files = sorted(glob.glob("ev_logs/run_*.txt"), key=os.path.getmtime, reverse=True)
    return log_files[0] if log_files else None


# === reset_state ===
def reset_state(session_state):
    session_state.update({
        "original_q": "",
        "final_q": "",
        "initial_user_query": "",
        "sql_query": "",
        "fd_history": [],
        "schema_result": {},
        "complexity": "",
        "final_result": "",
        "feedback_rating": None,
        "feedback_text": "",
        "fd_feedback_history": [],
        "feedback": False,
        "has_welcomed": False,
    })

    session_state["question_started"] = False
    session_state["skip_pipeline"] = False

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.log_file = f"ev_logs/run_{timestamp}.txt"

    input_visible = not session_state.get("limit_reached", False)

    return (
        "",
        [{"role": "assistant", "content": welcome_message}],
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=input_visible),
    )



# === update_ui_visibility ===
def update_ui_visibility(session_state, *, log_file=False, feedback_rating=False, inputrow=True):
    session_state["show_log_file"] = log_file
    session_state["show_feedback_rating"] = feedback_rating

    allow_input = inputrow
    if session_state.get("limit_reached") and not session_state.get("question_started"):
        allow_input = False
    session_state["show_inputrow"] = allow_input

    log_path = logger.log_file if (
        log_file and logger.log_file and os.path.exists(logger.log_file)
    ) else None

    return (
        gr.update(visible=log_file, value=log_path),
        gr.update(visible=feedback_rating),
        gr.update(visible=allow_input),
    )



# === handle_user_input ===
def handle_user_input(message, history, session_state):

    print(f"DEBUG: handle_user_input - Incoming history length: {len(history)}")
    if history and history[0].get("content"):
        print(f"DEBUG: handle_user_input - First message in history: {history[0]['content'][:50]}...")
    else:
        print("DEBUG: handle_user_input - History is empty or first message content is missing.")

    if session_state.get("feedback") is True:
        fd_chat = session_state.get("fd_feedback_history") or []
        fd_chat.append({"role": "user", "content": message})
        history.append({"role": "user", "content": message})
        session_state["fd_feedback_history"] = fd_chat
        logger.log("FD Feedback/User", message)
        return "", history, *update_ui_visibility(session_state, log_file=False, feedback_rating=False,
                                                  inputrow=True)

    max_questions = session_state.get("max_questions", 2) or 2
    question_count = session_state.get("question_count", 0)
    question_started = session_state.get("question_started", False)

    if not question_started:
        if question_count >= max_questions:
            session_state["limit_reached"] = True
            session_state["skip_pipeline"] = True
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": LIMIT_REACHED_MESSAGE})
            return "", history, *update_ui_visibility(session_state, log_file=False, feedback_rating=False, inputrow=False)
        session_state["question_count"] = question_count + 1
        session_state["question_started"] = True
        session_state["limit_reached"] = False
    session_state["skip_pipeline"] = False

    history.append({"role": "user", "content": message})

    # FD Skip shortcut
    if message.strip().lower().startswith("/skip"):
        skipped_q = message.replace("/skip", "", 1).strip()
        session_state["original_q"] = skipped_q
        session_state["initial_user_query"] = skipped_q
        session_state["final_q"] = skipped_q
        logger.log("Original Question (FD Skipped)", skipped_q)
        logger.log("Final Reformulated Question", skipped_q)
        history.append({
            "role": "assistant",
            "content": f"⏩ Front-Desk agent skipped. Proceeding with:\n\n> *{skipped_q}*\n\n🗂️ Schema Retriever running..."
        })
        return "", history, *update_ui_visibility(session_state, log_file=False, feedback_rating=False,
                                                  inputrow=True)

    # First question setup
    if not session_state["original_q"]:
        session_state["original_q"] = message
        session_state["initial_user_query"] = message
        logger.log("Original Question", message)

    return "", history, *update_ui_visibility(session_state, log_file=False, feedback_rating=False,
                                              inputrow=True)


def process_next_step(history, session_state):
    if session_state.get("skip_pipeline"):
        session_state["skip_pipeline"] = False
        return "", history, *update_ui_visibility(session_state, log_file=False, feedback_rating=False, inputrow=False)

    print("🔁 process_next_step triggered")
    print("📜 History length:", len(history))
    print("📘 Last message:", history[-1]["content"] if history else "EMPTY")

    # === FD Clarification Phase ===
    if not session_state.get("final_q") or not session_state["final_q"].strip():
        if history[-1]["role"] != "user":
            return "", history, *update_ui_visibility(session_state, log_file=False, feedback_rating=False,
                                                      inputrow=True)

        user_input = history[-1]["content"]
        reply, clarified, updated = fd_chat_step(
            session_state.get("fd_history", []),
            user_input,
            load_schema_text(),
            "No values available"
        )
        session_state["fd_history"] = updated
        logger.log("FD/User", user_input)
        logger.log("FD/Response", reply)

        if clarified:
            session_state["final_q"] = clarified
            logger.log("Final Reformulated Question", clarified)
            history.append({
                "role": "assistant",
                "content": f"✅ Finalized your question:\n\n> *{clarified}*\n\n🗂️ Schema Retriever running..."
            })
        else:
            history.append({"role": "assistant", "content": reply})

        yield "", history, *update_ui_visibility(session_state, log_file=False, feedback_rating=False,
                                             inputrow=True)

    # === Schema Retriever ===
    if "Schema Retriever running" in history[-1]["content"]:
        yield "", history, *update_ui_visibility(session_state, log_file=False, feedback_rating=False,
                                             inputrow=True)

        schema_result = retrieve_schema_with_llm(session_state["final_q"])
        session_state["complexity"] = schema_result.get("complexity")
        session_state["schema_result"] = schema_result
        logger.log("Schema Reasoning Explanation", schema_result["explanation"])
        logger.log("Selected Schema Context", schema_result["selected_schema"])
        logger.log("complexity", session_state["complexity"])

        if "Table" not in schema_result["selected_schema"]:
            msg = "⚠️ Your question doesn't seem related to our warehouse database schema. Try asking a new valid question about shipments, items, orders, transport units, etc."
            history.append({"role": "assistant", "content": msg})
            return "", history, *update_ui_visibility(session_state, log_file=False, feedback_rating=False,
                                             inputrow=True)

        history.append({"role": "assistant", "content": "⚙️ Generating SQL Query..."})
        yield "", history, *update_ui_visibility(session_state, log_file=False, feedback_rating=False,
                                             inputrow=True)

    # === SQL Generator ===
    if "Generating SQL" in history[-1]["content"]:
        yield "", history, *update_ui_visibility(session_state, log_file=False, feedback_rating=False,
                                             inputrow=True)

        if session_state.get("sql_query"):
            return None

        try:
            cg_response = generate_sql_query(
                session_state["final_q"],
                session_state["schema_result"]["selected"],
                session_state["complexity"]
            )
            session_state["sql_query"] = cg_response
            logger.log("Generated SQL Query", cg_response)

            explanation = extract_explanation(cg_response)
            final_sql = extract_final_sql(cg_response)

            history.append({"role": "assistant", "content": "🔍 Validating result with SQL Server..."})
            yield "", history, *update_ui_visibility(session_state, log_file=False, feedback_rating=False,
                                                 inputrow=True), session_state

            rows, columns, feedback = validate_sql(final_sql)
            session_state["raw_result_rows"] = rows or []
            corrected_sql = None
            analyzer_expl = None
            session_state["feedback"] = True

            if not rows:
                history.append({"role": "assistant", "content": "🤖 No results found. Let me check if the SQL query can be improved..."})
                history.append({"role": "assistant", "content": "🧠 Analyzer running..."})
                yield "", history, *update_ui_visibility(session_state, log_file=False, feedback_rating=False,
                                                     inputrow=True), session_state

                try:
                    corrected_sql, analyzer_expl = analyze_failure(
                        question=session_state["final_q"],
                        selected_schema=session_state["schema_result"]["selected"],
                        sql_query=session_state["sql_query"],
                        error_message=feedback,
                    )
                except Exception as e:
                    logger.log("Analyzer Crash", str(e))
                    history.append({"role": "assistant", "content": f"❌ Analyzer crashed: `{str(e)}`"})
                    yield "", history, *update_ui_visibility(session_state, log_file=False, feedback_rating=False,
                                                         inputrow=True)
                    return None

                if not corrected_sql or not isinstance(corrected_sql, str) or not re.search(r"\bselect\b", corrected_sql.strip(), re.IGNORECASE):
                    history.append({"role": "assistant", "content": "❌ Analyzer failed to produce a valid SQL query. Please try rephrasing your question."})
                    yield "", history, *update_ui_visibility(session_state, log_file=False, feedback_rating=False,
                                                         inputrow=True)
                    return None

                session_state["sql_query"] = corrected_sql
                history.append({"role": "assistant", "content": "🔍 Validating updated SQL from Analyzer..."})
                rows, columns, feedback = validate_sql(corrected_sql)
                session_state["raw_result_rows"] = rows or []
                session_state["feedback"] = True

            truncated_rows = rows[:10] if rows else []
            header_line = "\t".join(columns) if columns else ""
            data_lines = ["\t".join(str(cell) for cell in row) for row in truncated_rows]
            result_preview = "\n".join([header_line] + data_lines) if header_line else "\n".join(data_lines)

            session_state["final_result"] = result_preview

            # Display explanations
            if not corrected_sql:
                history.append({
                    "role": "assistant",
                    "content": (
                        f"🤖 **Query Explanation (CG):**\n{explanation}\n\n"
                        f"📄 **SQL Query:**\n```sql\n{final_sql}\n```\n\n"
                        f"📦 **Top 10 Results:**\n```\n{result_preview}\n```"
                    )
                })
            else:
                history.append({
                    "role": "assistant",
                    "content": (
                        f"🤖 **Query Generator Explanation:**\n{explanation}\n\n"
                        f"📄 **CG SQL Query:**\n```sql\n{final_sql}\n```"
                    )
                })
                history.append({
                    "role": "assistant",
                    "content": (
                        f"🧠 **Analyzer Explanation:**\n{analyzer_expl}\n\n"
                        f"📄 **Analyzer SQL (corrected):**\n```sql\n{corrected_sql}\n```"
                    )
                })
                history.append({
                    "role": "assistant",
                    "content": f"📦 **Top 10 Results:**\n```\n{result_preview}\n```"
                })
            session_state["feedback"] = True

            yield "", history, *update_ui_visibility(session_state, log_file=False, feedback_rating=False,
                                                 inputrow=True)

        except Exception as e:
            logger.log("Validator/CG error", str(e))
            history.append({
                "role": "assistant",
                "content": f"❌ Unexpected error:\n\n[UNHANDLED ERROR during SQL execution]\n{str(e)}"
            })
            session_state["feedback"] = True

            yield "", history, *update_ui_visibility(session_state, log_file=False, feedback_rating=False,
                                                 inputrow=True)

    # === FD Feedback Agent Phase ===
    if session_state.get("feedback") is True:
        print("💬 FD Feedback Agent Activated")
        fd_chat = session_state.get("fd_feedback_history") or []

        # Parse result rows safely (fallback to empty)
        rows = session_state.get("raw_result_rows", []) or []

        try:
            reply, rating_start, fd_chat = fd_feedback(
                chat_history=fd_chat,
                final_question=session_state.get("final_q", ""),
                sql_query=session_state.get("sql_query", ""),
                result_rows=rows,
                selected_schema=session_state.get("schema_result", {}).get("selected", {})
            )
            # If feedback finished, show log file
            show_log = "<Rating>" in reply

            # Trim out the last rating line before sending to UI
            lines = reply.strip().splitlines()
            if lines and "Estimated user rating" in lines[-1]:
                ui_reply = "\n".join(lines[:-1]).strip()
            else:
                ui_reply = reply.strip()

            # Show only trimmed message to user
            history.append({"role": "assistant", "content": ui_reply})

            session_state["fd_feedback_history"] = fd_chat
            logger.log("FD Feedback/Reply", reply)
            logger.save()
            yield "", history, *update_ui_visibility(session_state, log_file=show_log, feedback_rating=False,
                                                     inputrow=True)
        except Exception as e:
            logger.log("FD Feedback Crash - agent call", str(e))
            reply = "❌ Feedback Agent crashed. Please retry."
            history.append({"role": "assistant", "content": reply})

    return "", history, *update_ui_visibility(session_state, log_file=True, feedback_rating=False,
                                          inputrow=True)
