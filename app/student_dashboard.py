from google import genai
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import sys
import datetime
from pathlib import Path
from quiz.notifications import student_notification_panel
import firebase_admin
from firebase_admin import credentials, firestore
from streamlit_qrcode_scanner import qrcode_scanner
from quiz.academic_journey import academic_journey_panel
from quiz.gamification import gamification_panel
BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(ROOT_DIR)

from quiz.quiz_student import quiz_student_panel
from quiz.ai_quiz_analysis import build_student_quiz_context

# ================= CONFIG =================
st.set_page_config(
    page_title="LIET Student ERP",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================= GEMINI =================
def init_gemini():
    try:
        api_key = st.secrets["gemini"]["api_key"]
        return genai.Client(api_key=api_key)
    except Exception as e:
        st.sidebar.warning("Gemini key not configured")
        return None

gemini_client = init_gemini()

# ================= FIREBASE =================
def init_firebase():
    if not firebase_admin._apps:
        try:
            firebase_config = dict(st.secrets["firebase"])
            cred = credentials.Certificate(firebase_config)
        except Exception as e:
            st.error("Firebase secrets not configured in Streamlit Cloud.")
            st.code(str(e))
            st.stop()

        firebase_admin.initialize_app(cred)

    return firestore.client()

db = init_firebase()

# ================= HELPERS =================
def safe_id(value):
    return str(value).replace("@", "_at_").replace(".", "_").replace("/", "_")

def get_gradecard(name):
    safe = name.strip().replace(" ", "_")
    return f"output/gradecards/{safe}_gradecard.pdf"

def get_certificate(name):
    safe = name.strip().replace(" ", "_")
    return f"output/certificates/{safe}_certificate.pdf"

@firestore.transactional
def punch_attendance(transaction, session_ref, record_ref, student_data):
    session_snap = session_ref.get(transaction=transaction)

    if not session_snap.exists:
        return False, "Invalid QR code"

    data = session_snap.to_dict()

    if not data.get("is_active", False):
        return False, "QR is closed by admin"

    max_scans = int(data.get("max_scans", 0))
    scanned_count = int(data.get("scanned_count", 0))

    student_key = safe_id(student_data["email"])
    attendees = data.get("attendees", {})

    if student_key in attendees:
        return False, "Attendance already punched from this QR"

    if scanned_count >= max_scans:
        return False, "QR scan limit completed"

    punch_data = {
        "name": student_data["name"],
        "email": student_data["email"],
        "rank": student_data["rank"],
        "percentage": student_data["percentage"],
        "punch_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    transaction.update(session_ref, {
        "scanned_count": firestore.Increment(1),
        f"attendees.{student_key}": punch_data
    })

    transaction.set(record_ref, {
        "session_token": data.get("token"),
        "class_name": data.get("class_name"),
        "module": data.get("module"),
        "name": student_data["name"],
        "email": student_data["email"],
        "rank": student_data["rank"],
        "percentage": student_data["percentage"],
        "status": "Present",
        "punch_time": firestore.SERVER_TIMESTAMP
    })

    return True, "Attendance punched successfully"

# ================= CSS =================
try:
    with open("styles/style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except:
    pass

# ================= DATA =================
df = pd.read_excel("output/final_rankings.xlsx")
df.columns = df.columns.str.strip()
df["Email"] = df["Email"].astype(str).str.strip().str.lower()
df["Name"] = df["Name"].astype(str).str.strip()

# ================= SESSION =================
if "login" not in st.session_state:
    st.session_state.login = False

if "student" not in st.session_state:
    st.session_state.student = None

# ================= LOGIN =================
if not st.session_state.login:

    st.markdown(
        "<h1 style='text-align:center;'>🎓 LIET Student ERP</h1>",
        unsafe_allow_html=True
    )

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        user = df[df["Email"].str.lower() == email.lower().strip()]

        if len(user) > 0 and password == "Lloyd@2025":
            st.session_state.login = True
            st.session_state.student = user.iloc[0]
            st.rerun()
        else:
            st.error("Invalid Credentials")

    st.stop()

# ================= STUDENT =================
student = st.session_state.student

# ================= SIDEBAR =================
if os.path.exists("assets/avatar.png"):
    st.sidebar.image("assets/avatar.png", width=130)

st.sidebar.markdown(f"### {student['Name']}")
st.sidebar.write(student["Email"])

page = st.sidebar.radio(
    "Navigation",
    [
        "🏠 Dashboard",
        "📥 Downloads",
        "📌 Attendance",
        "📝 Quiz Center",
        "🧠 AI Academic Mentor",
        "📈 Academic Journey",
        "🏅 Achievements",
        "⚙ Settings",
        "🔔 Notifications"
    ]
)

# ================= DASHBOARD =================
if page == "🏠 Dashboard":

    st.title("🎓 Student Dashboard")
    st.success(f"Welcome {student['Name']} 👋")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Rank", student["Rank"])
    c2.metric("Percentage", f"{student['Percentage']}%")
    c3.metric("CGPA", student["CGPA"])
    c4.metric("Attendance", f"{student['Attendance_%']}%")

    col1, col2 = st.columns([1, 3])

    with col1:
        if os.path.exists("assets/avatar.png"):
            st.image("assets/avatar.png", width=170)

    with col2:
        st.markdown(f"""
        <div class="glass">
            <h2>{student['Name']}</h2>
            <h4>{student['Email']}</h4>
            <p>CGPA : {student['CGPA']}</p>
            <p>Rank : {student['Rank']}</p>
            <p>Grade : {student['Grade']}</p>
        </div>
        """, unsafe_allow_html=True)

    st.subheader("📈 Performance")

    st.write("Overall Percentage")
    st.progress(int(student["Percentage"]))

    st.write("Attendance")
    st.progress(int(student["Attendance_%"]))

    cgpa_percent = int((float(student["CGPA"]) / 10) * 100)
    st.write("CGPA Progress")
    st.progress(cgpa_percent)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=["Attendance", "Percentage", "CGPA"],
        y=[student["Attendance_%"], student["Percentage"], student["CGPA"] * 10]
    ))
    fig.update_layout(title="My Performance", height=420)
    st.plotly_chart(fig, use_container_width=True)

    marks_cols = [c for c in df.columns if "_Marks" in c]

    if marks_cols:
        module_df = pd.DataFrame([
            {"Module": c.replace("_Marks", ""), "Marks": student[c]}
            for c in marks_cols
        ])

        fig3 = px.bar(module_df, x="Module", y="Marks", title="Module Performance")
        st.plotly_chart(fig3, use_container_width=True)

    total = len(df)
    percentile = round((1 - (student["Rank"] / total)) * 100, 2)

    st.success(f"🏆 You are better than **{percentile}%** students")

    st.subheader("🏅 Achievements")

    if student["Rank"] == 1:
        st.balloons()
        st.success("🥇 College Topper")
    elif student["Rank"] <= 3:
        st.success("🥈 Top 3 Performer")
    elif student["Rank"] <= 10:
        st.info("🥉 Top 10 Performer")
    else:
        st.warning("🏅 Participant")

# ================= DOWNLOADS =================
elif page == "📥 Downloads":

    st.title("📥 Download Center")

    c1, c2, c3 = st.columns(3)

    c1.metric("Rank", student["Rank"])
    c2.metric("Grade", student["Grade"])
    c3.metric("Percentage", f"{student['Percentage']}%")

    gradecard = get_gradecard(student["Name"])
    certificate = get_certificate(student["Name"])

    col1, col2 = st.columns(2)

    with col1:
        if os.path.exists(gradecard):
            with open(gradecard, "rb") as f:
                st.download_button(
                    "📄 Download Gradecard",
                    f,
                    file_name=os.path.basename(gradecard)
                )
        else:
            st.warning("Gradecard not available")

    with col2:
        if os.path.exists(certificate):
            with open(certificate, "rb") as f:
                st.download_button(
                    "🏆 Download Certificate",
                    f,
                    file_name=os.path.basename(certificate)
                )
        else:
            st.warning("Certificate not available")

# ================= ATTENDANCE =================
elif page == "📌 Attendance":

    st.title("📌 QR Attendance")

    student_data = {
        "name": str(student["Name"]),
        "email": str(student["Email"]).strip().lower(),
        "rank": str(student["Rank"]),
        "percentage": str(student["Percentage"])
    }

    st.success(f"Logged in as: {student_data['name']}")

    st.markdown("---")
    st.subheader("📷 Scan QR Code")

    try:
        qr_token = qrcode_scanner(key="student_qr_scanner")
    except Exception as e:
        qr_token = None
        st.warning("Camera scanner not working. Please paste token manually.")
        st.caption(str(e))

    manual_token = st.text_input("Paste QR Token Manually")

    token = qr_token or manual_token

    if token:
        st.write("Detected QR Token:")
        st.code(token)

        if st.button("✅ Punch Attendance"):

            session_ref = db.collection("attendance_sessions").document(token.strip())

            record_id = f"{token.strip()}_{safe_id(student_data['email'])}"
            record_ref = db.collection("attendance_records").document(record_id)

            transaction = db.transaction()

            success, msg = punch_attendance(
                transaction,
                session_ref,
                record_ref,
                student_data
            )

            if success:
                st.success("✅ " + msg)
            else:
                st.warning("⚠️ " + msg)

    st.markdown("---")
    st.subheader("📊 My Attendance Records")

    records = (
        db.collection("attendance_records")
        .where("email", "==", student_data["email"])
        .stream()
    )

    my_rows = []

    for r in records:
        d = r.to_dict()
        my_rows.append({
            "Class": d.get("class_name"),
            "Module": d.get("module"),
            "Status": d.get("status"),
            "Punch Time": str(d.get("punch_time"))
        })

    if my_rows:
        st.dataframe(pd.DataFrame(my_rows), use_container_width=True)
    else:
        st.info("No attendance records found.")

# ================= QUIZ CENTER =================
elif page == "📝 Quiz Center":

    quiz_student_panel(db, student)

# ================= AI ACADEMIC MENTOR =================
elif page == "🧠 AI Academic Mentor":

    st.title("🧠 Personal Academic Mentor Agent")
    st.info("Ask anything. This AI reads your scorecard and quiz history.")

    if gemini_client is None:
        st.error("Gemini API key not configured.")
        st.stop()

    if "mentor_chat" not in st.session_state:
        st.session_state.mentor_chat = []

    marks_cols = [c for c in df.columns if "_Marks" in c]

    module_details = ""

    for c in marks_cols:
        try:
            module_details += f"{c}: {student[c]}\n"
        except:
            pass

    quiz_context = build_student_quiz_context(
        db,
        str(student["Email"]).strip().lower()
    )

    student_context = f"""
You are an AI Academic Mentor for LIET Student ERP.

Student Profile:
Name: {student['Name']}
Email: {student['Email']}
Rank: {student['Rank']}
Grade: {student['Grade']}
CGPA: {student['CGPA']}
Percentage: {student['Percentage']}
Attendance: {student['Attendance_%']}%

Module Scores:
{module_details}

Quiz Data:
{quiz_context}

Rules:
- Answer personally for this student only.
- Use student's scorecard and quiz history.
- If student asks weak topic, use quiz wrong-answer data.
- If student asks improvement, give topic-wise plan.
- If student asks why marks are low, explain using quiz attempts.
- Keep tone friendly, motivational, and clear.
- Do not give generic answer.
"""

    for role, msg in st.session_state.mentor_chat:
        with st.chat_message(role):
            st.write(msg)

    user_question = st.chat_input("Ask your academic mentor...")

    if user_question:

        st.session_state.mentor_chat.append(("user", user_question))

        full_prompt = f"""
{student_context}

Previous Chat:
{st.session_state.mentor_chat[-6:]}

Student Question:
{user_question}
"""

        with st.spinner("Mentor is analyzing your scorecard and quiz history..."):
            try:
                response = gemini_client.models.generate_content(
                    model="models/gemini-2.5-flash",
                    contents=full_prompt
                )
                answer = response.text
            except Exception as e:
                answer = f"Error: {e}"

        st.session_state.mentor_chat.append(("assistant", answer))
        st.rerun()
elif page == "🔔 Notifications":
    student_notification_panel(db, student)
                                
elif page == "📈 Academic Journey":
    academic_journey_panel(db, student)
elif page == "🏅 Achievements":
    gamification_panel(db, student)    
# ================= SETTINGS =================
elif page == "⚙ Settings":

    st.title("⚙ Settings Panel")

    st.subheader("🎨 Theme Settings")

    theme = st.selectbox("Choose Theme", ["Light", "Dark"])

    if theme == "Dark":
        st.markdown(
            """
            <style>
            body { background-color: #0e1117; color: white; }
            </style>
            """,
            unsafe_allow_html=True
        )
        st.success("Dark theme applied")
    else:
        st.success("Light theme active")

    st.markdown("---")

    st.subheader("🚪 Logout")

    if st.button("Logout Now"):
        st.session_state.login = False
        st.session_state.student = None
        st.success("Logged out successfully!")
        st.rerun()

# ================= SIDEBAR LOGOUT =================
st.sidebar.markdown("---")

if st.sidebar.button("🚪 Logout"):
    st.session_state.login = False
    st.session_state.student = None
    st.rerun()