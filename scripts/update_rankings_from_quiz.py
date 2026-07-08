import pandas as pd
import os
import firebase_admin
from firebase_admin import credentials, firestore
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "output" / "final_rankings.xlsx"

if not firebase_admin._apps:
    cred = credentials.Certificate(BASE_DIR / "firebase_key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()


def grade_from_percentage(p):
    if p >= 90:
        return "A+"
    elif p >= 80:
        return "A"
    elif p >= 70:
        return "B"
    elif p >= 60:
        return "C"
    elif p >= 40:
        return "D"
    else:
        return "F"


def update_rankings_from_quiz():
    if not os.path.exists(DATA_FILE):
        print("final_rankings.xlsx not found")
        return False

    df = pd.read_excel(DATA_FILE)
    df.columns = df.columns.str.strip()

    df["Email"] = df["Email"].astype(str).str.strip().str.lower()
    df["Name"] = df["Name"].astype(str).str.strip()

    attempts = db.collection("quiz_attempts").stream()

    rows = []

    for a in attempts:
        d = a.to_dict()

        email = str(d.get("email", "")).strip().lower()

        if not email or email == "nan":
            continue

        rows.append({
            "Email": email,
            "Quiz": str(d.get("quiz_title", "Quiz")),
            "Score": float(d.get("score", 0)),
            "Total": float(d.get("total_marks", 1)),
            "Percentage": float(d.get("percentage", 0)),
        })

    if not rows:
        print("No quiz attempts found")
        return False

    attempts_df = pd.DataFrame(rows)

    best_attempts = (
        attempts_df
        .sort_values(["Email", "Quiz", "Percentage"], ascending=[True, True, False])
        .drop_duplicates(["Email", "Quiz"])
    )

    quiz_score_df = (
        best_attempts
        .groupby("Email")["Percentage"]
        .mean()
        .round(2)
    )

    df["Live_Quiz_Percentage"] = (
        df["Email"]
        .map(quiz_score_df)
        .fillna(0)
        .round(2)
    )

    if "Percentage" not in df.columns:
        print("Percentage column not found in final_rankings.xlsx")
        return False

    df["Base_Percentage"] = pd.to_numeric(df["Percentage"], errors="coerce").fillna(0)

    df["Updated_Percentage"] = (
        df["Base_Percentage"] * 0.70 +
        df["Live_Quiz_Percentage"] * 0.30
    ).round(2)

    df["Percentage"] = df["Updated_Percentage"]
    df["CGPA"] = (df["Percentage"] / 10).round(2)
    df["Grade"] = df["Percentage"].apply(grade_from_percentage)

    df["Rank"] = (
        df["Percentage"]
        .rank(method="dense", ascending=False)
        .astype(int)
    )

    df = df.sort_values("Rank")

    df.to_excel(DATA_FILE, index=False)

    print("final_rankings.xlsx updated successfully from quiz attempts")
    print("Students updated:", len(df))
    print("Quiz attempts used:", len(attempts_df))
    return True


if __name__ == "__main__":
    update_rankings_from_quiz()