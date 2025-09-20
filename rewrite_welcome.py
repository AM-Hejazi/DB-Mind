from pathlib import Path

HTML = """
<div style='padding: 16px; border: 1px solid #2f2f2f; border-radius: 14px; background-color: #1b1b1b; color: #f5f5f5; font-size: 14px; box-shadow: 0 0 12px rgba(0,0,0,0.35); max-width: 860px; margin: 0 auto;'>
  <div style='display:flex; align-items:center; gap:10px; margin-bottom:8px; flex-wrap:wrap;'>
    <span style='font-size:20px;'>🔧</span>
    <h3 style='margin:0; font-size:18px;'>Maintenance Demo Assistant</h3>
  </div>
  <p style='margin:0 0 6px 0;'>ℹ️ This demo connects to the <code>maintenance_demo</code> SQLite database bundled with DB-Mind.</p>
  <p style='margin:0 0 16px 0;'><strong>⚠️ Hinweis:</strong> Demo build – Antworten dienen nur zur Illustration; responses are illustrative only.</p>
  <div style='display:flex; flex-wrap:wrap; gap:24px; justify-content:space-between;'>
    <div style='flex:1; min-width:260px; max-width:400px;'>
      <h4 style='margin:0 0 8px 0; font-size:15px;'>🇩🇪 Demo-Version</h4>
      <ul style='margin:0; padding-left:0; list-style:none; line-height:1.6; display:flex; flex-direction:column; gap:6px;'>
        <li>🔍 Welche Wartungsaufträge sind diesen Monat überfällig?</li>
        <li>🗓️ Zeige geplante Arbeiten für Pumpe A.</li>
        <li>👷‍♂️ Welche Techniker schlossen letzte Woche Inspektionen ab?</li>
      </ul>
    </div>
    <div style='flex:1; min-width:260px; max-width:400px;'>
      <h4 style='margin:0 0 8px 0; font-size:15px;'>🇬🇧 Try Asking</h4>
      <ul style='margin:0; padding-left:0; list-style:none; line-height:1.6; display:flex; flex-direction:column; gap:6px;'>
        <li>🔍 What maintenance tasks are overdue this month?</li>
        <li>🗓️ List upcoming work orders for Pump A.</li>
        <li>👷‍♂️ Which technicians completed inspections last week?</li>
      </ul>
    </div>
  </div>
</div>
""".strip()

TARGETS = {
    Path("src/ui/layout.py"): "        chatbot = gr.Chatbot(",
    Path("src/ui/handlers.py"): "logger.log(\"CONFIG Snapshot\"",
    Path("src/ui/handlers_FD.py"): "logger.log(\"CONFIG Snapshot\"",
    Path("src/ui/handlers_FD_bk.py"): "logger.log(\"CONFIG Snapshot\"",
    Path("main_UI_bk.py"): "        chatbot = gr.Chatbot(",
}

for path, sentinel in TARGETS.items():
    text = path.read_text(encoding='utf-8')

    if 'import textwrap' not in text:
        lines = text.splitlines()
        insert_idx = 0
        for idx, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                insert_idx = idx + 1
        lines.insert(insert_idx, 'import textwrap')
        text = '\n'.join(lines)

    start = text.index('welcome_message')
    end = text.index(sentinel, start)

    indent_line = text[:start].splitlines()[-1]
    indent = indent_line[:len(indent_line) - len(indent_line.lstrip())]

    block = f"{indent}welcome_message = textwrap.dedent(\"\"\"\n{HTML}\n\"\"\").strip()\n\n"

    new_text = text[:start] + block + text[end:]
    path.write_text(new_text, encoding='utf-8')
