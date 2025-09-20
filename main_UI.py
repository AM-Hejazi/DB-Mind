from app import build_demo

# Create the Gradio Blocks UI and bind all events
# (build_demo applies shared queue settings)
demo = build_demo()

# Launch the application
if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", share=True, favicon_path="data/icon.png")

# http://127.0.0.1:7860/?__theme=dark
# https://ba8dc27c9f9ddb483b.gradio.live/?__theme=dark
