import streamlit as st
import pandas as pd
import datetime
import uuid
import zoneinfo
import plotly.express as px
from firebase_admin import firestore

from quiz.notifications import create_bulk_notification

IST = zoneinfo.ZoneInfo("Asia/Kolkata")

REQUIRED_COLS = [
    "Question",
    "Option1",
    "Option2",
    "Option3",
    "Option4",
    "Correct Option",
    "Marks",
    "Difficulty",
    "Topic",
]


def quiz_leaderboard_panel(db, quiz_id):
    st.subheader("🏆 Quiz Leaderboard")

    attempts = (
        db.collection("quiz_attempts")
        .where("quiz_id", "==", quiz_id)
        .stream()
    )

    rows = []

    for a in attempts:
        d = a.to_dict()
        rows.append({
            "Name": d.get("name"),
            "Email": d.get("email"),
            "Score": d.get("score"),
            "Total": d.get("total_marks"),
            "Percentage": d.get("percentage"),
            "Correct": d.get("correct"),
            "Wrong": d.get("wrong"),
            "Attempt No": d.get("attempt_no"),
            "Submitted At": str(d.get("submitted_at")),
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

    st.dataframe(best_df, use_container_width=True)

    st.download_button(
        "⬇ Download Leaderboard CSV",
        best_df.to_csv(index=False).encode("utf-8"),
        "quiz_leaderboard.csv",
        "text/csv",
    )


def quiz_analytics_panel(db, quiz_id):
    st.subheader("📊 Quiz Analytics")

    attempts = (
        db.collection("quiz_attempts")
        .where("quiz_id", "==", quiz_id)
        .stream()
    )

    rows = []
    review_rows = []

    for a in attempts:
        d = a.to_dict()

        rows.append({
            "Name": d.get("name"),
            "Email": d.get("email"),
            "Score": d.get("score"),
            "Total": d.get("total_marks"),
            "Percentage": d.get("percentage"),
            "Correct": d.get("correct"),
            "Wrong": d.get("wrong"),
            "Attempt No": d.get("attempt_no"),
            "Submitted At": str(d.get("submitted_at")),
        })

        for r in d.get("review", []):
            review_rows.append({
                "Name": d.get("name"),
                "Email": d.get("email"),
                "Question": r.get("Question"),
                "Your Answer": r.get("Your Answer"),
                "Correct Answer": r.get("Correct Answer"),
                "Marks Awarded": r.get("Marks Awarded", r.get("Marks", 0)),
                "Total Marks": r.get("Total Marks", 1),
                "Topic": r.get("Topic", "Unknown"),
                "Difficulty": r.get("Difficulty", "Unknown"),
            })

    if not rows:
        st.info("No quiz attempts yet.")
        return

    df = pd.DataFrame(rows)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Attempts", len(df))
    c2.metric("Average %", round(df["Percentage"].mean(), 2))
    c3.metric("Highest %", round(df["Percentage"].max(), 2))
    c4.metric("Lowest %", round(df["Percentage"].min(), 2))

    fig = px.histogram(df, x="Percentage", nbins=10, title="Score Distribution")
    st.plotly_chart(fig, use_container_width=True)

    fig2 = px.bar(
        df.sort_values("Percentage", ascending=False),
        x="Name",
        y="Percentage",
        title="Student Wise Performance",
    )
    st.plotly_chart(fig2, use_container_width=True)

    if review_rows:
        review_df = pd.DataFrame(review_rows)

        topic_df = (
            review_df.groupby("Topic")["Marks Awarded"]
            .mean()
            .reset_index()
            .sort_values("Marks Awarded")
        )

        st.subheader("📚 Topic Wise Average Marks")
        st.dataframe(topic_df, use_container_width=True)

        fig3 = px.bar(
            topic_df,
            x="Topic",
            y="Marks Awarded",
            title="Topic Wise Performance"
        )
        st.plotly_chart(fig3, use_container_width=True)

        difficulty_df = (
            review_df.groupby("Difficulty")["Marks Awarded"]
            .mean()
            .reset_index()
        )

        st.subheader("🎯 Difficulty Wise Performance")
        st.dataframe(difficulty_df, use_container_width=True)

        fig4 = px.pie(
            difficulty_df,
            names="Difficulty",
            values="Marks Awarded",
            title="Difficulty Wise Avg Marks",
        )
        st.plotly_chart(fig4, use_container_width=True)

        st.subheader("⚠️ Weak Topics Detected")
        weak_topics = topic_df.head(5)
        st.warning("These topics need revision or mentoring.")
        st.dataframe(weak_topics, use_container_width=True)

        st.download_button(
            "⬇ Download Weak Topics CSV",
            weak_topics.to_csv(index=False).encode("utf-8"),
            "weak_topics.csv",
            "text/csv",
        )

    st.download_button(
        "⬇ Download Full Attempts CSV",
        df.to_csv(index=False).encode("utf-8"),
        "quiz_attempts_full.csv",
        "text/csv",
    )


def quiz_admin_panel(db):
    st.title("📚 Quiz Management V4")

    tab1, tab2 = st.tabs(["➕ Create Quiz", "📊 Published Quizzes"])

    with tab1:
        title = st.text_input("Quiz Title", "ML Placement Quiz")
        module = st.text_input("Module", "Machine Learning")
        description = st.text_area("Description", "Placement practice quiz")

        c1, c2 = st.columns(2)

        with c1:
            start_date = st.date_input("Start Date", datetime.date.today())
            start_time = st.time_input("Start Time", datetime.datetime.now(IST).time())

        with c2:
            end_date = st.date_input("End Date", datetime.date.today())
            end_time = st.time_input("End Time", datetime.datetime.now(IST).time())

        duration = st.number_input("Duration Minutes", 1, 180, 15)
        attempts_allowed = st.number_input("Attempts Allowed", 1, 10, 1)
        randomize = st.checkbox("Shuffle Questions", value=True)

        uploaded_file = st.file_uploader("Upload Quiz CSV", type=["csv"])

        st.caption(
            "CSV columns: Question, Option1, Option2, Option3, Option4, Correct Option, Marks, Difficulty, Topic"
        )

        if uploaded_file:
            quiz_df = pd.read_csv(uploaded_file)
            quiz_df.columns = quiz_df.columns.str.strip()

            st.dataframe(quiz_df, use_container_width=True)

            missing = [c for c in REQUIRED_COLS if c not in quiz_df.columns]

            if missing:
                st.error(f"Missing columns: {missing}")
                return

            if st.button("🚀 Publish Quiz"):
                quiz_id = str(uuid.uuid4())

                start_dt = datetime.datetime.combine(start_date, start_time).replace(tzinfo=IST)
                end_dt = datetime.datetime.combine(end_date, end_time).replace(tzinfo=IST)

                if end_dt <= start_dt:
                    st.error("End time must be after start time.")
                    return

                quiz_df["Correct Option"] = quiz_df["Correct Option"].astype(int)
                quiz_df["Marks"] = quiz_df["Marks"].astype(int)

                questions = quiz_df.to_dict(orient="records")
                total_marks = int(quiz_df["Marks"].sum())

                db.collection("quizzes").document(quiz_id).set({
                    "quiz_id": quiz_id,
                    "title": title,
                    "module": module,
                    "description": description,
                    "start_time": start_dt,
                    "end_time": end_dt,
                    "duration_minutes": int(duration),
                    "attempts_allowed": int(attempts_allowed),
                    "randomize": bool(randomize),
                    "total_marks": total_marks,
                    "total_questions": len(questions),
                    "questions": questions,
                    "is_active": True,
                    "created_at": firestore.SERVER_TIMESTAMP,
                })

                try:
                    df_students = pd.read_excel("output/final_rankings.xlsx")
                    df_students.columns = df_students.columns.str.strip()

                    emails = (
                        df_students["Email"]
                        .astype(str)
                        .str.strip()
                        .str.lower()
                        .tolist()
                    )

                    count = create_bulk_notification(
                        db,
                        emails,
                        "New Quiz Published",
                        f"{title} is now live in your Quiz Center.",
                        "quiz"
                    )

                    st.success(f"✅ Quiz published successfully. Notification sent to {count} students.")

                except Exception as e:
                    st.warning(f"Quiz published, but notification failed: {e}")

                st.rerun()

    with tab2:
        quizzes = list(db.collection("quizzes").stream())

        if not quizzes:
            st.warning("No quizzes published yet.")
            return

        rows = []

        for q in quizzes:
            d = q.to_dict()
            rows.append({
                "Quiz ID": d.get("quiz_id"),
                "Title": d.get("title"),
                "Module": d.get("module"),
                "Questions": d.get("total_questions"),
                "Total Marks": d.get("total_marks"),
                "Attempts": d.get("attempts_allowed"),
                "Active": d.get("is_active"),
                "Start": str(d.get("start_time")),
                "End": str(d.get("end_time")),
            })

        quiz_table = pd.DataFrame(rows)
        st.dataframe(quiz_table, use_container_width=True)

        selected_quiz = st.selectbox("Select Quiz", quiz_table["Quiz ID"].tolist())

        c1, c2, c3 = st.columns(3)

        with c1:
            if st.button("🔒 Close Quiz"):
                db.collection("quizzes").document(selected_quiz).update({
                    "is_active": False
                })
                st.success("Quiz closed")
                st.rerun()

        with c2:
            if st.button("🔓 Reopen Quiz"):
                db.collection("quizzes").document(selected_quiz).update({
                    "is_active": True
                })
                st.success("Quiz reopened")
                st.rerun()

        with c3:
            if st.button("🗑 Delete Quiz"):
                db.collection("quizzes").document(selected_quiz).delete()
                st.success("Quiz deleted")
                st.rerun()

        st.markdown("---")

        subtab1, subtab2 = st.tabs(["🏆 Leaderboard", "📊 Analytics"])

        with subtab1:
            quiz_leaderboard_panel(db, selected_quiz)

        with subtab2:
            quiz_analytics_panel(db, selected_quiz)