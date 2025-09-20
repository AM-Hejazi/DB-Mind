import os
from datetime import datetime

class PipelineLogger:
    def __init__(self, log_dir="ev_logs"):
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_file = os.path.join(log_dir, f"run_{timestamp}.txt")
        self.lines = []

    def log(self, title, content):
        entry = f"\n=== {title} ===\n{content.strip()}\n"
        self.lines.append(entry)
        print(entry)  # also print live to console

    def save(self):
        if not self.log_file:
            print("⚠️ Logger warning: log_file is None, skipping save.")
            return
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.writelines(self.lines)
        print(f"\n📄 Log saved to: {self.log_file}")


# Create only one logger instance
global_logger = PipelineLogger()
