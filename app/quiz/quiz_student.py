import streamlit as st
import pandas as pd
import datetime
import random
import zoneinfo
from firebase_admin import firestore

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


def safe_id(value):
    return (
        str(value)
        .replace("@", "_at_")
        .replace(".", "_")
        .replace("/", "_")
        .replace(" ", "_")
    )


def convert_firestore_datetime(value):
    if value is None:
        return None

    if isinstance(value, datetime.datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.datetime.fromisoformat(value)
        except Exception:
            return None
    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)

    return dt.astimezone(IST)


def get_attempts(db, quiz_id, email):
    attempts = (
        db.collection("quiz_attempts")
        .where("quiz_id", "==", quiz_id)
        .where("email", "==", email)
        .stream()
    )
    return [a.to_dict() for a in attempts]


def get_draft_ref(db, quiz_id, email):
    draft_id = f"{quiz_id}_{safe_id(email)}"
    return db.collection("quiz_drafts").document(draft_id)


def load_draft(db, quiz_id, email):
    ref = get_draft_ref(db, quiz_id, email)
    snap = ref.get()
    if snap.exists:
        return snap.to_dict()
    return None


def save_answer(db, quiz_id, email, question_index, answer, quiz, student_name):
    ref = get_draft_ref(db, quiz_id, email)

    ref.set(
        {
            "quiz_id": quiz_id,
            "quiz_title": quiz.get("title", ""),
            "email": email,
            "name": student_name,
            "answers": {str(question_index): answer},
            "updated_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )


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
        st.info("No leaderboard available yet.")
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


def quiz_student_panel(db, student):
    st.title("📝 Quiz Center V3")

    student_email = str(student["Email"]).strip().lower()
    student_name = str(student["Name"]).strip()

    now = datetime.datetime.now(IST)
    st.caption(f"Current Time: {now.strftime('%Y-%m-%d %H:%M:%S')} IST")

    quiz_docs = list(db.collection("quizzes").stream())

    live_quizzes = []

    for qdoc in quiz_docs:
        d = qdoc.to_dict()

        start_dt = convert_firestore_datetime(d.get("start_time"))
        end_dt = convert_firestore_datetime(d.get("end_time"))

        if not start_dt or not end_dt:
            continue

        d["_doc_id"] = qdoc.id
        d["_start_dt"] = start_dt
        d["_end_dt"] = end_dt

        if d.get("is_active", True) and start_dt <= now <= end_dt:
            live_quizzes.append(d)

    tab1, tab2, tab3, tab4 = st.tabs(
        ["🔥 Live Quiz", "📚 History", "🏆 Leaderboard", "🛠 Debug"]
    )

    with tab1:
        if "active_quiz" not in st.session_state:
            if not live_quizzes:
                st.info("No live quiz available right now.")

            for quiz in live_quizzes:
                st.markdown("---")
                st.subheader(quiz.get("title", "Untitled Quiz"))

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Module", quiz.get("module", "N/A"))
                c2.metric("Questions", len(quiz.get("questions", [])))
                c3.metric("Marks", quiz.get("total_marks", 0))
                c4.metric("Attempts", quiz.get("attempts_allowed", 1))

                st.write("Start:", quiz["_start_dt"].strftime("%d-%m-%Y %I:%M %p"))
                st.write("End:", quiz["_end_dt"].strftime("%d-%m-%Y %I:%M %p"))

                attempts_done = len(get_attempts(db, quiz.get("quiz_id"), student_email))
                st.write("Attempts Done:", attempts_done)

                if attempts_done >= int(quiz.get("attempts_allowed", 1)):
                    st.warning("You have used all attempts.")
                    continue

                draft = load_draft(db, quiz.get("quiz_id"), student_email)
                btn_text = "🔄 Resume Quiz" if draft else "▶ Start Quiz"

                if st.button(
                    f"{btn_text} - {quiz.get('title')}",
                    key=f"start_{quiz.get('quiz_id')}",
                ):
                    questions = quiz.get("questions", [])

                    if not questions:
                        st.error("No questions found.")
                        continue

                    if draft and "questions" in draft:
                        active_questions = draft["questions"]
                        started_at = draft.get(
                            "started_at",
                            datetime.datetime.now(IST).isoformat(),
                        )
                        current_q = int(draft.get("current_q", 0))
                    else:
                        active_questions = questions.copy()

                        if quiz.get("randomize", True):
                            random.shuffle(active_questions)

                        started_at = datetime.datetime.now(IST).isoformat()
                        current_q = 0

                        get_draft_ref(db, quiz.get("quiz_id"), student_email).set(
                            {
                                "quiz_id": quiz.get("quiz_id"),
                                "quiz_title": quiz.get("title", ""),
                                "email": student_email,
                                "name": student_name,
                                "questions": active_questions,
                                "answers": {},
                                "started_at": started_at,
                                "current_q": 0,
                                "created_at": firestore.SERVER_TIMESTAMP,
                            },
                            merge=True,
                        )

                    st.session_state.active_quiz = quiz
                    st.session_state.active_questions = active_questions
                    st.session_state.quiz_started_at = started_at
                    st.session_state.current_q = current_q
                    st.rerun()

        else:
            quiz = st.session_state.active_quiz
            questions = st.session_state.active_questions
            quiz_id = quiz.get("quiz_id")

            draft = load_draft(db, quiz_id, student_email)
            saved_answers = draft.get("answers", {}) if draft else {}

            started_at = datetime.datetime.fromisoformat(st.session_state.quiz_started_at)

            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=IST)

            duration = int(quiz.get("duration_minutes", 15))
            deadline = started_at + datetime.timedelta(minutes=duration)
            remaining = deadline - datetime.datetime.now(IST)

            time_over = remaining.total_seconds() <= 0

            st.header(f"📝 {quiz.get('title')}")

            if time_over:
                st.error("⏰ Time is over. Submit your quiz now.")
            else:
                mins = int(remaining.total_seconds() // 60)
                secs = int(remaining.total_seconds() % 60)
                st.warning(f"⏳ Time Left: {mins:02d}:{secs:02d}")

            total_questions = len(questions)

            if "current_q" not in st.session_state:
                st.session_state.current_q = 0

            current_q = st.session_state.current_q

            st.markdown("### Question Palette")

            cols = st.columns(10)

            for i in range(total_questions):
                answered = str(i) in saved_answers
                label = f"✅ {i + 1}" if answered else f"⬜ {i + 1}"

                if cols[i % 10].button(label, key=f"jump_{i}"):
                    st.session_state.current_q = i
                    get_draft_ref(db, quiz_id, student_email).set(
                        {"current_q": i},
                        merge=True,
                    )
                    st.rerun()

            st.markdown("---")

            q = questions[current_q]

            st.subheader(f"Q{current_q + 1}. {q.get('Question', '')}")

            options = [
                q.get("Option1", ""),
                q.get("Option2", ""),
                q.get("Option3", ""),
                q.get("Option4", ""),
            ]

            previous_answer = saved_answers.get(str(current_q), None)

            selected = st.radio(
                "Choose answer",
                options,
                index=options.index(previous_answer) if previous_answer in options else 0,
                key=f"{quiz_id}_q_{current_q}",
            )

            save_answer(
                db,
                quiz_id,
                student_email,
                current_q,
                selected,
                quiz,
                student_name,
            )

            c1, c2, c3 = st.columns(3)

            with c1:
                if st.button("⬅ Previous") and current_q > 0:
                    st.session_state.current_q -= 1
                    get_draft_ref(db, quiz_id, student_email).set(
                        {"current_q": st.session_state.current_q},
                        merge=True,
                    )
                    st.rerun()

            with c2:
                if st.button("➡ Save & Next") and current_q < total_questions - 1:
                    st.session_state.current_q += 1
                    get_draft_ref(db, quiz_id, student_email).set(
                        {"current_q": st.session_state.current_q},
                        merge=True,
                    )
                    st.rerun()

            with c3:
                submit_clicked = st.button("✅ Submit Quiz")

            answered_count = len(saved_answers)
            st.info(f"Answered: {answered_count}/{total_questions}")

            if submit_clicked or time_over:
                draft = load_draft(db, quiz_id, student_email)
                saved_answers = draft.get("answers", {}) if draft else {}

                score = 0
                correct_count = 0
                wrong_count = 0
                review = []

                for i, question in enumerate(questions):
                    selected_answer = saved_answers.get(str(i), "")

                    opts = [
                        question.get("Option1", ""),
                        question.get("Option2", ""),
                        question.get("Option3", ""),
                        question.get("Option4", ""),
                    ]

                    try:
                        correct_index = int(question.get("Correct Option", 1)) - 1
                    except Exception:
                        correct_index = 0

                    correct_index = max(0, min(correct_index, 3))
                    correct_answer = opts[correct_index]

                    try:
                        marks = int(question.get("Marks", 1))
                    except Exception:
                        marks = 1

                    is_correct = selected_answer == correct_answer

                    if is_correct:
                        score += marks
                        correct_count += 1
                    else:
                        wrong_count += 1

                    review.append({
                        "Question": question.get("Question", ""),
                        "Your Answer": selected_answer,
                        "Correct Answer": correct_answer,
                        "Marks Awarded": marks if is_correct else 0,
                        "Total Marks": marks,
                        "Topic": question.get("Topic", ""),
                        "Difficulty": question.get("Difficulty", ""),
                    })

                total_marks = int(quiz.get("total_marks", 1))
                percentage = round((score / total_marks) * 100, 2)

                attempt_no = len(get_attempts(db, quiz_id, student_email)) + 1
                attempt_id = f"{quiz_id}_{safe_id(student_email)}_{attempt_no}"

                db.collection("quiz_attempts").document(attempt_id).set({
                    "quiz_id": quiz_id,
                    "quiz_title": quiz.get("title", ""),
                    "module": quiz.get("module", ""),
                    "name": student_name,
                    "email": student_email,
                    "score": score,
                    "total_marks": total_marks,
                    "percentage": percentage,
                    "correct": correct_count,
                    "wrong": wrong_count,
                    "attempt_no": attempt_no,
                    "review": review,
                    "started_at": st.session_state.quiz_started_at,
                    "submitted_at": firestore.SERVER_TIMESTAMP,
                })

                get_draft_ref(db, quiz_id, student_email).delete()

                st.success("✅ Quiz submitted successfully")
                st.metric("Score", f"{score}/{total_marks}")
                st.metric("Percentage", f"{percentage}%")
                st.dataframe(pd.DataFrame(review), use_container_width=True)

                del st.session_state.active_quiz
                del st.session_state.active_questions
                del st.session_state.quiz_started_at
                del st.session_state.current_q

                st.stop()

    with tab2:
        st.subheader("📚 My Quiz History")

        attempts = (
            db.collection("quiz_attempts")
            .where("email", "==", student_email)
            .stream()
        )

        rows = []

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
                "Submitted At": str(d.get("submitted_at")),
            })

        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            st.info("No quiz history found.")

    with tab3:
        st.subheader("🏆 My Quiz Leaderboards")

        quiz_options = []

        for qdoc in quiz_docs:
            d = qdoc.to_dict()
            quiz_options.append({
                "label": d.get("title", "Untitled Quiz"),
                "quiz_id": d.get("quiz_id"),
            })

        if quiz_options:
            selected_label = st.selectbox(
                "Select Quiz Leaderboard",
                [q["label"] for q in quiz_options],
            )

            selected_quiz_id = [
                q["quiz_id"] for q in quiz_options if q["label"] == selected_label
            ][0]

            quiz_leaderboard_panel(db, selected_quiz_id)
        else:
            st.info("No quizzes found.")

    with tab4:
        st.subheader("Debug")

        st.write("Total quizzes:", len(quiz_docs))

        debug_rows = []

        for qdoc in quiz_docs:
            d = qdoc.to_dict()

            debug_rows.append({
                "Quiz ID": d.get("quiz_id"),
                "Title": d.get("title"),
                "Active": d.get("is_active"),
                "Start": str(d.get("start_time")),
                "End": str(d.get("end_time")),
                "Questions": len(d.get("questions", [])),
            })

        st.dataframe(pd.DataFrame(debug_rows), use_container_width=True)