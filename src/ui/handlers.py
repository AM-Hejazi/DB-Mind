# === handlers.py ===
import os
import glob
from datetime import datetime
import gradio as gr

from src.logger import global_logger as logger
from src.retrieval import retrieve_schema_with_llm
from src.clarifier import clarify_question
from src.QFinalizer import finalize_question
from src.query_generator import generate_sql_query, extract_final_sql, extract_explanation
from src.validator import validate_sql
from src.feedback import generate_updated_question
from config import CONFIG

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

logger.log("CONFIG Snapshot", str(CONFIG))

def get_latest_log():
    log_files = sorted(glob.glob("ev_logs/run_*.txt"), key=os.path.getmtime, reverse=True)
    return log_files[0] if log_files else None

# === reset_state ===
def reset_state(session_state):
    for key in session_state:
        session_state[key] = "" if isinstance(session_state[key], str) else None
    logger.log_file = None
    session_state["feedback_rating"] = None
    session_state["feedback_text"] = ""
    session_state["has_welcomed"] = False # <--- ADD THIS LINE
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.log_file = f"ev_logs/run_{timestamp}.txt"

    return (
        # Replace the empty string with the initial message structure
        [{"role": "assistant", "content": welcome_message}],
        gr.update(visible=False),  # log_file
        gr.update(visible=False),  # feedback_rating (Radio)
        gr.update(visible=False),  # feedback_textbox
        gr.update(visible=False),  # feedback_submit_btn
        gr.update(visible=True),  # inputrow
        session_state  # session_state dict
    )


# === update_ui_visibility ===
def update_ui_visibility(session_state, **kwargs):
    for key, value in kwargs.items():
        full_key = f"show_{key}"
        if full_key in session_state:
            session_state[full_key] = value

    log_path = logger.log_file if (
        session_state.get("show_log_file") and logger.log_file and os.path.exists(logger.log_file)
    ) else None

    return (
        gr.update(visible=session_state["show_feedback_buttons_row"]),
        gr.update(visible=session_state["show_log_file"], value=log_path),
        gr.update(visible=session_state["show_feedback_rating"]),
        gr.update(visible=session_state["show_feedback_textbox"]),
        gr.update(visible=session_state.get("show_feedback_submit_btn", False))
    )


# === handle_user_input ===
def handle_user_input(message, history, session_state):
    print(f"DEBUG: handle_user_input - Incoming history length: {len(history)}")
    if history and history[0].get("content"):
        print(f"DEBUG: handle_user_input - First message in history: {history[0]['content'][:50]}...")
    else:
        print("DEBUG: handle_user_input - History is empty or first message content is missing.")

    if not session_state["original_q"]:
        session_state["original_q"] = message
        session_state["initial_user_query"] = message
        logger.log("Original Question", message)

        # Append user's question AFTER ensuring welcome message is there
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": "🔎 Schema Retriever running..."})

        feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
            session_state, feedback_buttons_row=False, feedback_submit_btn=False, log_file=False
        )
        submit_u = gr.update(visible=False)
        return "", history, feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u, session_state

    elif session_state.get("is_clear") and not session_state.get("sql_query"):
        session_state["final_q"] = session_state["original_q"]
        session_state["complexity"] = "Simple"
        logger.log("User Rewrite", "(Skipped - question was clear)")
        logger.log("Final Reformulated Question", session_state["final_q"])
        history.append({"role": "assistant", "content": "⚙️ Generating SQL..."})
        feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
            session_state, feedback_buttons_row=False, feedback_submit_btn=False, log_file=False
        )
        submit_u = gr.update(visible=False)
        return "", history, feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u, session_state

    elif session_state.get("is_clear") and session_state.get("sql_query"):
        feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
            session_state, feedback_buttons_row=False, log_file=False
        )
        submit_u = gr.update(visible=False)
        return "", history, feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u, session_state

    elif not session_state["user_rewrite"]:
        if session_state.get("is_clear") and not session_state.get("sql_query"):
            session_state["final_q"] = session_state["original_q"]
            session_state["complexity"] = "Simple"
            logger.log("User Rewrite", "(Skipped - question was clear)")
            logger.log("Final Reformulated Question", session_state["final_q"])
            history.append({"role": "assistant", "content": "⚙️ Generating SQL..."})
            feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
                session_state, feedback_buttons_row=False, feedback_submit_btn=False, log_file=False
            )
            submit_u = gr.update(visible=False)
            return "", history, feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u, session_state

        session_state["user_rewrite"] = message
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": "✍️ Question Finalizer running..."})
        feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
            session_state, feedback_buttons_row=False, feedback_submit_btn=False, log_file=False
        )
        submit_u = gr.update(visible=False)
        return "", history, feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u, session_state

    feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
        session_state, feedback_buttons_row=False, feedback_submit_btn=False, log_file=False
    )
    submit_u = gr.update(visible=False)
    return "", history, feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u, session_state


# === handle_yes_click ===
def handle_yes_click(history, session_state):
    print("🟢 handle_yes_click triggered")
    print("📜 Incoming history:", history)
    print("📘 Last message:", history[-1]["content"] if history else "EMPTY")

    if not history or not isinstance(history, list) or not history[-1].get("content"):
        history = [{"role": "user", "content": "✅ Yes"}]
    else:
        last_msg = history[-1]["content"]
        if "Did you get your expected results" in last_msg:
            session_state["last_yes_context"] = "validator"
            history.append({"role": "user", "content": "✅ Yes"})
        elif "Use this version?" in last_msg:
            session_state["last_yes_context"] = "qf"
            history.append({"role": "user", "content": "✅ Yes"})
            history.append({"role": "assistant", "content": "⚙️ Generating SQL..."})
        else:
            session_state["last_yes_context"] = None
            history.append({"role": "user", "content": "✅ Yes"})

    print("✅ Returning from handle_yes_click with history length:", len(history))
    print("📤 Final chatbot value will be:", history)

    return (
        history,
        gr.update(visible=False),   # feedback_buttons_row
        gr.update(visible=False),   # log_file
        gr.update(visible=False),   # feedback_rating_row <-- The missing update
        gr.update(visible=True),    # feedback_rating
        gr.update(visible=False),   # feedback_form / textbox
        gr.update(visible=False),   # feedback_submit_btn
        gr.update(visible=False),   # inputrow
        session_state
    )


# === handle_no_click ===
def handle_no_click(history, session_state):
    """
    Handles the user clicking the 'No' button.
    Hides irrelevant controls and shows the feedback form components.
    """
    history.append({"role": "user", "content": "❌ No"})
    history.append({"role": "assistant", "content": "📝 Please describe what you'd like to change."})

    # Return a tuple of updates for each specific component
    return (
        history,
        gr.update(visible=False),  # feedback_buttons_row
        gr.update(visible=True),  # feedback_controls_col  ✅ ADD THIS
        gr.update(visible=True),  # feedback_textbox
        gr.update(visible=True),  # feedback_submit_btn
        gr.update(visible=False),  # inputrow
    )

def process_next_step(history, session_state):
    last = history[-1]["content"]

    print("🔁 process_next_step triggered")
    print("📜 History length:", len(history))
    print("📘 Last message:", history[-1]["content"] if history else "EMPTY")

    if session_state.get("last_yes_context") == "validator":
        print("🟢 YES was for validator flow")
        session_state["last_yes_context"] = None
        history.append({"role": "assistant", "content": "⭐ Please rate your experience using the options below."})
        print("✅ Returning from process_next_step with history length:", len(history))
        feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
            session_state,
            feedback_buttons_row=False,
            log_file=False,
            feedback_rating=True, # This sets the visibility for the Radio component
            feedback_textbox=False,
            feedback_submit_btn=True
        )
        feedback_rating_row_u = gr.update(visible=True)
        yield (
            history,
            feedback_buttons_row_u,
            log_u,
            feedback_rating_row_u, # <--- ENSURE THIS IS PASSED HERE
            rating_u,
            feedback_u,
            submit_u,
            gr.update(visible=False),  # inputrow
            session_state
        )
        return ( # Ensure return also matches yield
            history,
            feedback_buttons_row_u,
            log_u,
            feedback_rating_row_u, # <--- ENSURE THIS IS PASSED HERE
            rating_u,
            feedback_u,
            submit_u,
            gr.update(visible=False),  # inputrow
            session_state
        )


    elif session_state.get("last_yes_context") == "qf":
        # ✅ Let QF flow continue
        session_state["last_yes_context"] = None  # reset
        pass  # Let rest of logic handle "⚙️ Generating SQL..."

    # ---- SCHEMA RETRIEVER ----
    if "Schema Retriever running" in last:
        # Hide YES/NO row
        feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
            session_state, feedback_buttons_row=False, log_file=False)
        yield history, feedback_buttons_row_u, log_u, gr.update(visible=False), rating_u, feedback_u, submit_u, gr.update(visible=False), session_state

        schema_result = retrieve_schema_with_llm(session_state["original_q"])
        session_state["schema_result"] = schema_result
        logger.log("Schema Reasoning Explanation", schema_result["explanation"])
        logger.log("Selected Schema Context", schema_result["selected_schema"])
        if "Table" not in schema_result["selected_schema"]:
            msg = "⚠️ Your question doesn't seem related to our warehouse database schema. Try asking a new valid question about shipments, items, orders, transport units, etc."
            history.append({"role": "assistant", "content": msg})
            return history, *[gr.update(visible=False)] * 7, session_state

        history.append({"role": "assistant", "content": "🧠 Clarifier running..."})
        feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
            session_state, feedback_buttons_row=False, log_file=False)
        yield history, feedback_buttons_row_u, log_u, gr.update(visible=False), rating_u, feedback_u, submit_u, gr.update(visible=False), session_state

        qc_response, is_clear = clarify_question(session_state["original_q"], schema_result["selected_schema"])
        qc_text = qc_response.split("【IS_CLEAR】")[0].strip()
        session_state["qc_feedback"] = qc_text
        session_state["is_clear"] = is_clear
        logger.log("QC is_clear Flag", str(is_clear))
        logger.log("Clarifier Output", qc_text)

        if is_clear:
            session_state["final_q"] = session_state["original_q"]
            session_state["complexity"] = "Simple"
            logger.log("User Rewrite", "(Skipped - question was clear)")
            logger.log("Final Reformulated Question", session_state["final_q"])

            history.append({"role": "assistant", "content": "⚙️ Generating SQL..."})
            feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(session_state, feedback_buttons_row=False, log_file=False)
            yield history, feedback_buttons_row_u, log_u, gr.update(visible=False), rating_u, feedback_u, submit_u, gr.update(visible=False), session_state

            if session_state.get("sql_query"):
                return

            schema_context = session_state["schema_result"]["selected_schema"]
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
            feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(session_state, feedback_buttons_row=False, log_file=False)
            yield history, feedback_buttons_row_u, log_u, gr.update(visible=False), rating_u, feedback_u, submit_u, gr.update(visible=False), session_state

            # ---- VALIDATOR ----
            rows, feedback = validate_sql(final_sql)
            result = "\n".join(str(r) for r in rows) if rows else "(no rows returned)"
            session_state["final_result"] = result

            truncated_rows = rows[:100] if rows else []
            result_preview = "\n".join(str(r) for r in truncated_rows) or "(no rows returned)"

            history.append({
                "role": "assistant",
                "content": (
                    f"🧠 **Query Explanation:**\n{explanation}\n\n"
                    f"📄 **Final SQL Query:**\n```sql\n{final_sql}\n```\n\n"
                    f"📦 **Top 100 Results:**\n```\n{result_preview}\n```"
                )
            })

            log_path = logger.log_file
            # ---- FEEDBACK PROMPT ----
            history.append({"role": "assistant",
                            "content": "<span style='color: lightgreen;'>✅ Did you get your expected results</span>"})

            feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
                session_state,
                feedback_buttons_row=True,
                log_file=False,
                feedback_rating=False,
                feedback_textbox=False,
                feedback_submit_btn=False
            )
            row_u = gr.update(visible=True)  # ✅ Show the rating row container itself
            yield history, feedback_buttons_row_u, log_u, row_u, rating_u, feedback_u, submit_u, gr.update(
                visible=False), session_state
            return history, feedback_buttons_row_u, log_u, row_u, rating_u, feedback_u, submit_u, gr.update(visible=False), session_state

        # If not clear, show clarification message, keep feedback row hidden
        history.append({"role": "assistant", "content": qc_text})
        history.append({"role": "assistant", "content": "💬 Please respond so I can finalize your question."})
        feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
            session_state,
            feedback_buttons_row=False,
            log_file=False
        )
        yield history, feedback_buttons_row_u, log_u, gr.update(visible=False), rating_u, feedback_u, submit_u, gr.update(
            visible=True), session_state

    # ---- QUESTION FINALIZER ----
    if "Question Finalizer running" in last:
        feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
            session_state,
            feedback_buttons_row=False,
            log_file=False
        )
        yield history, feedback_buttons_row_u, log_u, gr.update(visible=False), rating_u, feedback_u, submit_u, gr.update(
            visible=False), session_state

        if session_state.get("is_clear"):
            # ... (code before the return)
            yield history, feedback_buttons_row_u, log_u, gr.update(
                visible=False), rating_u, feedback_u, submit_u, gr.update(
                visible=False), session_state

            # CORRECTED RETURN:
            return (
                history,
                gr.update(visible=False),  # feedback_buttons_row
                gr.update(visible=False),  # log_file
                gr.update(visible=False),  # feedback_rating_row
                gr.update(visible=False),  # feedback_rating
                gr.update(visible=False),  # feedback_textbox
                gr.update(visible=False),  # feedback_submit_btn
                gr.update(visible=False),  # inputrow
                session_state
            )
        else:
            if not any("Question Finalizer running" in msg["content"] for msg in history):
                history.append({"role": "assistant", "content": "✍️ Question Finalizer running..."})
            feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
                session_state,
                feedback_buttons_row=False,
                log_file=False
            )
            yield history, feedback_buttons_row_u, log_u, gr.update(visible=False), rating_u, feedback_u, submit_u, gr.update(
                visible=False), session_state
            final_q, complexity = finalize_question(
                original_q=session_state["original_q"],
                feedback=session_state["qc_feedback"],
                user_rewrite=session_state["user_rewrite"]
            )
            session_state["final_q"] = final_q
            session_state["complexity"] = complexity
            logger.log("User Rewrite", session_state["user_rewrite"])
            logger.log("Final Reformulated Question", final_q)
            logger.log("Question Complexity Class", complexity)
            history[-1] = {
                "role": "assistant",
                "content": f"✍️ Final reformulated question:\n\n**{final_q}**\n\n✅ Use this version?"
            }
            feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
                session_state,
                feedback_buttons_row=True,  # ✅ Fix: this makes the buttons show
                log_file=False
            )

            yield history, feedback_buttons_row_u, log_u, gr.update(visible=False), rating_u, feedback_u, submit_u, gr.update(
                visible=False), session_state
            return

    # ---- SQL GENERATOR ----
    if "Generating SQL" in last:
        feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
            session_state,
            feedback_buttons_row=False,
            log_file=False
        )
        yield history, feedback_buttons_row_u, log_u, gr.update(visible=False), rating_u, feedback_u, submit_u, gr.update(
            visible=False), session_state

        if session_state.get("sql_query"):
            return

        try:
            schema_context = session_state["schema_result"]["selected_schema"]
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
            feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
                session_state,
                feedback_buttons_row=False,
                log_file=False
            )
            yield history, feedback_buttons_row_u, log_u, gr.update(visible=False), rating_u, feedback_u, submit_u, gr.update(
                visible=False), session_state

            # VALIDATOR
            rows, feedback = validate_sql(final_sql)
            result = "\n".join(str(r) for r in rows) if rows else "(no rows returned)"
            session_state["final_result"] = result

            truncated_rows = rows[:100] if rows else []
            result_preview = "\n".join(str(r) for r in truncated_rows) or "(no rows returned)"

            history.append({
                "role": "assistant",
                "content": (
                    f"🧠 **Query Explanation:**\n{explanation}\n\n"
                    f"📄 **Final SQL Query:**\n```sql\n{final_sql}\n```\n\n"
                    f"📦 **Top 100 Results:**\n```\n{result_preview}\n```"
                )
            })

            log_path = logger.log_file
            history.append({"role": "assistant",
                            "content": "<span style='color: lightgreen;'>✅ Did you get your expected results</span>"})

            feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
                session_state,
                feedback_buttons_row=True,
                log_file=False,
                feedback_rating=False,
                feedback_textbox=False,
                feedback_submit_btn=False
            )
            row_u = gr.update(visible=True)  # ✅ Show the rating row container itself
            yield history, feedback_buttons_row_u, log_u, row_u, rating_u, feedback_u, submit_u, gr.update(
                visible=False), session_state
            return history, feedback_buttons_row_u, log_u, row_u, rating_u, feedback_u, submit_u, gr.update(
                visible=False), session_state


        except Exception as e:
            history.append({
                "role": "assistant",
                "content": f"❌ Unexpected error:\n\n[UNHANDLED ERROR during SQL execution]\n{str(e)}"
            })
            history.append({"role": "assistant",
                            "content": "<span style='color: lightgreen;'>✅ Did you get your expected results</span>"})

            feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
                session_state,
                feedback_buttons_row=True,
                log_file=False,
                feedback_rating=False,
                feedback_textbox=False,
                feedback_submit_btn=False
            )
            row_u = gr.update(visible=True)  # ✅ Show the rating row container itself
            yield history, feedback_buttons_row_u, log_u, row_u, rating_u, feedback_u, submit_u, gr.update(
                visible=False), session_state
            return history, feedback_buttons_row_u, log_u, row_u, rating_u, feedback_u, submit_u, gr.update(
                visible=False), session_state

    # ---- FALLBACK: always hide feedback row at end ----
    feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
        session_state,
        feedback_buttons_row=False,
        log_file=False,
        feedback_rating=False,
        feedback_textbox=False,
        feedback_submit_btn=False
    )
    return history, feedback_buttons_row_u, log_u, gr.update(visible=False), rating_u, feedback_u, submit_u, gr.update(
        visible=False), session_state

def process_rating(selected, history, session_state):
    session_state["feedback_rating"] = selected
    logger.log("User Satisfaction", f"⭐ {selected}")
    logger.save()

    history.append({"role": "user", "content": f"⭐️ Rating: {selected}"})
    history.append({"role": "assistant", "content": f"🙏 Thanks for your rating: {selected}!"})

    session_state["chat"] = history

    feedback_buttons_row_u, log_u, rating_u, feedback_u, submit_u = update_ui_visibility(
        session_state,
        feedback_buttons_row=False,
        feedback_rating=False,
        log_file=True,
        feedback_submit_btn=False,
        feedback_textbox=False
    )

    # Explicitly define visibility for the row components returned
    feedback_rating_row_u = gr.update(visible=False) # Hide the container row for ratings
    inputrow_visibility_update = gr.update(visible=False) # Hide the input row

    return (
        history,
        feedback_buttons_row_u,
        log_u,
        feedback_rating_row_u,
        rating_u,
        feedback_u,
        submit_u,
        inputrow_visibility_update,
        session_state
    )


# === In src/ui/handlers.py ===

def process_feedback(history, session_state):
    """
    Handles the submission of user feedback, and re-runs the full pipeline.
    """
    feedback_text = session_state.get("feedback_text", "").strip()

    # Update UI immediately to acknowledge submission
    history.append({"role": "user", "content": feedback_text})
    history.append({"role": "assistant", "content": "💬 Thanks for your feedback! Re-evaluating your request..."})

    # Immediately hide the feedback controls
    yield (
        history,
        gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
        gr.update(visible=False), gr.update(visible=False, value=""), gr.update(visible=False),
        gr.update(visible=False), session_state
    )

    if not feedback_text:
        history.append({"role": "assistant", "content": "⚠️ Feedback was empty. Please try again."})
        # Re-show the feedback controls
        yield (
            history,
            gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), gr.update(visible=True), gr.update(visible=True),
            gr.update(visible=False), session_state
        )
        return

    # Helper function for creating UI updates
    def make_updates(h, s, show_final_feedback=False):
        return (
            h,
            gr.update(visible=show_final_feedback), gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), gr.update(visible=False, value=""), gr.update(visible=False),
            gr.update(visible=False), s
        )

    # --- Main Pipeline Logic ---
    logger.log("User Satisfaction", "❌ User rejected result")
    logger.log("User Feedback", feedback_text)

    updated_question = generate_updated_question(
        Original_Q_For_FA_Prompt=session_state["initial_user_query"],
        Finalized_q=session_state["final_q"],
        sql_query=session_state["sql_query"],
        result_preview=session_state["final_result"],
        user_feedback=feedback_text
    )
    session_state["original_q"] = updated_question
    session_state["final_q"] = updated_question
    session_state["sql_query"] = ""
    session_state["feedback_text"] = ""
    session_state["feedback_rating"] = None

    history.append({
        "role": "assistant",
        "content": f"🔄 **New Question based on your feedback:**\n\n> *{updated_question}*"
    })
    history.append({"role": "assistant", "content": "🔎 Schema Retriever running..."})
    yield make_updates(history, session_state)

    # --- Re-run the pipeline ---
    schema_result = retrieve_schema_with_llm(updated_question)
    session_state["schema_result"] = schema_result

    history.append({"role": "assistant", "content": "⚙️ Generating SQL..."})
    yield make_updates(history, session_state)

    cg_response = generate_sql_query(
        updated_question,
        schema_result["selected"],
        session_state.get("complexity", "Simple")
    )
    final_sql = extract_final_sql(cg_response)
    explanation = extract_explanation(cg_response)

    history.append({"role": "assistant", "content": "🔍 Validating result with SQL Server..."})
    yield make_updates(history, session_state)

    rows, feedback = validate_sql(final_sql)
    session_state["final_result"] = "\n".join(str(r) for r in rows) if rows else "(no rows returned)"

    # ✅ FIX 1: Correctly generate the result preview
    truncated_rows = rows[:100] if rows else []
    result_preview = "\n".join(str(r) for r in truncated_rows) or "(no rows returned)"

    history.append({
        "role": "assistant",
        "content": (
            f"🧠 **Query Explanation:**\n{explanation}\n\n"
            f"📄 **Final SQL Query:**\n```sql\n{final_sql}\n```\n\n"
            f"📦 **Top 100 Results:**\n```\n{result_preview}\n```"
        )
    })
    history.append({"role": "assistant",
                    "content": "<span style='color: lightgreen;'>✅ Did you get your expected results</span>"})

    # ✅ FIX 2: Use 'yield' for the final update for better reliability
    yield make_updates(history, session_state, show_final_feedback=True)
    return

