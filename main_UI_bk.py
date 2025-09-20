import gradio as gr
import os
import glob
from src.clarifier import clarify_question
from src.QFinalizer import finalize_question
from src.query_generator import generate_sql_query, extract_final_sql, extract_explanation
from src.validator import validate_sql
from src.retrieval import retrieve_schema_with_llm
from src.logger import global_logger as logger
from config import CONFIG

logger.log("CONFIG Snapshot", str(CONFIG))

def get_latest_log():
    log_files = sorted(glob.glob("logs/run_*.txt"), key=os.path.getmtime, reverse=True)
    return log_files[0] if log_files else None

def reset_state(session_state):
    for key in session_state:
        session_state[key] = "" if isinstance(session_state[key], str) else None
    return "", [], gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), session_state


def update_visibility(yes_visible=False, no_visible=False, log_path=None):
    yes_btn_update = gr.update(visible=yes_visible)
    no_btn_update = gr.update(visible=no_visible)
    log_file_update = gr.update(visible=True, value=log_path) if log_path else gr.update(visible=False)
    return yes_btn_update, no_btn_update, log_file_update

def handle_user_input(message, history, session_state):
    # Step 0: New question
    if not session_state["original_q"]:
        session_state["original_q"] = message
        logger.log("Original Question", message)
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": "🔎 Schema Retriever running..."})
        return "", history, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), session_state

    # Step 1: Auto-skip clarification if question is clear and no SQL yet
    elif session_state.get("is_clear") and not session_state.get("sql_query"):
        # Set the final question and skip rewrite
        session_state["final_q"] = session_state["original_q"]
        session_state["complexity"] = "Simple"
        logger.log("User Rewrite", "(Skipped - question was clear)")
        logger.log("Final Reformulated Question", session_state["final_q"])

        # ⚠️ This is key: forcibly append SQL trigger message
        history.append({"role": "assistant", "content": "⚙️ Generating SQL..."})
        return "", history, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), session_state


    elif session_state.get("is_clear") and session_state.get("sql_query"):
        return "", history, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), session_state

    # Step 1
    elif not session_state["user_rewrite"]:
        # 🚀 If the question was already marked clear, SKIP QF and go directly to SQL
        if session_state.get("is_clear") and not session_state.get("sql_query"):
            session_state["final_q"] = session_state["original_q"]
            session_state["complexity"] = "Simple"
            logger.log("User Rewrite", "(Skipped - question was clear)")
            logger.log("Final Reformulated Question", session_state["final_q"])
            history.append({"role": "assistant", "content": "⚙️ Generating SQL..."})
            return "", history, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), session_state

        # 🔁 Otherwise, go to QF rewrite
        session_state["user_rewrite"] = message
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": "✍️ Question Finalizer running..."})
        return "", history, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), session_state



    # Step 2
    elif session_state["final_q"] and not session_state["sql_query"]:
        history.append({"role": "user", "content": message})
        if message.strip().lower() != "y":
            history.append({"role": "assistant", "content": "❌ Discarded. Please restart."})
            return "", history, gr.update(visible=False), gr.update(visible=False), gr.update(
                visible=False), session_state
        history.append({"role": "assistant", "content": "⚙️ Generating SQL..."})
        return "", history, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), session_state

    yes_u, no_u, log_u = update_visibility(False, False, None)
    return "", history, yes_u, no_u, log_u, session_state

def process_next_step(history, session_state):
    last = history[-1]["content"]

    if "Schema Retriever running" in last:
        yes_u, no_u, log_u = update_visibility(False, False, None)
        yield history, yes_u, no_u, log_u, session_state

        schema_result = retrieve_schema_with_llm(session_state["original_q"])
        session_state["schema_result"] = schema_result
        logger.log("Schema Reasoning Explanation", schema_result["explanation"])
        logger.log("Selected Schema Context", schema_result["selected_schema"])

        history.append({"role": "assistant", "content": "🧠 Clarifier running..."})
        yes_u, no_u, log_u = update_visibility(False, False, None)
        yield history, yes_u, no_u, log_u, session_state

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
            yes_u, no_u, log_u = update_visibility(False, False, None)
            yield history, yes_u, no_u, log_u, session_state

            if session_state.get("sql_query"):
                return

            schema_context = session_state["schema_result"]["selected"]
            cg_response = generate_sql_query(
                session_state["final_q"],
                schema_context,
                session_state["complexity"]
            )
            session_state["sql_query"] = cg_response
            logger.log("Generated SQL Query", cg_response)

            # Extract tagged parts before validation
            explanation = extract_explanation(cg_response)
            final_sql = extract_final_sql(cg_response)

            history.append({"role": "assistant", "content": "🔍 Validating result with SQL Server..."})
            yes_u, no_u, log_u = update_visibility(False, False, None)
            yield history, yes_u, no_u, log_u, session_state

            # Validate raw SQL only
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

            logger.log("Validator Result Rows", result)
            logger.save()
            success_path = logger.log_file.replace(".txt", "__SUCCESS.txt")
            if not logger.log_file.endswith("__SUCCESS.txt"):
                os.rename(logger.log_file, success_path)
                logger.log_file = success_path

            log_path = logger.log_file
            yes_u, no_u, log_u = update_visibility(False, False, log_path)
            yield history, yes_u, no_u, log_u, session_state
            return

        history.append({"role": "assistant", "content": qc_text})
        history.append({"role": "assistant", "content": "💬 Please respond so I can finalize your question."})
        yes_u, no_u, log_u = update_visibility(True, True, None)
        yield history, yes_u, no_u, log_u, session_state

    if "Question Finalizer running" in last:
        yes_u, no_u, log_u = update_visibility(False, False, None)
        yield history, yes_u, no_u, log_u, session_state
        if session_state.get("is_clear"):
            session_state["final_q"] = session_state["original_q"]
            session_state["complexity"] = "Simple"
            logger.log("User Rewrite", "(Skipped - original question was clear)")
            logger.log("Final Reformulated Question", session_state["final_q"])
            history[-1] = {"role": "assistant", "content": "⚙️ Generating SQL..."}
            yes_u, no_u, log_u = update_visibility(False, False, None)
            yield history, yes_u, no_u, log_u, session_state
            return None
        else:
            if not any("Question Finalizer running" in msg["content"] for msg in history):
                history.append({"role": "assistant", "content": "✍️ Question Finalizer running..."})
            yes_u, no_u, log_u = update_visibility(False, False, None)
            yield history, yes_u, no_u, log_u, session_state
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
            yes_u, no_u, log_u = update_visibility(True, True, None)
            yield history, yes_u, no_u, log_u, session_state
            return

    if "Generating SQL" in last:
        yes_u, no_u, log_u = update_visibility(False, False, None)
        yield history, yes_u, no_u, log_u, session_state

        if session_state.get("sql_query"):
            return

        try:
            schema_context = session_state["schema_result"]["selected"]
            cg_response = generate_sql_query(
                session_state["final_q"],
                schema_context,
                session_state["complexity"]
            )
            session_state["sql_query"] = cg_response
            logger.log("Generated SQL Query", cg_response)

            # Extract tagged parts before validation
            explanation = extract_explanation(cg_response)
            final_sql = extract_final_sql(cg_response)

            history.append({"role": "assistant", "content": "🔍 Validating result with SQL Server..."})
            yes_u, no_u, log_u = update_visibility(False, False, None)
            yield history, yes_u, no_u, log_u, session_state

            # Validate raw SQL only
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

            success_path = logger.log_file.replace(".txt", "__SUCCESS.txt")
            if not logger.log_file.endswith("__SUCCESS.txt"):
                os.rename(logger.log_file, success_path)
                logger.log_file = success_path

            log_path = logger.log_file
            yes_u, no_u, log_u = update_visibility(False, False, log_path)
            yield history, yes_u, no_u, log_u, session_state
            return

        except Exception as e:
            error_msg = f"[UNHANDLED ERROR during SQL execution]\n{str(e)}"
            logger.log("Validation Status", "❌ Exception")
            logger.log("Validator Feedback", error_msg)
            logger.save()
            history[-1] = {"role": "assistant", "content": f"❌ Unexpected error:\n\n{error_msg}"}
            log_path = get_latest_log()
            yes_u, no_u, log_u = update_visibility(False, False, log_path)
            yield history, yes_u, no_u, log_u, session_state
            return None

    yes_u, no_u, log_u = update_visibility(False, False, None)
    yield history, yes_u, no_u, log_u, session_state



# --- UI ---
with gr.Blocks(theme=gr.themes.Base(), css="""
body, html, #root {
    margin: 0;
    height: 100vh;
    overflow: hidden;
    background-color: #121212;
    font-family: 'Segoe UI', sans-serif;
}
.chat-container {
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
    padding: 24px;
    box-sizing: border-box;
    background-color: #1e1e1e;
    gap: 12px;
}

#chatbox {
    flex: 1;
    overflow-y: auto !important;
    background-color: #181818;
    padding: 16px;
    border-radius: 12px;
    border: 1px solid #333;
    min-height: 300px;  /* ✅ Prevent collapse during transient state */
    max-height: calc(100vh - 200px);  /* ✅ Reserve space for input */
}

#chatbox .message {
    padding: 10px 14px;
    margin-bottom: 12px;
    border-radius: 8px;
    line-height: 1.6;
}

#chatbox .user {
    background-color: #333;
    text-align: right;
    margin-left: auto;
}

#chatbox .assistant {
    background-color: #2a2a2a;
    margin-right: auto;
    white-space: pre-wrap;
    font-family: monospace;
}

#inputrow {
    border-top: 1px solid #444;
    padding: 8px 0;
    background-color: #1e1e1e;
    position: sticky;
    bottom: 0;
    z-index: 10;
}
""") as demo:
    session_state = gr.State({
        "original_q": "",
        "qc_feedback": "",
        "user_rewrite": "",
        "final_q": "",
        "explanation" :"",
        "schema_result": None,
        "sql_query": "",
        "final_result": "",
        "is_clear": False
    })

    with gr.Column(elem_classes="chat-container"):
        # 🧠 Title Header with Icon
        gr.HTML("""
            <div style='display: flex; align-items: center; gap: 12px; font-size: 22px; font-weight: bold; color: #f5f5f5;'>
                <svg width="28" height="28" viewBox="0 0 24 24" fill="#f5f5f5" xmlns="http://www.w3.org/2000/svg">
                    <path d="M4 10a8 8 0 1116 0v2a2 2 0 01-2 2h-1v-2h1v-2a6 6 0 10-12 0v2h1v2H6a2 2 0 01-2-2v-2z"/>
                    <circle cx="9" cy="12" r="1.5"/>
                    <circle cx="15" cy="12" r="1.5"/>
                </svg>
                WAMind-Chatbot
            </div>
        """)

        chatbot = gr.Chatbot(elem_id="chatbox", type="messages", show_label=False)
        # Welcome message (shown before user input)
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

        chatbot.value = [{"role": "assistant", "content": welcome_message}]

        with gr.Row(elem_id="inputrow"):
            user_input = gr.Textbox(placeholder="Type your question here...", container=False, scale=9, autofocus=True)
            send_btn = gr.Button("Send", scale=1)
            yes_btn = gr.Button("✅ Yes", visible=False)
            no_btn = gr.Button("❌ No", visible=False)

        log_file = gr.File(label="📁 Download Final Answer Log", visible=False)
        reset_btn = gr.Button("🔄 New Question")

    send_btn.click(
        fn=handle_user_input,
        inputs=[user_input, chatbot, session_state],
        outputs=[user_input, chatbot, yes_btn, no_btn, log_file, session_state]

    ).then(
    fn=process_next_step,
    inputs=[chatbot, session_state],
    outputs=[chatbot, yes_btn, no_btn, log_file, session_state])


    yes_btn.click(
        fn=lambda h, s: (
            h + [{"role": "user", "content": "✅ Yes"}] +
            [{"role": "assistant", "content": "⚙️ Generating SQL..."}],
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),  # <-- log_file visibility
            s
        ),
        inputs=[chatbot, session_state],
        outputs=[chatbot, yes_btn, no_btn, log_file, session_state]

    ).then(
    fn=process_next_step,
    inputs=[chatbot, session_state],
    outputs=[chatbot, yes_btn, no_btn, log_file, session_state])


    no_btn.click(
        fn=lambda h, s: (
            h + [{"role": "user", "content": "❌ No"}] +
            [{"role": "assistant", "content": "❌ Discarded. Please restart."}],
            gr.update(visible=False),
            gr.update(visible=False),
            s
        ),
        inputs=[chatbot, session_state],
        outputs=[chatbot, yes_btn, no_btn, log_file, session_state])

    user_input.submit(
        fn=handle_user_input,
        inputs=[user_input, chatbot, session_state],
        outputs=[user_input, chatbot, yes_btn, no_btn, log_file, session_state]
    ).then(
    fn=process_next_step,
    inputs=[chatbot, session_state],
    outputs=[chatbot, yes_btn, no_btn, log_file, session_state])

    reset_btn.click(
        fn=reset_state,
        inputs=[session_state],
        outputs=[user_input, chatbot, yes_btn, no_btn, log_file, session_state]
    )
demo.launch(server_name="0.0.0.0", share=True)



