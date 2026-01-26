# In src/ui/layout.py

import gradio as gr
from src.ui.state import default_session_state
from src.ui.events import bind_event_handlers

def create_ui():
    with gr.Blocks(theme=gr.themes.Default(), css="""
    html, body {
        height: 100%;
        overflow: hidden;
    }
    .gradio-container {
        height: 100vh;
        display: flex;
        flex-direction: column;
        box-sizing: border-box;
    }
    #chatbot {
        flex: 1 1 auto;
        overflow-y: hidden !important;
        min-height: 65vh;
        display: flex;
        flex-direction: column;
    }
    
    #chatbot .wrap {
        overflow-y: auto !important;
        flex: 1;
    }

    #controls-container {
        min-height: 180px;
        overflow-y: auto; 
    }
    """) as demo:
        session_state = default_session_state()

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

        chatbot = gr.Chatbot(
            value=[{"role": "assistant", "content": welcome_message}], #
            elem_id="chatbot",
            label="DB-Mind 1.2-b",
            show_copy_button=True,
            avatar_images=(None, "data/icon.png"),
            type='messages',  # <-- Add this line back
            bubble_full_width=False
        )

        # Auto-scroll script remains the same
        gr.HTML("""
            <script>
            function setupChatboxScroll() {
                const anElement = document.getElementById("chatbot")
                if (!anElement) { return; }

                const scrollableContainer = anElement.querySelector('.wrap');
                if (scrollableContainer) {
                    console.log("✅ Chatbox scrollable container found. Attaching observer.");
                    const scrollToBottom = () => {
                        scrollableContainer.scrollTo({ top: scrollableContainer.scrollHeight, behavior: 'smooth' });
                    };

                    const observer = new MutationObserver((mutations) => {
                        for (const mutation of mutations) {
                            if (mutation.type === 'childList' && mutation.addedNodes.length) {
                                scrollToBottom();
                                break;
                            }
                        }
                    });

                    observer.observe(scrollableContainer, { childList: true });
                    setTimeout(scrollToBottom, 100);
                } else {
                    console.warn("❌ Chatbox inner scrollable area (.wrap) not found. Retrying...");
                }
            }

            const intervalId = setInterval(() => {
                const scrollableContainer = document.querySelector('#chatbot .wrap');
                if (scrollableContainer) {
                    setupChatboxScroll();
                    clearInterval(intervalId);
                }
            }, 500);
            </script>
            """)

        # --- Corrected Controls Layout ---
        # Top-right model selector: user can choose Deepseek or OpenAI
        def _set_model_choice(choice, state_dict):
            try:
                if isinstance(state_dict, dict):
                    state_dict["model_choice"] = choice.lower()
                else:
                    state_dict.update({"model_choice": choice.lower()})
            except Exception:
                state_dict = {"model_choice": choice.lower()}
            return state_dict

        with gr.Row(visible=True) as top_row:
            with gr.Column(scale=1):
                gr.HTML("")
            with gr.Column(scale=0):
                model_dropdown = gr.Dropdown(choices=["Deepseek", "OpenAI"], value="Deepseek", label="Model Provider", elem_id="model-dropdown")
                # update session_state when selection changes
                model_dropdown.change(fn=_set_model_choice, inputs=[model_dropdown, session_state], outputs=[session_state])

        with gr.Column(elem_id="controls-container", scale=0) as controls_container:
            # Row for star rating
            with gr.Row(visible=False) as feedback_rating_row:
                feedback_rating = gr.Radio(
                    choices=["★", "★★", "★★★", "★★★★", "★★★★★"],
                    label="Please rate your experience",
                    interactive=True
                )

            # Row for the main user input
            with gr.Row(elem_id="inputrow") as inputrow:
                user_input = gr.Textbox(
                    placeholder="Type your question here...", container=False, scale=9, autofocus=True)
                send_btn = gr.Button("Send", scale=1)

            # Column for footer controls (log file and reset button)
            with gr.Column(elem_classes="footer-controls") as footer_row:
                log_file = gr.File(label="📁 Download Final Answer Log", visible=False, file_count="single")
                reset_btn = gr.Button("🔄 New Question")

        # --- Dictionary of Elements ---
        elements = {
            "chatbot": chatbot,
            "user_input": user_input,
            "send_btn": send_btn,
            "inputrow": inputrow,
            "feedback_rating_row": feedback_rating_row,
            "feedback_rating": feedback_rating,
            "log_file": log_file,
            "reset_btn": reset_btn,
            "footer_row": footer_row,
            "model_dropdown": model_dropdown,
        }

        bind_event_handlers(elements, session_state)

    return demo
