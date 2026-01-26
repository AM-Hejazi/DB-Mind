# In src/ui/layout.py

import gradio as gr
from src.ui.state import default_session_state
from src.ui.events import bind_event_handlers

def create_ui():
    with gr.Blocks(theme=gr.themes.Default(), css="""
    /* Allow page scrolling for small screens */
    html, body {
        height: 100%;
        margin: 0;
        padding: 0;
        overflow: auto;
    }
    
    .gradio-container {
        min-height: 100vh !important;
        display: flex !important;
        flex-direction: column !important;
        padding: 16px !important;
        box-sizing: border-box !important;
    }
    
    /* Header area with title and model dropdown */
    #header-row {
        flex: 0 0 auto;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    #logo-img {
        width: 32px !important;
        height: 32px !important;
        min-width: 32px !important;
        min-height: 32px !important;
    }
    
    #logo-img img {
        object-fit: contain;
        border-radius: 4px;
    }
    
    #model-selector-container {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-left: auto;
    }
    
    #model-selector-container label {
        margin: 0;
        white-space: nowrap;
        font-size: 14px;
    }
    
    /* Main content area - takes remaining space */
    #main-content-row {
        flex: 1 1 auto;
        display: flex !important;
        min-height: 400px;
        max-height: 70vh;
        overflow: hidden;
    }
    
    /* Chatbot container - fixed height with internal scroll */
    #chatbot-column {
        flex: 1 1 auto;
        display: flex !important;
        flex-direction: column !important;
        min-height: 400px;
    }
    
    #chatbot {
        flex: 1 1 auto !important;
        min-height: 400px !important;
        max-height: 100% !important;
        display: flex !important;
        flex-direction: column !important;
        overflow: hidden !important;
    }
    
    #chatbot .wrap {
        flex: 1 1 auto !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        min-height: 0 !important;
    }
    
    #model-dropdown {
        min-width: 150px;
    }
    
    /* Controls container - fixed at bottom */
    #controls-container {
        flex: 0 0 auto;
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid #444;
        max-height: 160px;
    }
    
    #inputrow {
        margin-bottom: 6px;
    }
    
    #inputrow input {
        font-size: 14px;
    }
    
    /* Make footer controls inline */
    .footer-controls {
        display: flex;
        flex-direction: row;
        gap: 12px;
        align-items: center;
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

        # --- Header Row with Title and Model Selector ---
        with gr.Row(elem_id="header-row") as header_row:
            with gr.Column(scale=0, min_width=50):
                gr.Image("data/icon.png", height=32, width=32, show_label=False, show_download_button=False, container=False, elem_id="logo-img")
            with gr.Column(scale=4):
                gr.HTML("<h2 style='margin: 0; padding: 0; line-height: 32px;'>DB-Mind 1.2-b</h2>")
            with gr.Column(elem_id="model-selector-container", scale=0, min_width=180):
                model_dropdown = gr.Dropdown(
                    choices=["Deepseek", "OpenAI"], 
                    value="Deepseek", 
                    label="",
                    container=False,
                    elem_id="model-dropdown"
                )
        
        # --- Main Content: Chatbot ---
        with gr.Row(elem_id="main-content-row") as main_content:
            with gr.Column(elem_id="chatbot-column"):
                chatbot = gr.Chatbot(
                    value=[{"role": "assistant", "content": welcome_message}],
                    elem_id="chatbot",
                    label="Chatbot",
                    show_copy_button=True,
                    avatar_images=(None, "data/icon.png"),
                    type='messages',
                    bubble_full_width=False
                )

        # Auto-scroll script - automatically scrolls to bottom on new messages
        gr.HTML("""
            <script>
            (function() {
                let scrollContainer = null;
                let observer = null;
                
                function scrollToBottom() {
                    if (!scrollContainer) return;
                    scrollContainer.scrollTop = scrollContainer.scrollHeight;
                }
                
                function findAndSetupScroll() {
                    const chatbot = document.getElementById("chatbot");
                    if (!chatbot) return false;
                    
                    // Try multiple selectors to find the scrollable container
                    const selectors = [
                        '.wrap.svelte-1ed2p3z',
                        '.wrap',
                        '.overflow-y-auto',
                        '.scroll-container',
                        '[class*="overflow"]'
                    ];
                    
                    for (const selector of selectors) {
                        const container = chatbot.querySelector(selector);
                        if (container && container.scrollHeight > container.clientHeight) {
                            scrollContainer = container;
                            console.log("✅ Found chatbot scroll container:", selector);
                            break;
                        }
                    }
                    
                    // Fallback: use the first scrollable element
                    if (!scrollContainer) {
                        const elements = chatbot.querySelectorAll('*');
                        for (const el of elements) {
                            if (el.scrollHeight > el.clientHeight) {
                                scrollContainer = el;
                                console.log("✅ Found scrollable element via fallback");
                                break;
                            }
                        }
                    }
                    
                    if (!scrollContainer) {
                        console.warn("❌ No scrollable container found");
                        return false;
                    }
                    
                    // Setup MutationObserver to watch for changes
                    if (observer) observer.disconnect();
                    
                    observer = new MutationObserver(() => {
                        requestAnimationFrame(scrollToBottom);
                    });
                    
                    // Observe the chatbot and all descendants
                    observer.observe(chatbot, {
                        childList: true,
                        subtree: true,
                        characterData: true,
                        attributes: false
                    });
                    
                    // Initial scroll
                    setTimeout(scrollToBottom, 200);
                    console.log("✅ Auto-scroll enabled");
                    return true;
                }
                
                // Try to setup immediately
                if (!findAndSetupScroll()) {
                    // If not ready, keep trying
                    let attempts = 0;
                    const interval = setInterval(() => {
                        if (findAndSetupScroll() || ++attempts > 20) {
                            clearInterval(interval);
                            if (attempts > 20) {
                                console.error("❌ Failed to setup auto-scroll");
                            }
                        }
                    }, 500);
                }
                
                // Re-scroll on window resize
                window.addEventListener('resize', scrollToBottom);
            })();
            </script>
            """)

        # --- Model dropdown event handler ---
        def _set_model_choice(choice, state_dict):
            from config import set_models_for_provider
            try:
                if isinstance(state_dict, dict):
                    state_dict["model_choice"] = choice.lower()
                else:
                    state_dict.update({"model_choice": choice.lower()})
            except Exception:
                state_dict = {"model_choice": choice.lower()}
            # Update CONFIG models based on the selected provider
            set_models_for_provider(choice)
            return state_dict
        
        model_dropdown.change(
            fn=_set_model_choice, 
            inputs=[model_dropdown, session_state], 
            outputs=[session_state]
        )

        # --- Controls Container (Fixed at Bottom) ---
        with gr.Column(elem_id="controls-container") as controls_container:
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
                    placeholder="Type your question here...", 
                    container=False, 
                    scale=9, 
                    autofocus=True
                )
                send_btn = gr.Button("Send", scale=1, variant="primary")

            # Row for footer controls (log file and reset button) - side by side
            with gr.Row(elem_classes="footer-controls") as footer_row:
                log_file = gr.File(
                    label="📁 Download Log", 
                    visible=False, 
                    file_count="single",
                    scale=3
                )
                reset_btn = gr.Button("🔄 New Question", scale=1, size="sm")

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
