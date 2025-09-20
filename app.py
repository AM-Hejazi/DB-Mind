import os
import gradio as gr
from src.ui.layout import create_ui


def build_demo():
    demo = create_ui()
    demo.queue(max_size=10)
    return demo

# Work around a Gradio client schema bug (bool JSON Schema)
try:
    import gradio_client.utils as _gc_utils  # type: ignore

    _orig_json_schema_to_python_type = _gc_utils.json_schema_to_python_type

    def _safe_json_schema_to_python_type(schema):  # type: ignore
        try:
            if isinstance(schema, bool):
                return "Any"
            return _orig_json_schema_to_python_type(schema)
        except Exception:
            return "Any"

    _gc_utils.json_schema_to_python_type = _safe_json_schema_to_python_type  # type: ignore
except Exception:
    # If patching fails, proceed; app may still work locally
    pass

demo = build_demo()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    launch_kwargs = {
        "show_api": False,
        "max_threads": 1,
    }

    if os.environ.get("HF_SPACE_ID") or os.environ.get("SPACE_ID"):
        launch_kwargs.update(server_name="0.0.0.0", server_port=port, share=False)
    else:
        launch_kwargs.update(server_name="127.0.0.1", server_port=port, share=True, favicon_path="data/icon.png")

    demo.launch(**launch_kwargs)
