# === src/ui/events.py ===
import gradio as gr
from src.ui.handlers_FD import (
    handle_user_input,
    process_next_step,
    reset_state,
    handle_yes_click,
    handle_no_click,
    process_rating,
    process_feedback,
)

def bind_event_handlers(elements, session_state):
    """Binds all event listeners to their respective UI elements."""

    # --- Send Button & User Input Submit ---
    elements["send_btn"].click(
        fn=handle_user_input,
        inputs=[elements["user_input"], elements["chatbot"], session_state],
        outputs=[
            elements["user_input"],
            elements["chatbot"],
            elements["feedback_buttons_row"],
            elements["log_file"],
            elements["feedback_rating"],
            elements["feedback_textbox"],
            elements["feedback_submit_btn"],
            session_state,
        ],
    ).then(
        fn=process_next_step,
        inputs=[elements["chatbot"], session_state],
        outputs=[
            elements["chatbot"],
            elements["feedback_buttons_row"],
            elements["log_file"],
            elements["feedback_rating_row"],
            elements["feedback_rating"],
            elements["feedback_textbox"],
            elements["feedback_submit_btn"],
            elements["inputrow"],
            session_state,
        ]
    )

    elements["user_input"].submit(
        fn=handle_user_input,
        inputs=[elements["user_input"], elements["chatbot"], session_state],
        outputs=[
            elements["user_input"],
            elements["chatbot"],
            elements["feedback_buttons_row"],
            elements["log_file"],
            elements["feedback_rating"],
            elements["feedback_textbox"],
            elements["feedback_submit_btn"],
            session_state,
        ],
    ).then(
        fn=process_next_step,
        inputs=[elements["chatbot"], session_state],
        outputs=[
            elements["chatbot"],
            elements["feedback_buttons_row"],
            elements["log_file"],
            elements["feedback_rating_row"],
            elements["feedback_rating"],
            elements["feedback_textbox"],
            elements["feedback_submit_btn"],
            elements["inputrow"],
            session_state,
        ]
    )

    # --- Yes Button ---
    elements["yes_btn"].click(
        fn=handle_yes_click,
        inputs=[elements["chatbot"], session_state],
        outputs=[
            elements["chatbot"],
            elements["feedback_buttons_row"],
            elements["log_file"],
            elements["feedback_rating_row"],
            elements["feedback_rating"],
            elements["feedback_textbox"],
            elements["feedback_submit_btn"],
            elements["inputrow"],
            session_state,
        ],
    ).then( # This .then() is for process_next_step
        fn=process_next_step,
        inputs=[elements["chatbot"], session_state],
        outputs=[ # These outputs must match what process_next_step yields/returns
            elements["chatbot"],
            elements["feedback_buttons_row"],
            elements["log_file"],
            elements["feedback_rating_row"],
            elements["feedback_rating"],
            elements["feedback_textbox"],
            elements["feedback_submit_btn"],
            elements["inputrow"],
            session_state,
        ]
    )

    # --- No Button ---
    elements["no_btn"].click(
        fn=handle_no_click,
        inputs=[elements["chatbot"], session_state],
        outputs=[
            elements["chatbot"],
            elements["feedback_buttons_row"],
            elements["feedback_controls_col"],  # ⬅️ add this line
            elements["feedback_textbox"],
            elements["feedback_submit_btn"],
            elements["inputrow"],
        ]
    )

    # --- Rating Buttons ---
    elements["feedback_rating"].change(
        fn=process_rating,
        inputs=[elements["feedback_rating"], elements["chatbot"], session_state],
        outputs=[
            elements["chatbot"],
            elements["feedback_buttons_row"],
            elements["log_file"],
            elements["feedback_rating_row"],  # <-- ADD THIS LINE
            elements["feedback_rating"],
            elements["feedback_textbox"],
            elements["feedback_submit_btn"],
            elements["inputrow"],
            session_state,
        ]
    )

    # --- Feedback Textbox ---
    # This event updates the session state as the user types. This is correct.
    elements["feedback_textbox"].change(
        fn=lambda t, s: s.update({"feedback_text": t}) or s,
        inputs=[elements["feedback_textbox"], session_state],
        outputs=[session_state],
    )

    # --- Feedback Textbox Submit (via Enter Key) ---
    # This now calls process_feedback directly.
    elements["feedback_textbox"].submit(
        fn=process_feedback,
        inputs=[elements["chatbot"], session_state],
        outputs=[
            elements["chatbot"],
            elements["feedback_buttons_row"],
            elements["log_file"],
            elements["feedback_rating_row"],
            elements["feedback_rating"],
            elements["feedback_textbox"],
            elements["feedback_submit_btn"],
            elements["inputrow"],
            session_state,
        ]
    )



    elements["reset_btn"].click(
        fn=reset_state,
        inputs=[session_state],
        outputs=[
            elements["chatbot"],
            elements["feedback_buttons_row"],  # ✅ Add this line
            elements["log_file"],
            elements["feedback_rating"],
            elements["feedback_textbox"],
            elements["feedback_submit_btn"],
            elements["inputrow"],
            session_state,
        ]
    )
