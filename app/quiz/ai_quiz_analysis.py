import pandas as pd


def get_student_quiz_attempts(db, student_email):
    attempts = (
        db.collection("quiz_attempts")
        .where("email", "==", student_email.strip().lower())
        .stream()
    )

    rows = []
    review_rows = []

    for a in attempts:
        d = a.to_dict()

        rows.append({
            "quiz": d.get("quiz_title"),
            "module": d.get("module"),
            "score": d.get("score"),
            "total": d.get("total_marks"),
            "percentage": d.get("percentage"),
            "correct": d.get("correct"),
            "wrong": d.get("wrong"),
            "attempt_no": d.get("attempt_no"),
        })

        for r in d.get("review", []):
            review_rows.append({
                "quiz": d.get("quiz_title"),
                "module": d.get("module"),
                "question": r.get("Question"),
                "your_answer": r.get("Your Answer"),
                "correct_answer": r.get("Correct Answer"),
                "marks_awarded": r.get("Marks Awarded", 0),
                "total_marks": r.get("Total Marks", 1),
                "topic": r.get("Topic", "Unknown"),
                "difficulty": r.get("Difficulty", "Unknown"),
            })

    return rows, review_rows


def build_student_quiz_context(db, student_email):
    attempts, reviews = get_student_quiz_attempts(db, student_email)

    if not attempts:
        return "No quiz attempts found yet."

    attempts_df = pd.DataFrame(attempts)
    reviews_df = pd.DataFrame(reviews)

    avg_score = round(attempts_df["percentage"].mean(), 2)
    best_score = round(attempts_df["percentage"].max(), 2)
    latest = attempts[-1]

    weak_topics_text = "No weak topic detected."

    if not reviews_df.empty:
        wrong_df = reviews_df[reviews_df["marks_awarded"] == 0]

        if not wrong_df.empty:
            topic_summary = (
                wrong_df["topic"]
                .value_counts()
                .head(5)
                .reset_index()
            )
            topic_summary.columns = ["Topic", "Wrong Count"]

            weak_topics_text = "\n".join(
                [f"- {r['Topic']}: {r['Wrong Count']} wrong" for _, r in topic_summary.iterrows()]
            )

    context = f"""
Quiz Performance Summary:
Total Attempts: {len(attempts)}
Average Quiz Percentage: {avg_score}%
Best Quiz Percentage: {best_score}%

Latest Quiz:
Quiz: {latest.get("quiz")}
Module: {latest.get("module")}
Score: {latest.get("score")}/{latest.get("total")}
Percentage: {latest.get("percentage")}%
Correct: {latest.get("correct")}
Wrong: {latest.get("wrong")}

Weak Topics From Quiz Attempts:
{weak_topics_text}
"""

    return context


def get_admin_quiz_summary(db):
    attempts = db.collection("quiz_attempts").stream()

    rows = []
    review_rows = []

    for a in attempts:
        d = a.to_dict()

        rows.append({
            "name": d.get("name"),
            "email": d.get("email"),
            "quiz": d.get("quiz_title"),
            "module": d.get("module"),
            "score": d.get("score"),
            "total": d.get("total_marks"),
            "percentage": d.get("percentage"),
            "correct": d.get("correct"),
            "wrong": d.get("wrong"),
        })

        for r in d.get("review", []):
            review_rows.append({
                "name": d.get("name"),
                "email": d.get("email"),
                "quiz": d.get("quiz_title"),
                "module": d.get("module"),
                "topic": r.get("Topic", "Unknown"),
                "difficulty": r.get("Difficulty", "Unknown"),
                "marks_awarded": r.get("Marks Awarded", 0),
                "total_marks": r.get("Total Marks", 1),
            })

    if not rows:
        return {
            "summary_text": "No quiz attempts found yet.",
            "attempts_df": pd.DataFrame(),
            "weak_topics_df": pd.DataFrame(),
            "weak_students_df": pd.DataFrame(),
        }

    attempts_df = pd.DataFrame(rows)

    avg_score = round(attempts_df["percentage"].mean(), 2)
    total_attempts = len(attempts_df)
    total_students = attempts_df["email"].nunique()

    weak_students_df = (
        attempts_df[attempts_df["percentage"] < 60]
        .sort_values("percentage")
        .head(20)
    )

    weak_topics_df = pd.DataFrame()

    if review_rows:
        review_df = pd.DataFrame(review_rows)
        wrong_df = review_df[review_df["marks_awarded"] == 0]

        if not wrong_df.empty:
            weak_topics_df = (
                wrong_df.groupby("topic")
                .size()
                .reset_index(name="Wrong Count")
                .sort_values("Wrong Count", ascending=False)
                .head(10)
            )

    weak_topics_text = "No weak topics detected."

    if not weak_topics_df.empty:
        weak_topics_text = "\n".join(
            [f"- {r['topic']}: {r['Wrong Count']} wrong answers" for _, r in weak_topics_df.iterrows()]
        )

    summary_text = f"""
Overall Quiz Summary:
Total Quiz Attempts: {total_attempts}
Unique Students Attempted: {total_students}
Average Quiz Percentage: {avg_score}%

Top Weak Topics:
{weak_topics_text}

Low Performing Students:
{len(weak_students_df)} students scored below 60%.
"""

    return {
        "summary_text": summary_text,
        "attempts_df": attempts_df,
        "weak_topics_df": weak_topics_df,
        "weak_students_df": weak_students_df,
    }