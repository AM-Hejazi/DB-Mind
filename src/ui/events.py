# === src/ui/events.py ===
import gradio as gr
from src.ui.handlers_FD import (
    handle_user_input,
    process_next_step,
    reset_state,
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
            elements["log_file"],
            elements["feedback_rating"],
            elements["inputrow"],
            session_state,
        ],
    ).then(
        fn=process_next_step,
        inputs=[elements["chatbot"], session_state],
        outputs=[
            elements["user_input"],
            elements["chatbot"],
            elements["log_file"],
            elements["feedback_rating"],
            elements["inputrow"],
            session_state,
        ],
    )


    elements["user_input"].submit(
        fn=handle_user_input,
        inputs=[elements["user_input"], elements["chatbot"], session_state],
        outputs=[
            elements["user_input"],
            elements["chatbot"],
            elements["log_file"],
            elements["feedback_rating"],
            elements["inputrow"],
            session_state,
        ],
    ).then(
        fn=process_next_step,
        inputs=[elements["chatbot"], session_state],
        outputs=[
            elements["user_input"],
            elements["chatbot"],
            elements["log_file"],
            elements["feedback_rating"],
            elements["inputrow"],
            session_state,
        ],
    )


    elements["reset_btn"].click(
        fn=reset_state,
        inputs=[session_state],
        outputs=[
            elements["user_input"],  # reset text
            elements["chatbot"],  # update history
            elements["log_file"],  # update file
            elements["feedback_rating"],  # update rating
            elements["inputrow"],  # show/hide input
            session_state,  # keep session
        ]

    )
