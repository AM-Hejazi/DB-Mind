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

    # Optional password protection via env vars
    # Supports either APP_USERNAME + APP_PASSWORD or APP_AUTH="u1:p1,u2:p2"
    auth_pairs = []
    multi_auth = os.environ.get("APP_AUTH")
    if multi_auth:
        for token in multi_auth.split(","):
            token = token.strip()
            if not token or ":" not in token:
                continue
            u, p = token.split(":", 1)
            u, p = u.strip(), p.strip()
            if u and p:
                auth_pairs.append((u, p))
    else:
        user = os.environ.get("APP_USERNAME")
        pwd = os.environ.get("APP_PASSWORD")
        if user and pwd:
            auth_pairs.append((user, pwd))

    if auth_pairs:
        launch_kwargs["auth"] = auth_pairs[0] if len(auth_pairs) == 1 else auth_pairs
        launch_kwargs["auth_message"] = os.environ.get(
            "APP_AUTH_MESSAGE", "Private demo – enter recruiter password"
        )

    if os.environ.get("HF_SPACE_ID") or os.environ.get("SPACE_ID"):
        launch_kwargs.update(server_name="0.0.0.0", server_port=port, share=False)
    else:
        launch_kwargs.update(server_name="127.0.0.1", server_port=port, share=True, favicon_path="data/icon.png")

    demo.launch(**launch_kwargs)
