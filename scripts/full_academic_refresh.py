import os
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SCRIPTS = [
    "scripts/update_rankings_from_quiz.py",
    "scripts/generate_scorecard.py",
    "scripts/certificate_generator.py",
]


def run_script(script_path):
    full_path = BASE_DIR / script_path

    if not full_path.exists():
        return False, f"Missing script: {script_path}"

    result = subprocess.run(
        [sys.executable, str(full_path)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True
    )

    output = result.stdout + "\n" + result.stderr

    return result.returncode == 0, output


def full_academic_refresh():
    results = []

    for script in SCRIPTS:
        success, output = run_script(script)
        results.append({
            "script": script,
            "success": success,
            "output": output
        })

        if not success:
            break

    return results


if __name__ == "__main__":
    results = full_academic_refresh()

    for r in results:
        print("=" * 60)
        print(r["script"])
        print("SUCCESS" if r["success"] else "FAILED")
        print(r["output"])