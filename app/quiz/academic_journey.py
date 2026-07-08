import streamlit as st
import pandas as pd
import plotly.express as px


def academic_journey_panel(db, student):
    st.title("📈 Academic Journey")

    student_email = str(student["Email"]).strip().lower()

    st.subheader("🎓 Current Academic Snapshot")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Rank", student["Rank"])
    c2.metric("Percentage", f"{student['Percentage']}%")
    c3.metric("CGPA", student["CGPA"])
    c4.metric("Attendance", f"{student['Attendance_%']}%")

    attempts = (
        db.collection("quiz_attempts")
        .where("email", "==", student_email)
        .stream()
    )

    rows = []
    review_rows = []

    for a in attempts:
        d = a.to_dict()

        rows.append({
            "Quiz": d.get("quiz_title"),
            "Module": d.get("module"),
            "Score": d.get("score"),
            "Total": d.get("total_marks"),
            "Percentage": d.get("percentage"),
            "Attempt No": d.get("attempt_no"),
            "Correct": d.get("correct"),
            "Wrong": d.get("wrong"),
            "Submitted At": str(d.get("submitted_at"))
        })

        for r in d.get("review", []):
            review_rows.append({
                "Quiz": d.get("quiz_title"),
                "Module": d.get("module"),
                "Question": r.get("Question"),
                "Your Answer": r.get("Your Answer"),
                "Correct Answer": r.get("Correct Answer"),
                "Marks Awarded": r.get("Marks Awarded", 0),
                "Topic": r.get("Topic", "Unknown"),
                "Difficulty": r.get("Difficulty", "Unknown")
            })

    if not rows:
        st.info("No quiz attempts found yet. Start attempting quizzes to build your academic journey.")
        return

    journey_df = pd.DataFrame(rows)

    st.subheader("📊 Quiz Progress Timeline")

    fig = px.line(
        journey_df,
        x=journey_df.index + 1,
        y="Percentage",
        markers=True,
        title="Quiz Percentage Improvement"
    )

    fig.update_layout(
        xaxis_title="Attempt Number",
        yaxis_title="Percentage"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📚 Quiz Attempt History")
    st.dataframe(journey_df, use_container_width=True)

    avg_percentage = round(journey_df["Percentage"].mean(), 2)
    best_percentage = round(journey_df["Percentage"].max(), 2)
    latest_percentage = round(journey_df.iloc[-1]["Percentage"], 2)

    c1, c2, c3 = st.columns(3)
    c1.metric("Average Quiz %", f"{avg_percentage}%")
    c2.metric("Best Quiz %", f"{best_percentage}%")
    c3.metric("Latest Quiz %", f"{latest_percentage}%")

    st.subheader("🏆 Best Quiz Performance")

    best_row = journey_df.sort_values("Percentage", ascending=False).iloc[0]

    st.success(
        f"Best performance in **{best_row['Quiz']}** with **{best_row['Percentage']}%**"
    )

    if review_rows:
        review_df = pd.DataFrame(review_rows)

        wrong_df = review_df[review_df["Marks Awarded"] == 0]

        st.subheader("⚠️ Weak Topic Analysis")

        if not wrong_df.empty:
            weak_topics = (
                wrong_df["Topic"]
                .value_counts()
                .reset_index()
            )

            weak_topics.columns = ["Topic", "Wrong Count"]

            st.dataframe(weak_topics, use_container_width=True)

            fig2 = px.bar(
                weak_topics,
                x="Topic",
                y="Wrong Count",
                title="Weak Topics Based on Wrong Answers"
            )

            st.plotly_chart(fig2, use_container_width=True)

            top_weak = weak_topics.iloc[0]["Topic"]

            st.warning(
                f"Your most repeated weak topic is **{top_weak}**. Revise this first."
            )

            st.subheader("🧠 Recommended Action Plan")

            st.write(f"""
            1. Revise **{top_weak}** today.
            2. Re-attempt related quizzes.
            3. Practice 10 MCQs from this topic.
            4. Ask Jarvis: *Explain {top_weak} with examples.*
            5. Track your next quiz percentage improvement.
            """)
        else:
            st.success("No weak topics detected. Great performance!")