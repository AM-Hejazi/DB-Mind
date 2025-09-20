import gradio as gr


def handle_star_rating(rating, session_state):
    print("DEBUG: rating received =", rating)
    chat = session_state.get("chat", [])
    chat.append({"role": "user", "content": f"⭐️ User Rating: {rating} star(s)"})
    chat.append({"role": "assistant", "content": f"🙏 Thanks for your rating: {rating}!"})
    return chat, gr.update(visible=False), session_state


with gr.Blocks() as demo:
    session_state = gr.State({"chat": []})
    chatbot = gr.Chatbot(label="Chat", elem_id="chatbox", type="messages")

    # Hidden textbox to store rating value
    feedback_rating = gr.Textbox(
        label="Your Rating",
        visible=False,
        elem_id="star_score"
    )

    with gr.Row(visible=True) as star_row:
        gr.HTML("""
        <style>
        .star-container {
            display: flex;
            justify-content: center;
            margin: 20px 0;
        }
        .star { 
            font-size: 2.6em; 
            color: #ddd; 
            cursor: pointer; 
            padding: 0 4px; 
            transition: color 0.2s;
        }
        .star.filled { color: #ffd700; }
        </style>
        <div class="star-container">
          <span class="star" data-value="1">&#9734;</span>
          <span class="star" data-value="2">&#9734;</span>
          <span class="star" data-value="3">&#9734;</span>
          <span class="star" data-value="4">&#9734;</span>
          <span class="star" data-value="5">&#9734;</span>
        </div>
        <script>
        // Robust initialization that handles Gradio's DOM structure
        function initStars() {
            const stars = document.querySelectorAll('.star');
            let hiddenInput = document.querySelector('input[id$="star_score"]');

            // If not found, try alternative selectors
            if (!hiddenInput) {
                hiddenInput = document.querySelector('input[aria-label="Your Rating"]');
            }
            if (!hiddenInput) {
                hiddenInput = document.querySelector('input[data-testid="textbox"]');
            }

            if (!hiddenInput) {
                console.error("Rating input not found! Will retry...");
                setTimeout(initStars, 300);
                return;
            }

            function fillStars(val) {
                stars.forEach(s => {
                    const starValue = parseInt(s.dataset.value);
                    if (starValue <= val) {
                        s.innerHTML = "&#9733;";
                        s.classList.add("filled");
                    } else {
                        s.innerHTML = "&#9734;";
                        s.classList.remove("filled");
                    }
                });
            }

            stars.forEach(star => {
                star.addEventListener('mouseenter', function() {
                    fillStars(parseInt(this.dataset.value));
                });

                star.addEventListener('mouseleave', function() {
                    fillStars(parseInt(hiddenInput.value) || 0);
                });

                star.addEventListener('click', function() {
                    const value = this.dataset.value;
                    fillStars(value);
                    hiddenInput.value = value;

                    // Create and dispatch a proper input event
                    const event = new Event('input', {
                        bubbles: true,
                        composed: true
                    });
                    hiddenInput.dispatchEvent(event);

                    console.log("Rating submitted:", value);
                });
            });

            fillStars(parseInt(hiddenInput.value) || 0);
            console.log("Stars initialized successfully!");
        }

        // Initialize when Gradio is ready
        document.addEventListener('DOMContentLoaded', initStars);
        window.addEventListener('load', initStars);

        // Gradio-specific initialization
        if (window.gradioApp) {
            window.gradioApp.addEventListener('render', initStars);
        }

        // Initialize after a short delay
        setTimeout(initStars, 500);
        </script>
        """)

    feedback_rating.change(
        fn=handle_star_rating,
        inputs=[feedback_rating, session_state],
        outputs=[chatbot, star_row, session_state]
    )

    demo.load(
        fn=lambda: ([{"role": "assistant", "content": "How was your experience? Please rate:"}],
                    gr.update(visible=True),
                    {"chat": [{"role": "assistant", "content": "How was your experience? Please rate:"}]}),
        inputs=[],
        outputs=[chatbot, star_row, session_state]
    )

demo.launch()