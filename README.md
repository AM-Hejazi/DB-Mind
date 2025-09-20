---
title: DB-Mind Assistant
emoji: 🚀
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: "4.44.1"
app_file: app.py
pinned: false
---

# DB-Mind

V1.2 demo: A multi agent AI chatbot for SQL querying.

## Hugging Face Space Deployment

This repo now includes an `app.py` entrypoint that wraps the Gradio interface and enforces a 2-question-per-user limit. To publish the UI on a Hugging Face Space:

1. Install the CLI once: `pip install -U huggingface_hub`
2. Log in: `huggingface-cli login`
3. Create the new Space (replace placeholders):
   ```bash
   huggingface-cli repo create <username>/<space-name> --type space --sdk gradio --private
   ```
4. Add the remote and push the required files (`app.py`, `main_UI.py`, `requirements.txt`, `src`, `data/icon.png`, and any config you rely on):
   ```bash
   git remote add hf https://huggingface.co/spaces/<username>/<space-name>
   git push hf HEAD:main
   ```
5. In the Space settings, set the SDK to **Gradio**, `app.py` as the entry file, and Python 3.10+ as the runtime. The UI will launch automatically; share the Space URL once it is live.

> Tip: If you need database credentials, store them as Space Secrets (Settings -> Variables) and read them inside the app before connecting.

Once deployed, visitors will see the same UI as `main_UI.py`, but each browser session can start at most two new questions. After the limit is reached, the input field is disabled and the assistant explains the restriction.
