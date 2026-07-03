import os
import subprocess
import pandas as pd
from datetime import datetime

SCRIPTS = [
    "scripts/merge_quizzes.py",
    "scripts/calculate_scores.py",
    "scripts/generate_scorecard.py",
    "scripts/certificate_generator.py"
]

LOG_FILE = "output/agent_log.txt"

def write_log(msg):
    os.makedirs("output", exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] {msg}\n")

def run_script(script):
    write_log(f"Running {script}")
    result = subprocess.run(
        ["python", script],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        write_log(f"ERROR in {script}: {result.stderr}")
        return False, result.stderr

    write_log(f"SUCCESS: {script}")
    return True, result.stdout

def run_agent():
    results = []

    for script in SCRIPTS:
        if not os.path.exists(script):
            results.append((script, False, "Script not found"))
            continue

        success, output = run_script(script)
        results.append((script, success, output))

        if not success:
            break

    return results

def prediction_model():
    file = "output/final_rankings.xlsx"

    if not os.path.exists(file):
        return None

    df = pd.read_excel(file)
    df.columns = df.columns.str.strip()

    predictions = []

    for _, row in df.iterrows():

        current_percentage = float(row.get("Percentage", 0))
        attendance = float(row.get("Attendance_%", 0))
        cgpa = float(row.get("CGPA", 0))

        predicted_percentage = (
            current_percentage * 0.65 +
            attendance * 0.15 +
            (cgpa * 10) * 0.20
        )

        if predicted_percentage >= 90:
            predicted_grade = "A+"
        elif predicted_percentage >= 80:
            predicted_grade = "A"
        elif predicted_percentage >= 70:
            predicted_grade = "B"
        elif predicted_percentage >= 60:
            predicted_grade = "C"
        else:
            predicted_grade = "Needs Improvement"

        risk = "Low Risk"
        if attendance < 75 or predicted_percentage < 60:
            risk = "High Risk"
        elif predicted_percentage < 70:
            risk = "Medium Risk"

        predictions.append({
            "Name": row["Name"],
            "Email": row["Email"],
            "Current %": current_percentage,
            "Current Rank": row.get("Rank", ""),
            "Predicted %": round(predicted_percentage, 2),
            "Predicted Grade": predicted_grade,
            "Risk Level": risk
        })

    pred_df = pd.DataFrame(predictions)
    pred_df["Predicted Rank"] = pred_df["Predicted %"].rank(
        ascending=False,
        method="dense"
    ).astype(int)

    pred_df = pred_df.sort_values("Predicted Rank")

    output = "output/predictions.xlsx"
    pred_df.to_excel(output, index=False)

    return pred_df