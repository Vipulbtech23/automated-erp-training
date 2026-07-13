import os
import sys
import re
import glob
import json
import datetime
import html
import textwrap
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from google import genai
except ImportError:
    genai = None

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    firebase_admin = None
    credentials = None
    firestore = None

try:
    from streamlit_qrcode_scanner import qrcode_scanner
except ImportError:
    qrcode_scanner = None

from app.quiz.notifications import student_notification_panel
from app.quiz.academic_journey import academic_journey_panel
from app.quiz.gamification import gamification_panel
from app.quiz.quiz_student import quiz_student_panel
from app.quiz.ai_quiz_analysis import build_student_quiz_context
from utils.speech import speak

# ================= CONFIG =================
st.set_page_config(
    page_title="LIET Student ERP",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ================= HTML RENDER HELPER =================
def render_html(content):
    """
    Render HTML without Markdown code-block conversion.
    Uses st.html when available and components.html as fallback.
    """
    if hasattr(st, "html"):
        st.html(content)
    else:
        st.components.v1.html(
            content,
            height=700,
            scrolling=True
        )

# ================= GEMINI =================
def get_gemini_api_key():
    try:
        direct_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        direct_key = ""

    try:
        nested_key = st.secrets["gemini"]["api_key"]
    except Exception:
        nested_key = ""

    return (
        str(direct_key).strip()
        or str(nested_key).strip()
        or os.getenv("GEMINI_API_KEY", "").strip()
    )


@st.cache_resource
def init_gemini():
    api_key = get_gemini_api_key()

    if genai is None or not api_key:
        return None

    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None


gemini_client = init_gemini()

# ================= FIREBASE =================
@st.cache_resource
def init_firebase():
    if firebase_admin is None:
        return None

    if firebase_admin._apps:
        return firestore.client()

    try:
        firebase_config = dict(st.secrets["firebase"])

        if "private_key" in firebase_config:
            firebase_config["private_key"] = (
                firebase_config["private_key"].replace("\\n", "\n")
            )

        cred = credentials.Certificate(firebase_config)

    except Exception:
        local_key = BASE_DIR / "firebase_key.json"

        if not local_key.exists():
            return None

        cred = credentials.Certificate(str(local_key))

    firebase_admin.initialize_app(cred)
    return firestore.client()


db = init_firebase()

# ================= HELPERS =================
def safe_id(value):
    return str(value).replace("@", "_at_").replace(".", "_").replace("/", "_")


def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def clean_text(value, default=""):
    if value is None:
        return default

    text = str(value).strip()

    if text.lower() in ["", "nan", "none", "null"]:
        return default

    return text


def safe_filename(value):
    text = clean_text(value, "Student")
    text = re.sub(r'[<>:"/\\|?*]+', "", text)
    text = re.sub(r"\s+", "_", text)
    return text or "Student"


def find_student_pdf(folder, student_name, verification_id, document_type):
    folder = Path(folder)

    if not folder.exists():
        return None

    safe_name = safe_filename(student_name)
    safe_verification_id = safe_filename(verification_id)

    if safe_verification_id:
        expected_path = folder / (
            f"{safe_name}_{safe_verification_id}_{document_type}.pdf"
        )

        if expected_path.exists():
            return str(expected_path)

    for file_path in folder.glob("*.pdf"):
        filename = file_path.name.lower()

        if (
            safe_name.lower() in filename
            and document_type.lower() in filename
            and (
                not safe_verification_id
                or safe_verification_id.lower() in filename
            )
        ):
            return str(file_path)

    if safe_verification_id:
        for file_path in folder.glob("*.pdf"):
            filename = file_path.name.lower()

            if (
                safe_verification_id.lower() in filename
                and document_type.lower() in filename
            ):
                return str(file_path)

    old_path = folder / f"{safe_name}_{document_type}.pdf"

    if old_path.exists():
        return str(old_path)

    return None


def get_gradecard(student_row):
    return find_student_pdf(
        BASE_DIR / "output" / "gradecards",
        student_row.get("Name", ""),
        student_row.get("Verification_ID", ""),
        "gradecard"
    )


def get_certificate(student_row):
    return find_student_pdf(
        BASE_DIR / "output" / "certificates",
        student_row.get("Name", ""),
        student_row.get("Verification_ID", ""),
        "certificate"
    )

def _transactional_wrapper(func):
    if firestore is not None:
        return firestore.transactional(func)
    return func


@_transactional_wrapper
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
    with open(BASE_DIR / "styles" / "style.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except:
    pass

# ================= DATA =================
df = pd.read_excel(BASE_DIR / "output" / "final_rankings.xlsx", dtype={"Email": str, "Name": str, "Roll No": str, "Verification_ID": str})
df.columns = df.columns.str.strip()
df["Email"] = df["Email"].astype(str).str.strip().str.lower()
df["Name"] = df["Name"].astype(str).str.strip()

# ================= SESSION =================
if "login" not in st.session_state:
    st.session_state.login = False

if "student_email" not in st.session_state:
    st.session_state.student_email = None

# ================= LOGIN =================
if not st.session_state.login:

    render_html(
        """
        <style>
        [data-testid="stSidebar"] {
            display: none;
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        .block-container {
            padding-top: 1.1rem;
            padding-bottom: 1.1rem;
            max-width: 1180px;
        }

        .stApp {
            min-height: 100vh;
            background:
                radial-gradient(circle at 12% 18%, rgba(0,194,255,.22), transparent 27%),
                radial-gradient(circle at 88% 16%, rgba(138,80,255,.20), transparent 27%),
                radial-gradient(circle at 75% 84%, rgba(0,255,170,.14), transparent 30%),
                linear-gradient(135deg, #06131f 0%, #0b2440 48%, #102f53 100%);
            overflow-x: hidden;
        }

        .login-title-wrap {
            text-align: center;
            margin: 6px auto 22px;
            position: relative;
            z-index: 2;
        }

        .login-kicker {
            display: inline-block;
            padding: 8px 14px;
            border-radius: 999px;
            color: #c9f7ff;
            background: rgba(0,198,255,.12);
            border: 1px solid rgba(99,230,255,.28);
            font-size: 12px;
            font-weight: 800;
            letter-spacing: .5px;
        }

        .login-main-title {
            margin: 14px 0 8px;
            color: white;
            font-size: clamp(34px, 5vw, 58px);
            line-height: 1.05;
            font-weight: 900;
            letter-spacing: -1.2px;
        }

        .login-main-title span {
            background: linear-gradient(90deg,#63e6ff,#a8ffcf);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .login-main-subtitle {
            margin: 0 auto;
            max-width: 760px;
            color: rgba(255,255,255,.78);
            font-size: 16px;
            line-height: 1.65;
        }

        .animated-orb {
            position: fixed;
            border-radius: 50%;
            filter: blur(6px);
            opacity: .50;
            z-index: 0;
            pointer-events: none;
            animation: floatOrb 10s ease-in-out infinite;
        }

        .animated-orb.one {
            width: 190px;
            height: 190px;
            left: 5%;
            top: 14%;
            background: linear-gradient(135deg,#00c6ff,#0072ff);
        }

        .animated-orb.two {
            width: 230px;
            height: 230px;
            right: 3%;
            bottom: 5%;
            background: linear-gradient(135deg,#8e2de2,#4a00e0);
            animation-delay: 1.8s;
        }

        .animated-orb.three {
            width: 120px;
            height: 120px;
            right: 18%;
            top: 22%;
            background: linear-gradient(135deg,#00f5a0,#00d9f5);
            animation-delay: 3.2s;
        }

        @keyframes floatOrb {
            0%,100% {
                transform: translate(0,0) scale(1);
            }
            50% {
                transform: translate(18px,-24px) scale(1.08);
            }
        }

        .brand-card {
            min-height: 520px;
            padding: 42px;
            border-radius: 28px;
            color: white;
            background:
                linear-gradient(135deg,rgba(255,255,255,.12),rgba(255,255,255,.05));
            border: 1px solid rgba(255,255,255,.18);
            box-shadow: 0 24px 70px rgba(0,0,0,.30);
            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);
            position: relative;
            overflow: hidden;
        }

        .brand-card::before {
            content: "";
            position: absolute;
            inset: 0;
            background:
                repeating-linear-gradient(
                    90deg,
                    rgba(255,255,255,.028) 0,
                    rgba(255,255,255,.028) 1px,
                    transparent 1px,
                    transparent 58px
                );
            pointer-events: none;
        }

        .brand-logo {
            width: 92px;
            height: 92px;
            border-radius: 24px;
            display: grid;
            place-items: center;
            font-size: 42px;
            background: linear-gradient(135deg,#fff,#dff6ff);
            box-shadow: 0 14px 30px rgba(0,0,0,.22);
            animation: logoPulse 3.2s ease-in-out infinite;
        }

        @keyframes logoPulse {
            0%,100% {
                transform: scale(1) rotate(0);
            }
            50% {
                transform: scale(1.06) rotate(2deg);
            }
        }

        .brand-heading {
            margin: 24px 0 0;
            font-size: 40px;
            line-height: 1.05;
            font-weight: 900;
        }

        .brand-copy {
            margin-top: 16px;
            color: rgba(255,255,255,.80);
            font-size: 16px;
            line-height: 1.7;
        }

        .feature-grid {
            margin-top: 28px;
            display: grid;
            grid-template-columns: repeat(2,minmax(0,1fr));
            gap: 13px;
        }

        .feature-card {
            padding: 15px;
            border-radius: 15px;
            background: rgba(255,255,255,.08);
            border: 1px solid rgba(255,255,255,.12);
            color: rgba(255,255,255,.90);
            font-size: 13px;
            line-height: 1.5;
            transition: .25s ease;
        }

        .feature-card:hover {
            transform: translateY(-4px);
            background: rgba(255,255,255,.14);
        }

        .feature-card b {
            display: block;
            margin-bottom: 4px;
            color: white;
            font-size: 14px;
        }

        .status-pill {
            margin-top: 25px;
            display: inline-flex;
            align-items: center;
            gap: 9px;
            padding: 10px 14px;
            border-radius: 999px;
            color: #c9ffe9;
            background: rgba(0,255,170,.12);
            border: 1px solid rgba(0,255,170,.25);
            font-size: 12px;
            font-weight: 800;
        }

        .status-dot {
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background: #00ffa6;
            box-shadow: 0 0 14px #00ffa6;
            animation: blinkDot 1.5s infinite;
        }

        @keyframes blinkDot {
            0%,100% { opacity: 1; }
            50% { opacity: .35; }
        }

        [data-testid="stForm"] {
            min-height: 520px;
            padding: 36px 34px 28px;
            border-radius: 28px;
            background: rgba(255,255,255,.96);
            border: 1px solid rgba(255,255,255,.58);
            box-shadow: 0 24px 70px rgba(0,0,0,.28);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
        }

        .form-head-badge {
            display: inline-block;
            padding: 8px 12px;
            border-radius: 999px;
            color: #0877c9;
            background: #e9f7ff;
            font-size: 12px;
            font-weight: 900;
            letter-spacing: .4px;
        }

        .form-head-title {
            margin: 14px 0 5px;
            color: #0b2942;
            font-size: 31px;
            font-weight: 900;
        }

        div[data-testid="stForm"] .form-head-title {
            color: #0b2942 !important;
        }

        div[data-testid="stForm"] .form-head-text {
            color: #60758a !important;
        }

        .form-head-text {
            margin: 0 0 18px;
            color: #60758a;
            font-size: 14px;
            line-height: 1.6;
        }

        div[data-testid="stTextInput"] label p {
            color: #17324d !important;
            font-weight: 800 !important;
        }

        div[data-testid="stTextInput"] input {
            min-height: 50px;
            border-radius: 14px !important;
            border: 1px solid #cfdce8 !important;
            background: #f8fbfe !important;
            color: #17324d !important;
            box-shadow: none !important;
        }

        div[data-testid="stTextInput"] input:focus {
            border-color: #0877c9 !important;
            box-shadow: 0 0 0 3px rgba(8,119,201,.12) !important;
        }

        div[data-testid="stFormSubmitButton"] button {
            width: 100%;
            min-height: 51px;
            border: none;
            border-radius: 14px;
            color: white;
            font-size: 15px;
            font-weight: 900;
            background: linear-gradient(135deg,#005bea,#00c6fb);
            box-shadow: 0 12px 24px rgba(0,112,255,.24);
            transition: .25s ease;
        }

        div[data-testid="stFormSubmitButton"] button:hover {
            transform: translateY(-2px);
            box-shadow: 0 16px 30px rgba(0,112,255,.30);
        }

        .login-help {
            margin-top: 18px;
            padding: 13px 14px;
            border-radius: 13px;
            background: #fff8e7;
            border-left: 4px solid #ffb000;
            color: #6e5717;
            font-size: 12px;
            line-height: 1.6;
        }

        .login-security {
            margin-top: 15px;
            display: grid;
            grid-template-columns: repeat(3,1fr);
            gap: 7px;
        }

        .login-security span {
            padding: 9px 6px;
            border-radius: 10px;
            text-align: center;
            color: #587087;
            background: #f3f7fa;
            font-size: 10.5px;
            font-weight: 800;
        }

        .home-portal-link {
            margin-top: 17px;
            text-align: center;
            font-size: 13px;
        }

        .home-portal-link a {
            color: #0877c9;
            text-decoration: none;
            font-weight: 900;
        }

        @media (max-width: 900px) {
            .brand-card,
            [data-testid="stForm"] {
                min-height: auto;
            }

            .brand-card {
                padding: 28px;
            }
        }

        @media (max-width: 600px) {
            .block-container {
                padding-left: .8rem;
                padding-right: .8rem;
            }

            .brand-card {
                padding: 23px;
                border-radius: 20px;
            }

            [data-testid="stForm"] {
                padding: 25px 20px;
                border-radius: 20px;
            }

            .feature-grid {
                grid-template-columns: 1fr;
            }

            .login-security {
                grid-template-columns: 1fr;
            }
        }
        </style>

        <div class="animated-orb one"></div>
        <div class="animated-orb two"></div>
        <div class="animated-orb three"></div>

        <div class="login-title-wrap">
            <div class="login-kicker">LIET SMART ACADEMIC ECOSYSTEM</div>
            <h1 class="login-main-title">
                Welcome to <span>Student ERP</span>
            </h1>
            <p class="login-main-subtitle">
                Access your academic performance, attendance, quizzes,
                certificates, achievements, AI mentor and student support.
            </p>
        </div>
        """
    )

    left_panel, right_panel = st.columns(
        [1.12, 0.88],
        gap="large"
    )

    with left_panel:
        brand_panel_html = textwrap.dedent(
            """
            <div class="brand-card">
                <div class="brand-logo">🎓</div>

                <h2 class="brand-heading">
                    Your Academic Journey,<br>
                    Smarter and Connected
                </h2>

                <p class="brand-copy">
                    The LIET Student ERP brings every essential academic
                    service into one intelligent and secure portal.
                </p>

                <div class="feature-grid">
                    <div class="feature-card">
                        <b>📊 Performance Analytics</b>
                        View marks, percentage, CGPA, rank and attendance.
                    </div>

                    <div class="feature-card">
                        <b>🧠 AI Academic Mentor</b>
                        Receive personalized study and placement guidance.
                    </div>

                    <div class="feature-card">
                        <b>📝 Smart Quiz Center</b>
                        Attempt quizzes and identify your weak topics.
                    </div>

                    <div class="feature-card">
                        <b>🏆 Verified Documents</b>
                        Download official gradecards and certificates.
                    </div>

                    <div class="feature-card">
                        <b>📌 QR Attendance</b>
                        Punch attendance securely through an active QR.
                    </div>

                    <div class="feature-card">
                        <b>💬 Chat Support</b>
                        Connect directly with the training administration.
                    </div>
                </div>

                <div class="status-pill">
                    <span class="status-dot"></span>
                    Student portal is online and secure
                </div>
            </div>
            """
        ).strip()

        render_html(brand_panel_html)

    with right_panel:
        with st.form(
            "student_login_form",
            clear_on_submit=False
        ):
            form_heading_html = textwrap.dedent(
                """
                <div class="form-head-badge">
                    🔐 SECURE STUDENT LOGIN
                </div>

                <h2 class="form-head-title">
                    Welcome Back
                </h2>

                <p class="form-head-text">
                    Sign in using your registered training email
                    and ERP password.
                </p>
                """
            ).strip()

            render_html(form_heading_html)

            email = st.text_input(
                "Registered Email",
                placeholder="student@example.com"
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your ERP password"
            )

            login_clicked = st.form_submit_button(
                "🚀 Login to Student ERP",
                use_container_width=True
            )

            form_footer_html = textwrap.dedent(
                """
                <div class="login-help">
                    <b>Login Help:</b><br>
                    Use your registered training email address.
                    Contact the training team if you cannot access your account.
                </div>

                <div class="login-security">
                    <span>🔒 Secure</span>
                    <span>⚡ Fast</span>
                    <span>☁ Cloud ERP</span>
                </div>

                <div class="home-portal-link">
                    <a href="https://automated-erp-training-home.streamlit.app/"
                       target="_blank">
                        ← Back to LIET Home Portal
                    </a>
                </div>
                """
            ).strip()

            render_html(form_footer_html)

        if login_clicked:
            clean_email = email.lower().strip()
            user = df[df["Email"] == clean_email]

            if (
                len(user) > 0
                and password == "Lloyd@2025"
            ):
                st.session_state.login = True
                st.session_state.student_email = clean_email
                st.success(
                    "Login successful. Opening your dashboard..."
                )
                st.rerun()

            else:
                st.error(
                    "Invalid email or password. Please use your "
                    "registered email and correct ERP password."
                )

    st.stop()

# ================= STUDENT =================
student_matches = df[df["Email"] == st.session_state.student_email]

if student_matches.empty:
    st.session_state.login = False
    st.session_state.student_email = None
    st.error("Student record not found. Please login again.")
    st.stop()

student = student_matches.iloc[0]

# ================= SIDEBAR =================
if (BASE_DIR / "assets" / "avatar.png").exists():
    st.sidebar.image(str(BASE_DIR / "assets" / "avatar.png"), width=130)

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
        "💬 Chat Support",
        "⚙ Settings",
        "🔔 Notifications"
    ]
)

# ================= DASHBOARD =================
if page == "🏠 Dashboard":

    st.title("🎓 Student Dashboard")
    st.success(f"Welcome {student['Name']} 👋")

    student_performance_summary = f"""
    Welcome {student['Name']}.

    Your roll number is {student.get('Roll No', 'not available')}.

    Your current rank is {student['Rank']}.

    Your percentage is {student['Percentage']} percent.

    Your C G P A is {student['CGPA']}.

    Your attendance is {student['Attendance_%']} percent.

    Your current grade is {student['Grade']}.

    Keep learning, keep practicing, and keep improving.
    """

    speak(
        student_performance_summary,
        label="🔊 Listen to My Performance",
        key=f"student_home_speech_{safe_id(student['Email'])}"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Rank", student["Rank"])
    c2.metric("Percentage", f"{student['Percentage']}%")
    c3.metric("CGPA", student["CGPA"])
    c4.metric("Attendance", f"{student['Attendance_%']}%")

    col1, col2 = st.columns([1, 3])

    with col1:
        if (BASE_DIR / "assets" / "avatar.png").exists():
            st.image(str(BASE_DIR / "assets" / "avatar.png"), width=170)

    with col2:
        st.markdown(f"""
        <div class="glass">
            <h2>{student['Name']}</h2>
            <h4>{student['Email']}</h4>
            <p>Roll Number : {student.get('Roll No', 'N/A')}</p>
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

    gradecard = get_gradecard(student)
    certificate = get_certificate(student)

    col1, col2 = st.columns(2)

    with col1:
        if gradecard and os.path.exists(gradecard):
            with open(gradecard, "rb") as f:
                st.download_button(
                    "📄 Download Gradecard",
                    f,
                    file_name=os.path.basename(gradecard)
                )
        else:
            st.warning("Gradecard not available")

    with col2:
        if certificate and os.path.exists(certificate):
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

    if db is None:
        st.error("Firebase is not configured. Attendance is unavailable.")
        st.stop()

    student_data = {
        "name": str(student["Name"]),
        "email": str(student["Email"]).strip().lower(),
        "rank": str(student["Rank"]),
        "percentage": str(student["Percentage"])
    }

    st.success(f"Logged in as: {student_data['name']}")

    st.markdown("---")
    st.subheader("📷 Scan QR Code")

    qr_token = None

    if qrcode_scanner is not None:
        try:
            qr_token = qrcode_scanner(key="student_qr_scanner")
        except Exception as e:
            st.warning("Camera scanner not working. Please paste token manually.")
            st.caption(str(e))
    else:
        st.info("QR scanner package is not installed. Use manual token input.")

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

    if db is None:
        st.error("Firebase is not configured. Quiz Center is unavailable.")
    else:
        quiz_student_panel(db, student)

# ================= AI ACADEMIC MENTOR =================
elif page == "🧠 AI Academic Mentor":

    st.title("🧠 Personal AI Academic Mentor")
    st.caption(
        "Personalized guidance using your gradecard, attendance, "
        "assessment scores and quiz history."
    )

    if gemini_client is None:
        st.error("Gemini API key is not configured.")
        st.info(
            'Add GEMINI_API_KEY = "your_key" '
            "to .streamlit/secrets.toml"
        )
        st.stop()

    student_key = clean_text(
        student.get("Verification_ID", student["Email"])
    )

    chat_key = "mentor_chat_" + safe_id(student_key)
    plan_key = "mentor_plan_" + safe_id(student_key)

    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    marks_cols = [
        column
        for column in df.columns
        if column.endswith("_Marks")
    ]

    module_scores = [
        {
            "module": (
                column
                .replace("_Marks", "")
                .replace("_", " ")
            ),
            "marks": safe_float(student.get(column, 0))
        }
        for column in marks_cols
    ]

    sorted_modules = sorted(
        module_scores,
        key=lambda item: item["marks"]
    )

    weakest_modules = sorted_modules[:5]
    strongest_modules = list(reversed(sorted_modules[-5:]))

    quiz_context = "No quiz data available."

    if db is not None:
        try:
            quiz_context = build_student_quiz_context(
                db,
                clean_text(student["Email"]).lower()
            )
        except Exception:
            quiz_context = "Quiz history could not be loaded."

    current_percentage = safe_float(student["Percentage"])
    current_attendance = safe_float(student["Attendance_%"])
    current_cgpa = safe_float(student["CGPA"])

    placement_readiness = round(
        current_percentage * 0.45
        + current_attendance * 0.20
        + current_cgpa * 10 * 0.35,
        2
    )

    if (
        current_percentage < 60
        or current_attendance < 70
        or current_cgpa < 6
    ):
        risk_level = "High Risk"
    elif (
        current_percentage < 75
        or current_attendance < 80
    ):
        risk_level = "Medium Risk"
    else:
        risk_level = "Low Risk"

    student_context = {
        "name": clean_text(student["Name"]),
        "email": clean_text(student["Email"]),
        "roll_number": clean_text(student.get("Roll No", "")),
        "verification_id": clean_text(
            student.get("Verification_ID", "")
        ),
        "rank": int(safe_float(student["Rank"])),
        "grade": clean_text(student["Grade"]),
        "cgpa": current_cgpa,
        "percentage": current_percentage,
        "attendance": current_attendance,
        "placement_readiness": placement_readiness,
        "risk_level": risk_level,
        "weakest_modules": weakest_modules,
        "strongest_modules": strongest_modules,
        "all_module_scores": module_scores,
        "quiz_context": quiz_context
    }

    m1, m2, m3, m4 = st.columns(4)

    m1.metric(
        "Percentage",
        f"{current_percentage:.2f}%"
    )

    m2.metric(
        "Attendance",
        f"{current_attendance:.2f}%"
    )

    m3.metric(
        "CGPA",
        f"{current_cgpa:.2f}"
    )

    m4.metric(
        "Placement Readiness",
        f"{placement_readiness:.2f}%"
    )

    if risk_level == "High Risk":
        st.error(f"Academic Risk: {risk_level}")
    elif risk_level == "Medium Risk":
        st.warning(f"Academic Risk: {risk_level}")
    else:
        st.success(f"Academic Risk: {risk_level}")

    if st.button(
        "✨ Generate My Complete Academic Plan",
        use_container_width=True
    ):
        plan_prompt = f"""
You are the official AI Academic Mentor for
Lloyd Institute of Engineering & Technology.

Use only the supplied student data.
Do not invent marks, attendance, achievements,
personal details, or placement guarantees.

STUDENT DATA:
{json.dumps(student_context, indent=2)}

Generate a personalized report in clear markdown:

## Academic Summary
## Strongest Areas
## Weakest Areas
## Why Performance Is Low or High
## 7-Day Study Plan
For every day include topic, revision task,
practical task, assessment task and recommended time.
## 30-Day Improvement Roadmap
## Attendance Advice
## Placement Readiness
## Recommended Projects
## Mentor Message

Use simple and supportive language.
Make every recommendation specific to this student.
"""

        with st.spinner(
            "Gemini is preparing your academic plan..."
        ):
            try:
                response = gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=plan_prompt
                )

                st.session_state[plan_key] = (
                    response.text
                    if response.text
                    else "No response generated."
                )

            except Exception as error:
                st.error(f"Gemini error: {error}")

    complete_plan = st.session_state.get(plan_key, "")

    if complete_plan:
        st.markdown(complete_plan)

        speak(
            complete_plan,
            label="🔊 Listen to My Study Plan",
            key=f"student_plan_speech_{safe_id(student_key)}"
        )

        st.download_button(
            "⬇ Download My Academic Plan",
            data=complete_plan,
            file_name=(
                f"{safe_filename(student['Name'])}"
                "_AI_Academic_Plan.md"
            ),
            mime="text/markdown",
            use_container_width=True
        )

    st.markdown("---")
    st.subheader("💬 Chat with Your AI Mentor")

    for message in st.session_state[chat_key]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_question = st.chat_input(
        "Ask about weak topics, study plan, placement, "
        "projects or quiz mistakes..."
    )

    if user_question:
        st.session_state[chat_key].append(
            {
                "role": "user",
                "content": user_question
            }
        )

        recent_chat = st.session_state[chat_key][-8:]

        conversation_text = "\n\n".join(
            (
                f"{message['role'].upper()}: "
                f"{message['content']}"
            )
            for message in recent_chat
        )

        chat_prompt = f"""
You are a personal academic mentor for an LIET student.

Use only this academic data:
{json.dumps(student_context, indent=2)}

Recent conversation:
{conversation_text}

Answer the latest question with practical,
student-specific advice.

Rules:
- Use the student's actual data.
- Mention weak and strong modules when relevant.
- Use quiz history when relevant.
- Never guarantee placement.
- Never invent marks or facts.
- Keep the answer under 400 words.
"""

        with st.chat_message("user"):
            st.markdown(user_question)

        with st.chat_message("assistant"):
            with st.spinner(
                "Mentor is analyzing your academic data..."
            ):
                try:
                    response = gemini_client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=chat_prompt
                    )

                    answer = (
                        response.text
                        if response.text
                        else "No response generated."
                    )

                except Exception as error:
                    answer = f"Gemini error: {error}"

            st.markdown(answer)

            speak(
                answer,
                label="🔊 Listen to AI Mentor",
                key=(
                    f"student_mentor_speech_"
                    f"{safe_id(student_key)}_"
                    f"{len(st.session_state[chat_key])}"
                )
            )

        st.session_state[chat_key].append(
            {
                "role": "assistant",
                "content": answer
            }
        )

elif page == "🔔 Notifications":
    if db is None:
        st.error("Firebase is not configured.")
    else:
        student_notification_panel(db, student)
                                
elif page == "📈 Academic Journey":
    if db is None:
        st.error("Firebase is not configured.")
    else:
        academic_journey_panel(db, student)
elif page == "🏅 Achievements":
    if db is None:
        st.error("Firebase is not configured.")
    else:
        gamification_panel(db, student)    

# ================= CHAT SUPPORT =================
elif page == "💬 Chat Support":

    st.title("💬 Student Support Chat")
    st.caption(
        "Send messages directly to the LIET training and ERP support team."
    )

    if db is None:
        st.error(
            "Firebase is not configured. Chat Support is unavailable."
        )
        st.stop()

    student_email = clean_text(
        student["Email"]
    ).lower()

    student_name = clean_text(
        student["Name"],
        "Student"
    )

    room_id = safe_id(
        student_email
    )

    room_ref = (
        db.collection("chat_rooms")
        .document(room_id)
    )

    st.markdown(
        """
        <style>
        .chat-shell {
            padding: 18px;
            border-radius: 20px;
            background: linear-gradient(135deg,#f5f9fc,#ffffff);
            border: 1px solid #dce7f0;
            box-shadow: 0 12px 30px rgba(0,51,102,.08);
        }

        .chat-row {
            display: flex;
            width: 100%;
            margin: 10px 0;
        }

        .chat-row.student {
            justify-content: flex-end;
        }

        .chat-row.admin {
            justify-content: flex-start;
        }

        .chat-bubble {
            max-width: 76%;
            padding: 12px 15px;
            border-radius: 16px;
            font-size: 14px;
            line-height: 1.55;
            box-shadow: 0 6px 16px rgba(0,0,0,.07);
        }

        .chat-bubble.student {
            color: white;
            background: linear-gradient(135deg,#0877c9,#00a5c8);
            border-bottom-right-radius: 4px;
        }

        .chat-bubble.admin {
            color: #243447;
            background: #ffffff;
            border: 1px solid #dbe6ee;
            border-bottom-left-radius: 4px;
        }

        .chat-meta {
            margin-top: 6px;
            font-size: 10px;
            opacity: .76;
        }

        .support-banner {
            margin-bottom: 16px;
            padding: 16px 18px;
            border-radius: 15px;
            color: #16415f;
            background: #eaf7ff;
            border-left: 5px solid #0877c9;
        }
        </style>

        <div class="support-banner">
            <b>LIET ERP Support</b><br>
            Ask questions about attendance, gradecards, certificates,
            quizzes, login access or academic records.
        </div>
        """,
        unsafe_allow_html=True
    )

    refresh_col, status_col = st.columns(
        [1, 4]
    )

    with refresh_col:
        if st.button(
            "🔄 Refresh Chat",
            use_container_width=True
        ):
            st.rerun()

    with status_col:
        st.info(
            f"Logged in as {student_name} ({student_email})"
        )

    # Create / update student chat room
    try:
        room_ref.set(
            {
                "room_id": room_id,
                "student_name": student_name,
                "student_email": student_email,
                "status": "Open"
            },
            merge=True
        )
    except Exception as error:
        st.warning(
            f"Chat room could not be initialized: {error}"
        )

    try:
        message_docs = (
            room_ref
            .collection("messages")
            .order_by("created_at")
            .stream()
        )

        messages = []
        admin_messages_to_mark_seen = []

        for message_doc in message_docs:
            message_data = message_doc.to_dict() or {}

            sender = clean_text(
                message_data.get(
                    "sender",
                    "student"
                )
            ).lower()

            messages.append(
                {
                    "id": message_doc.id,
                    "reference": message_doc.reference,
                    "text": clean_text(
                        message_data.get(
                            "text",
                            ""
                        )
                    ),
                    "sender": sender,
                    "created_at": message_data.get(
                        "created_at"
                    ),
                    "seen": bool(
                        message_data.get(
                            "seen",
                            False
                        )
                    )
                }
            )

            if (
                sender == "admin"
                and not message_data.get(
                    "seen",
                    False
                )
            ):
                admin_messages_to_mark_seen.append(
                    message_doc.reference
                )

        for message_ref in admin_messages_to_mark_seen:
            try:
                message_ref.update(
                    {
                        "seen": True
                    }
                )
            except Exception:
                pass

        try:
            room_ref.set(
                {
                    "unread_student": 0
                },
                merge=True
            )
        except Exception:
            pass

    except Exception as error:
        messages = []
        st.warning(
            f"Chat history could not be loaded: {error}"
        )

    st.markdown(
        '<div class="chat-shell">',
        unsafe_allow_html=True
    )

    if not messages:
        st.info(
            "No messages yet. Start a conversation with the support team."
        )

    else:
        for item in messages:
            sender = (
                "admin"
                if item["sender"] == "admin"
                else "student"
            )

            safe_message = html.escape(
                item["text"]
            ).replace(
                "\n",
                "<br>"
            )

            timestamp = item.get(
                "created_at"
            )

            if hasattr(
                timestamp,
                "strftime"
            ):
                timestamp_text = timestamp.strftime(
                    "%d-%m-%Y %I:%M %p"
                )
            else:
                timestamp_text = ""

            sender_label = (
                "LIET Support"
                if sender == "admin"
                else "You"
            )

            seen_text = ""

            if sender == "student":
                seen_text = (
                    " • Seen"
                    if item.get("seen")
                    else " • Sent"
                )

            st.markdown(
                f"""
                <div class="chat-row {sender}">
                    <div class="chat-bubble {sender}">
                        {safe_message}
                        <div class="chat-meta">
                            {sender_label}
                            {seen_text}
                            {" • " + timestamp_text if timestamp_text else ""}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.markdown(
        "</div>",
        unsafe_allow_html=True
    )

    st.markdown("---")

    with st.form(
        "student_support_message_form",
        clear_on_submit=True
    ):
        support_message = st.text_area(
            "Write your message",
            placeholder=(
                "Example: My certificate is not available "
                "in the download section."
            ),
            height=110
        )

        send_message = st.form_submit_button(
            "📨 Send Message",
            use_container_width=True
        )

    if send_message:
        clean_message = clean_text(
            support_message
        )

        if not clean_message:
            st.warning(
                "Please type a message before sending."
            )

        else:
            try:
                room_ref.collection(
                    "messages"
                ).add(
                    {
                        "sender": "student",
                        "text": clean_message,
                        "seen": False,
                        "created_at": firestore.SERVER_TIMESTAMP
                    }
                )

                room_ref.set(
                    {
                        "room_id": room_id,
                        "student_name": student_name,
                        "student_email": student_email,
                        "last_message": clean_message,
                        "last_sender": "student",
                        "unread_admin": firestore.Increment(1),
                        "updated_at": firestore.SERVER_TIMESTAMP,
                        "status": "Open"
                    },
                    merge=True
                )

                st.success(
                    "Your message has been sent to LIET Support."
                )

                st.rerun()

            except Exception as error:
                st.error(
                    f"Message could not be sent: {error}"
                )


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
        st.session_state.student_email = None
        st.success("Logged out successfully!")
        st.rerun()

# ================= SIDEBAR LOGOUT =================
st.sidebar.markdown("---")

if st.sidebar.button("🚪 Logout"):
    st.session_state.login = False
    st.session_state.student_email = None
    st.rerun()