import time
import os
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

DATA_DIR = "data"

SCRIPTS = [
    "scripts/merge_quizzes.py",
    "scripts/calculate_scores.py",
    "scripts/generate_gradecards.py",
    "scripts/certificate_generator.py"
]

def run_pipeline():
    print("\nNew CSV detected. Running automation pipeline...\n")

    for script in SCRIPTS:
        print(f"Running {script}")

        result = subprocess.run(
            ["python", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        if result.returncode != 0:
            print(f"FAILED: {script}")
            print(result.stderr)
            return

        print(f"SUCCESS: {script}")

    print("\nAll automation tasks completed.\n")


class QuizHandler(FileSystemEventHandler):

    def on_created(self, event):
        if event.is_directory:
            return

        if event.src_path.lower().endswith(".csv"):
            print("Detected:", event.src_path)

            # wait for file copy to complete
            time.sleep(3)

            run_pipeline()


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)

    observer = Observer()
    observer.schedule(QuizHandler(), DATA_DIR, recursive=False)
    observer.start()

    print(f"Watching folder: {DATA_DIR}")
    print("Save quiz CSV here and pipeline will run automatically.")
    print("Press CTRL + C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()