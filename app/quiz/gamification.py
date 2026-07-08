import streamlit as st
import pandas as pd
import datetime


def calculate_student_xp(attempts):
    xp = 0

    for a in attempts:
        percentage = float(a.get("percentage", 0))
        correct = int(a.get("correct", 0))

        xp += correct * 10

        if percentage >= 90:
            xp += 100
        elif percentage >= 75:
            xp += 60
        elif percentage >= 60:
            xp += 30

    return xp


def assign_badges(student, attempts):
    badges = []

    percentage = float(student["Percentage"])
    attendance = float(student["Attendance_%"])
    rank = int(student["Rank"])

    if rank == 1:
        badges.append("🥇 College Topper")

    if rank <= 3:
        badges.append("🏆 Top 3 Performer")

    if rank <= 10:
        badges.append("⭐ Top 10 Achiever")

    if percentage >= 90:
        badges.append("🔥 Academic Excellence")

    if attendance >= 90:
        badges.append("📌 Attendance Star")

    if len(attempts) >= 5:
        badges.append("📝 Quiz Warrior")

    if any(float(a.get("percentage", 0)) >= 90 for a in attempts):
        badges.append("🚀 High Scorer")

    if not badges:
        badges.append("🏅 Active Learner")

    return badges


def calculate_streak(attempts):
    if not attempts:
        return 0

    dates = []

    for a in attempts:
        submitted = a.get("submitted_at")

        if submitted:
            try:
                dates.append(submitted.date())
            except Exception:
                pass

    if not dates:
        return len(attempts)

    unique_dates = sorted(set(dates), reverse=True)

    streak = 1

    for i in range(1, len(unique_dates)):
        if (unique_dates[i - 1] - unique_dates[i]).days == 1:
            streak += 1
        else:
            break

    return streak


def gamification_panel(db, student):
    st.title("🏅 Gamification & Achievements")

    student_email = str(student["Email"]).strip().lower()

    attempts_docs = (
        db.collection("quiz_attempts")
        .where("email", "==", student_email)
        .stream()
    )

    attempts = [a.to_dict() for a in attempts_docs]

    xp = calculate_student_xp(attempts)
    badges = assign_badges(student, attempts)
    streak = calculate_streak(attempts)

    level = max(1, xp // 500 + 1)
    next_level_xp = level * 500
    progress = min(100, int((xp % 500) / 500 * 100))

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("⭐ XP Points", xp)
    c2.metric("🎮 Level", level)
    c3.metric("🔥 Streak", f"{streak} days")
    c4.metric("🏅 Badges", len(badges))

    st.subheader("🎯 Level Progress")
    st.progress(progress)
    st.caption(f"{xp} XP / {next_level_xp} XP for next level")

    st.subheader("🏅 My Badges")

    cols = st.columns(3)

    for i, badge in enumerate(badges):
        with cols[i % 3]:
            st.success(badge)

    st.subheader("📊 XP History")

    if attempts:
        rows = []

        for a in attempts:
            rows.append({
                "Quiz": a.get("quiz_title"),
                "Score": a.get("score"),
                "Percentage": a.get("percentage"),
                "Correct": a.get("correct"),
                "XP Earned": int(a.get("correct", 0)) * 10,
                "Submitted At": str(a.get("submitted_at"))
            })

        xp_df = pd.DataFrame(rows)
        st.dataframe(xp_df, use_container_width=True)
    else:
        st.info("Attempt quizzes to earn XP and badges.")


def admin_gamification_leaderboard(db):
    st.subheader("🏆 XP Leaderboard")

    attempts_docs = db.collection("quiz_attempts").stream()

    student_map = {}

    for a in attempts_docs:
        d = a.to_dict()

        email = d.get("email")
        name = d.get("name")

        if not email:
            continue

        if email not in student_map:
            student_map[email] = {
                "Name": name,
                "Email": email,
                "XP": 0,
                "Attempts": 0,
                "Best %": 0
            }

        percentage = float(d.get("percentage", 0))
        correct = int(d.get("correct", 0))

        student_map[email]["XP"] += correct * 10

        if percentage >= 90:
            student_map[email]["XP"] += 100
        elif percentage >= 75:
            student_map[email]["XP"] += 60
        elif percentage >= 60:
            student_map[email]["XP"] += 30

        student_map[email]["Attempts"] += 1
        student_map[email]["Best %"] = max(student_map[email]["Best %"], percentage)

    if not student_map:
        st.info("No quiz attempts found.")
        return

    lb_df = pd.DataFrame(student_map.values())
    lb_df = lb_df.sort_values("XP", ascending=False).reset_index(drop=True)
    lb_df["Rank"] = lb_df.index + 1

    st.dataframe(
        lb_df[["Rank", "Name", "Email", "XP", "Attempts", "Best %"]],
        use_container_width=True
    )