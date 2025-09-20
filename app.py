import os
from src.ui.layout import create_ui


def build_demo():
    demo = create_ui()
    demo.queue(concurrency_count=1, max_size=10)
    return demo


demo = build_demo()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port, share=False, show_api=False)
