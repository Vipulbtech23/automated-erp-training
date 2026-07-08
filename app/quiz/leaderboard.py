import streamlit as st
import pandas as pd


def quiz_leaderboard_panel(db, quiz_id=None):
    st.subheader("🏆 Quiz Leaderboard")

    if quiz_id:
        attempts = (
            db.collection("quiz_attempts")
            .where("quiz_id", "==", quiz_id)
            .stream()
        )
    else:
        attempts = db.collection("quiz_attempts").stream()

    rows = []

    for a in attempts:
        d = a.to_dict()
        rows.append({
            "Name": d.get("name"),
            "Email": d.get("email"),
            "Quiz": d.get("quiz_title"),
            "Score": d.get("score"),
            "Total": d.get("total_marks"),
            "Percentage": d.get("percentage"),
            "Correct": d.get("correct"),
            "Wrong": d.get("wrong"),
            "Attempt No": d.get("attempt_no"),
            "Submitted At": str(d.get("submitted_at"))
        })

    if not rows:
        st.info("No attempts found.")
        return

    df = pd.DataFrame(rows)

    best_df = (
        df.sort_values(["Email", "Percentage"], ascending=[True, False])
        .drop_duplicates("Email")
        .sort_values("Percentage", ascending=False)
        .reset_index(drop=True)
    )

    best_df["Quiz Rank"] = best_df.index + 1

    st.dataframe(
        best_df[
            [
                "Quiz Rank",
                "Name",
                "Email",
                "Quiz",
                "Score",
                "Total",
                "Percentage",
                "Correct",
                "Wrong"
            ]
        ],
        use_container_width=True
    )

    st.download_button(
        "⬇ Download Leaderboard CSV",
        best_df.to_csv(index=False).encode("utf-8"),
        "quiz_leaderboard.csv",
        "text/csv"
    )