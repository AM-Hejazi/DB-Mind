from pathlib import Path
import re

FILES = [
    (
        Path('src/ui/layout.py'),
        "from src.ui.events import bind_event_handlers\n"
    ),
    (
        Path('src/ui/layout_bk.py'),
        "from src.ui.events import bind_event_handlers\n"
    ),
    (
        Path('src/ui/handlers.py'),
        "from config import CONFIG\n"
    ),
    (
        Path('src/ui/handlers_FD.py'),
        "from src.analyzer import analyze_failure\n"
    ),
    (
        Path('src/ui/handlers_FD_bk.py'),
        "from src.analyzer import analyze_failure\n"
    ),
    (
        Path('main_UI_bk.py'),
        "from src.logger import global_logger as logger\n"
    ),
]

HTML = """
<div style='padding: 16px; border: 1px solid #2f2f2f; border-radius: 14px; background-color: #1b1b1b; color: #f5f5f5; font-size: 14px; box-shadow: 0 0 12px rgba(0,0,0,0.35); max-width: 860px; margin: 0 auto;'>
  <div style='display:flex; align-items:center; gap:10px; margin-bottom:8px; flex-wrap:wrap;'>
    <span style='font-size:20px;'>&#128295;</span>
    <h3 style='margin:0; font-size:18px;'>Maintenance Demo Assistant</h3>
  </div>
  <p style='margin:0 0 6px 0;'>&#8505;&#65039; This demo connects to the <code>maintenance_demo</code> SQLite database bundled with DB-Mind.</p>
  <p style='margin:0 0 16px 0;'><strong>&#9888;&#65039; Hinweis:</strong> Demo build – Antworten dienen nur zur Illustration; responses are illustrative only.</p>
  <div style='display:flex; flex-wrap:wrap; gap:24px; justify-content:space-between;'>
    <div style='flex:1; min-width:260px; max-width:400px;'>
      <h4 style='margin:0 0 8px 0; font-size:15px;'>&#127465;&#127466; Demo-Version</h4>
      <ul style='margin:0; padding-left:18px; line-height:1.6;'>
        <li>&#128269; Welche Wartungsaufträge sind diesen Monat überfällig?</li>
        <li>&#128197; Zeige geplante Arbeiten für Pumpe A.</li>
        <li>&#129489;&#8205;&#128295; Welche Techniker schlossen letzte Woche Inspektionen ab?</li>
      </ul>
    </div>
    <div style='flex:1; min-width:260px; max-width:400px;'>
      <h4 style='margin:0 0 8px 0; font-size:15px;'>&#127468;&#127463; Try Asking</h4>
      <ul style='margin:0; padding-left:18px; line-height:1.6;'>
        <li>&#128269; What maintenance tasks are overdue this month?</li>
        <li>&#128197; List upcoming work orders for Pump A.</li>
        <li>&#129489;&#8205;&#128295; Which technicians completed inspections last week?</li>
      </ul>
    </div>
  </div>
</div>
""".strip()

BLOCK_TEMPLATE = "welcome_message = textwrap.dedent(\"\"\"\n{html}\n\"\"\").strip()\n\n"

WELCOME_PATTERN = re.compile(r"welcome_message\s*=\s*(?:textwrap\.dedent\()?\"\"\"(?:.|\r?\n)*?\"\"\"\.strip\(\)|welcome_message\s*=\s*\"(?:.|\r?\n)*?\")", re.MULTILINE)

for path, anchor in FILES:
    text = path.read_text(encoding='utf-8')

    if 'import textwrap' not in text:
        text = text.replace(anchor, anchor + 'import textwrap\n', 1)

    match = WELCOME_PATTERN.search(text)
    if not match:
        continue

    indent_line = text[:match.start()].splitlines()[-1]
    indent = indent_line[:len(indent_line) - len(indent_line.lstrip())]
    block = indent + BLOCK_TEMPLATE.format(html=HTML)

    text = text[:match.start()] + block + text[match.end():]
    path.write_text(text, encoding='utf-8')
