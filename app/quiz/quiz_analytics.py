import streamlit as st
import pandas as pd
import plotly.express as px


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
            "Submitted At": str(d.get("submitted_at"))
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
                "Difficulty": r.get("Difficulty", "Unknown")
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

    st.markdown("---")

    fig = px.histogram(
        df,
        x="Percentage",
        nbins=10,
        title="Score Distribution"
    )
    st.plotly_chart(fig, use_container_width=True)

    fig2 = px.bar(
        df.sort_values("Percentage", ascending=False),
        x="Name",
        y="Percentage",
        title="Student Wise Performance"
    )
    st.plotly_chart(fig2, use_container_width=True)

    if review_rows:
        review_df = pd.DataFrame(review_rows)

        topic_df = (
            review_df
            .groupby("Topic")["Marks Awarded"]
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
            review_df
            .groupby("Difficulty")["Marks Awarded"]
            .mean()
            .reset_index()
        )

        st.subheader("🎯 Difficulty Wise Performance")
        st.dataframe(difficulty_df, use_container_width=True)

        fig4 = px.pie(
            difficulty_df,
            names="Difficulty",
            values="Marks Awarded",
            title="Difficulty Wise Avg Marks"
        )
        st.plotly_chart(fig4, use_container_width=True)

        weak_topics = topic_df.head(5)

        st.subheader("⚠️ Weak Topics Detected")
        st.warning("These topics need revision or mentoring.")

        st.dataframe(weak_topics, use_container_width=True)

        st.download_button(
            "⬇ Download Weak Topics CSV",
            weak_topics.to_csv(index=False).encode("utf-8"),
            "weak_topics.csv",
            "text/csv"
        )

    st.download_button(
        "⬇ Download Full Attempts CSV",
        df.to_csv(index=False).encode("utf-8"),
        "quiz_attempts_full.csv",
        "text/csv"
    )