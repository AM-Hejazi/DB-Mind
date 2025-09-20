import os
from src.ui.layout import create_ui


def build_demo():
    demo = create_ui()
    demo.queue(max_size=10)
    return demo


demo = build_demo()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    launch_kwargs = {
        "show_api": False,
        "max_threads": 1,
    }

    if os.environ.get("HF_SPACE_ID") or os.environ.get("SPACE_ID"):
        launch_kwargs.update(server_name="0.0.0.0", server_port=port, share=True)
    else:
        launch_kwargs.update(server_name="127.0.0.1", server_port=port, share=True, favicon_path="data/icon.png")

    demo.launch(**launch_kwargs)
