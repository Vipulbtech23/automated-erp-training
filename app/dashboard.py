try:
    import streamlit as st
except ImportError:
    print("streamlit not installed. Run: pip install streamlit")
    raise

import pandas as pd
from quiz.gamification import admin_gamification_leaderboard
import plotly.express as px

import os
import glob
import re
import sys
import zipfile
import datetime
import uuid
import qrcode
import subprocess
import json

try:
    from google import genai
except ImportError:
    genai = None

from io import BytesIO
from quiz.ai_quiz_analysis import get_admin_quiz_summary
from quiz.quiz_admin import quiz_admin_panel
from quiz.notifications import admin_notification_panel
from pathlib import Path

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    st.error("firebase_admin not installed. Run: pip install firebase-admin")

try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
except (ImportError, ModuleNotFoundError):
    st.error("reportlab not installed. Run: pip install reportlab")
BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from utils.speech import speak

ATTENDANCE_FILE = "output/attendance.csv"
# ================= ROOT =================
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(ROOT_DIR)

from scripts.send_email import Emailer


# ================= CONFIG =================
st.set_page_config(page_title="LIET ERP", layout="wide")
# ================= FIREBASE =================

def init_firebase():

    if firebase_admin._apps:
        return firestore.client()

    try:
        # Streamlit Cloud
        firebase_dict = dict(st.secrets["firebase"])
        firebase_dict["private_key"] = firebase_dict["private_key"].replace("\\n", "\n")
        cred = credentials.Certificate(firebase_dict)

    except Exception:
        # Local Development
        cred = credentials.Certificate(
            os.path.join(BASE_DIR, "firebase_key.json")
        )

    firebase_admin.initialize_app(cred)

    return firestore.client()


db = init_firebase()

def admin_chat_panel(db):
    """
    Admin-side chat that uses the same Firestore structure as student chat:

    chat_rooms/{room_id}
        room_id
        student_name
        student_email
        last_message
        last_sender
        unread_admin
        unread_student
        status
        updated_at

    chat_rooms/{room_id}/messages/{message_id}
        sender: student/admin
        text
        seen
        created_at
    """

    st.title("💬 Student Support Chat")
    st.caption(
        "Open student conversations, reply to messages, "
        "mark chats resolved, reopen them, or delete a complete chat."
    )

    st.markdown(
        """
        <style>
        .admin-chat-banner {
            padding: 17px 19px;
            border-radius: 16px;
            background: linear-gradient(135deg,#eaf7ff,#ffffff);
            border-left: 5px solid #0877c9;
            color: #16415f;
            margin-bottom: 18px;
        }

        .room-card {
            padding: 14px 16px;
            border-radius: 14px;
            background: #f7fbfe;
            border: 1px solid #dce8f1;
            margin-bottom: 8px;
        }

        .room-open {
            color: #0877c9;
            font-weight: 800;
        }

        .room-resolved {
            color: #198754;
            font-weight: 800;
        }
        </style>

        <div class="admin-chat-banner">
            <b>LIET ERP Student Support</b><br>
            Messages shown here come directly from the Student ERP Chat Support page.
        </div>
        """,
        unsafe_allow_html=True
    )

    try:
        room_docs = db.collection("chat_rooms").stream()
    except Exception as error:
        st.error(f"Unable to load student chats: {error}")
        return

    room_rows = []

    for room_doc in room_docs:
        room_data = room_doc.to_dict() or {}

        room_id = (
            room_data.get("room_id")
            or room_doc.id
        )

        room_rows.append(
            {
                "Room ID": room_id,
                "Student": room_data.get("student_name", "Unknown Student"),
                "Email": room_data.get("student_email", ""),
                "Last Message": room_data.get("last_message", ""),
                "Unread": int(room_data.get("unread_admin", 0) or 0),
                "Status": room_data.get("status", "Open"),
                "Updated Raw": room_data.get("updated_at"),
                "Updated": str(room_data.get("updated_at", ""))
            }
        )

    if not room_rows:
        st.info("No student chat conversations found.")
        return

    room_df = pd.DataFrame(room_rows)

    def updated_sort_value(value):
        try:
            return value.timestamp()
        except Exception:
            return 0

    room_df["_updated_sort"] = room_df["Updated Raw"].apply(updated_sort_value)

    room_df = room_df.sort_values(
        by=["Unread", "_updated_sort"],
        ascending=[False, False]
    ).reset_index(drop=True)

    display_df = room_df[
        [
            "Student",
            "Email",
            "Last Message",
            "Unread",
            "Status",
            "Updated"
        ]
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )

    room_options = {
        (
            f"{row['Student']} | {row['Email']} | "
            f"Unread: {row['Unread']} | {row['Status']}"
        ): row["Room ID"]
        for _, row in room_df.iterrows()
    }

    selected_label = st.selectbox(
        "Select Student Conversation",
        list(room_options.keys()),
        key="admin_selected_chat_room"
    )

    room_id = room_options[selected_label]

    selected_room = room_df[
        room_df["Room ID"] == room_id
    ].iloc[0]

    room_ref = db.collection("chat_rooms").document(room_id)

    # Admin opened the room, so admin unread count becomes zero.
    try:
        room_ref.set(
            {
                "unread_admin": 0
            },
            merge=True
        )
    except Exception:
        pass

    st.subheader(
        f"Chat with {selected_room['Student']}"
    )

    st.caption(
        f"{selected_room['Email']} • Status: {selected_room['Status']}"
    )

    try:
        message_docs = (
            room_ref
            .collection("messages")
            .order_by("created_at")
            .stream()
        )
    except Exception as error:
        st.error(f"Unable to load chat messages: {error}")
        return

    messages_found = False
    student_message_refs_to_mark_seen = []

    for message_doc in message_docs:
        messages_found = True
        message_data = message_doc.to_dict() or {}

        sender = str(
            message_data.get("sender", "student")
        ).lower()

        text_value = str(
            message_data.get("text", "")
        )

        created_at = message_data.get("created_at")

        role = (
            "assistant"
            if sender == "admin"
            else "user"
        )

        with st.chat_message(role):
            st.write(text_value)

            if created_at:
                st.caption(str(created_at))

            if sender == "admin":
                if message_data.get("seen", False):
                    st.caption("Seen by student")
                else:
                    st.caption("Sent")
            else:
                if not message_data.get("seen", False):
                    student_message_refs_to_mark_seen.append(
                        message_doc.reference
                    )

    # Mark student messages as seen after admin opens the room.
    for message_ref in student_message_refs_to_mark_seen:
        try:
            message_ref.update(
                {
                    "seen": True
                }
            )
        except Exception:
            pass

    if not messages_found:
        st.info("No messages found in this conversation.")

    with st.form(
        f"admin_reply_form_{room_id}",
        clear_on_submit=True
    ):
        reply = st.text_area(
            "Reply to student",
            placeholder="Write your reply...",
            height=110
        )

        send_reply = st.form_submit_button(
            "📤 Send Reply",
            use_container_width=True
        )

    if send_reply:
        clean_reply = reply.strip()

        if not clean_reply:
            st.warning("Please write a reply.")
        else:
            try:
                room_ref.collection("messages").add(
                    {
                        "sender": "admin",
                        "text": clean_reply,
                        "seen": False,
                        "created_at": firestore.SERVER_TIMESTAMP
                    }
                )

                room_ref.set(
                    {
                        "room_id": room_id,
                        "student_name": selected_room["Student"],
                        "student_email": selected_room["Email"],
                        "last_message": clean_reply,
                        "last_sender": "admin",
                        "unread_student": firestore.Increment(1),
                        "updated_at": firestore.SERVER_TIMESTAMP,
                        "status": "Open"
                    },
                    merge=True
                )

                st.success("Reply sent successfully.")
                st.rerun()

            except Exception as error:
                st.error(f"Reply could not be sent: {error}")

    action1, action2, action3, action4 = st.columns(4)

    with action1:
        if st.button(
            "✅ Mark Resolved",
            use_container_width=True,
            key=f"resolve_chat_{room_id}"
        ):
            try:
                room_ref.set(
                    {
                        "status": "Resolved",
                        "updated_at": firestore.SERVER_TIMESTAMP
                    },
                    merge=True
                )

                st.success("Conversation marked as resolved.")
                st.rerun()

            except Exception as error:
                st.error(f"Could not resolve chat: {error}")

    with action2:
        if st.button(
            "🔓 Reopen",
            use_container_width=True,
            key=f"reopen_chat_{room_id}"
        ):
            try:
                room_ref.set(
                    {
                        "status": "Open",
                        "updated_at": firestore.SERVER_TIMESTAMP
                    },
                    merge=True
                )

                st.success("Conversation reopened.")
                st.rerun()

            except Exception as error:
                st.error(f"Could not reopen chat: {error}")

    with action3:
        if st.button(
            "🔄 Refresh",
            use_container_width=True,
            key=f"refresh_chat_{room_id}"
        ):
            st.rerun()

    with action4:
        confirm_delete_chat = st.checkbox(
            "Confirm delete",
            key=f"confirm_delete_chat_{room_id}"
        )

        if st.button(
            "🗑 Delete Chat",
            use_container_width=True,
            key=f"delete_chat_{room_id}",
            disabled=not confirm_delete_chat
        ):
            try:
                message_refs = (
                    room_ref
                    .collection("messages")
                    .stream()
                )

                for message_ref in message_refs:
                    message_ref.reference.delete()

                room_ref.delete()

                st.success("Chat and all its messages deleted permanently.")
                st.rerun()

            except Exception as error:
                st.error(f"Could not delete chat: {error}")



def admin_notification_delete_panel(db):
    """
    Permanent notification delete manager.

    It checks both common collection names:
    - notifications
    - student_notifications

    Deleted Firestore documents will no longer appear
    in the student dashboard.
    """

    st.markdown("---")
    st.subheader("🗑 Delete Existing Notifications")
    st.caption(
        "A permanently deleted notification will no longer be available "
        "to students on their dashboard."
    )

    collection_name = st.selectbox(
        "Notification Collection",
        [
            "notifications",
            "student_notifications"
        ],
        key="notification_delete_collection"
    )

    try:
        notification_docs = list(
            db.collection(collection_name).stream()
        )
    except Exception as error:
        st.error(f"Unable to load notifications: {error}")
        return

    notification_rows = []

    for notification_doc in notification_docs:
        data = notification_doc.to_dict() or {}

        title = (
            data.get("title")
            or data.get("heading")
            or data.get("subject")
            or "Untitled Notification"
        )

        message = (
            data.get("message")
            or data.get("body")
            or data.get("text")
            or ""
        )

        target = (
            data.get("target")
            or data.get("student_email")
            or data.get("email")
            or data.get("audience")
            or "All Students"
        )

        created_at = (
            data.get("created_at")
            or data.get("timestamp")
            or data.get("date")
            or ""
        )

        notification_rows.append(
            {
                "Document ID": notification_doc.id,
                "Title": str(title),
                "Message": str(message),
                "Target": str(target),
                "Created": str(created_at)
            }
        )

    if not notification_rows:
        st.info(
            f"No notifications found in '{collection_name}'."
        )
        return

    notification_df = pd.DataFrame(
        notification_rows
    )

    st.dataframe(
        notification_df[
            [
                "Title",
                "Message",
                "Target",
                "Created"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

    option_labels = {
        (
            f"{row['Title']} | {row['Target']} | "
            f"{row['Document ID']}"
        ): row["Document ID"]
        for _, row in notification_df.iterrows()
    }

    selected_label = st.selectbox(
        "Select Notification to Delete",
        list(option_labels.keys()),
        key="selected_notification_to_delete"
    )

    selected_document_id = option_labels[
        selected_label
    ]

    selected_notification = notification_df[
        notification_df["Document ID"]
        == selected_document_id
    ].iloc[0]

    st.warning(
        f"Selected: {selected_notification['Title']}\n\n"
        f"{selected_notification['Message']}"
    )

    confirm_delete = st.checkbox(
        "I understand this notification will be permanently deleted.",
        key="confirm_notification_delete"
    )

    delete_col1, delete_col2 = st.columns(2)

    with delete_col1:
        if st.button(
            "🗑 Delete Selected Notification",
            use_container_width=True,
            disabled=not confirm_delete,
            key="delete_selected_notification"
        ):
            try:
                db.collection(
                    collection_name
                ).document(
                    selected_document_id
                ).delete()

                st.success(
                    "Notification deleted permanently. "
                    "It will no longer appear in the Student ERP."
                )

                st.rerun()

            except Exception as error:
                st.error(
                    f"Notification could not be deleted: {error}"
                )

    with delete_col2:
        confirm_all = st.checkbox(
            "Confirm delete all",
            key="confirm_delete_all_notifications"
        )

        if st.button(
            "🧹 Delete All Notifications",
            use_container_width=True,
            disabled=not confirm_all,
            key="delete_all_notifications"
        ):
            try:
                deleted_count = 0

                for notification_doc in notification_docs:
                    notification_doc.reference.delete()
                    deleted_count += 1

                st.success(
                    f"{deleted_count} notification(s) deleted permanently."
                )

                st.rerun()

            except Exception as error:
                st.error(
                    f"Notifications could not be deleted: {error}"
                )


# ================= LOGIN =================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "liet123"

if not st.session_state.logged_in:

    st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(135deg, #061a40, #0b3d91, #00b4d8);
    }

    .hero-login-title {
        text-align: center;
        color: white;
        font-size: 42px;
        font-weight: 900;
        margin-top: 20px;
        margin-bottom: 5px;
    }

    .hero-login-subtitle {
        text-align: center;
        color: #e8f4ff;
        font-size: 17px;
        margin-bottom: 35px;
    }

    .speech {
        background: white;
        color: #003366;
        padding: 16px 24px;
        border-radius: 22px;
        font-weight: 800;
        text-align: center;
        box-shadow: 0 15px 35px rgba(0,0,0,0.25);
        margin-bottom: 20px;
        animation: slideUp 0.9s ease;
    }

    .character {
        text-align: center;
        font-size: 160px;
        animation: float 3s ease-in-out infinite;
        filter: drop-shadow(0 20px 40px rgba(0,0,0,0.35));
    }

    div[data-testid="stForm"] {
        background: rgba(255,255,255,0.18);
        backdrop-filter: blur(18px);
        padding: 34px;
        border-radius: 28px;
        border: 1px solid rgba(255,255,255,0.30);
        box-shadow: 0 25px 70px rgba(0,0,0,0.35);
        animation: slideUp 1s ease;
    }

    div[data-testid="stTextInput"] label {
        color: white;
        font-weight: 700;
    }

    div[data-testid="stTextInput"] input {
        border-radius: 14px;
        padding: 14px;
        font-size: 16px;
    }

    .stButton button {
        width: 100%;
        border-radius: 14px;
        padding: 14px;
        font-size: 18px;
        font-weight: 800;
        background: linear-gradient(135deg,#ff9800,#ff5722);
        color: white;
        border: none;
    }

    .bubble {
        position: fixed;
        width: 18px;
        height: 18px;
        background: rgba(255,255,255,0.35);
        border-radius: 50%;
        animation: bubble 9s infinite ease-in-out;
    }

    .b1 { left: 8%; top: 20%; animation-delay: 0s; }
    .b2 { left: 85%; top: 25%; animation-delay: 2s; }
    .b3 { left: 15%; top: 75%; animation-delay: 4s; }
    .b4 { left: 75%; top: 80%; animation-delay: 1s; }

    @keyframes slideUp {
        from {opacity:0; transform: translateY(40px);}
        to {opacity:1; transform: translateY(0);}
    }

    @keyframes float {
        0% {transform: translateY(0);}
        50% {transform: translateY(-18px);}
        100% {transform: translateY(0);}
    }

    @keyframes bubble {
        0% {transform: translateY(0) scale(1); opacity:0.4;}
        50% {transform: translateY(-140px) scale(1.7); opacity:0.9;}
        100% {transform: translateY(0) scale(1); opacity:0.4;}
    }
    </style>

    <div class="bubble b1"></div>
    <div class="bubble b2"></div>
    <div class="bubble b3"></div>
    <div class="bubble b4"></div>

    <div class="hero-login-title">🔐 LIET Admin Login</div>
    <div class="hero-login-subtitle">AI-Powered Academic ERP + LMS Control Center</div>
    """, unsafe_allow_html=True)

    left, right = st.columns([1.1, 1])

    with left:
        st.markdown("""
        <div class="speech">👋 Welcome Admin! Login from the secure panel</div>
        <div class="character">👨‍🏫👉</div>
        """, unsafe_allow_html=True)

    with right:
        with st.form("admin_login_form"):
            st.markdown("### 🔐 Secure Login")
            username = st.text_input("Username", placeholder="Enter admin username")
            password = st.text_input("Password", type="password", placeholder="Enter password")

            login_btn = st.form_submit_button("🚀 Login to Dashboard")

            if login_btn:
                if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                    st.session_state.logged_in = True
                    # Login ke baad admin summary ek baar bolegi
                    st.session_state.admin_voice_pending = True
                    st.success("Login Successful")
                    st.rerun()
                else:
                    st.error("Invalid Username or Password")

    st.stop()


df = pd.read_excel("output/final_rankings.xlsx")
df.columns = df.columns.str.strip()

# CLEAN DATA
df["Email"] = df["Email"].astype(str).str.strip().str.lower()
df["Name"] = df["Name"].astype(str).str.strip()
df["Badge"] = df["Rank"].apply(
    lambda x:
        "🥇 Gold" if x == 1
        else "🥈 Silver" if x <= 3
        else "🥉 Bronze" if x <= 10
        else "🏅 Participant"
)
# ================= AUTOMATIC ADMIN VOICE SUMMARY =================

if st.session_state.get("admin_voice_pending", False):

    total_students = len(df)

    average_percentage = round(
        pd.to_numeric(df["Percentage"], errors="coerce").fillna(0).mean(),
        2
    )

    top_score = (
        pd.to_numeric(df["Total"], errors="coerce").fillna(0).max()
        if "Total" in df.columns
        else 0
    )

    top_cgpa = (
        pd.to_numeric(df["CGPA"], errors="coerce").fillna(0).max()
        if "CGPA" in df.columns
        else 0
    )

    low_performers = (
        pd.to_numeric(df["Percentage"], errors="coerce").fillna(0) < 60
    ).sum()

    current_hour = datetime.datetime.now().hour

    if current_hour < 12:
        greeting = "Good morning"
    elif current_hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    admin_summary = f"""
    {greeting}, Admin.

    Welcome to the LIET Smart ERP and Learning Management System control center.

    There are currently {total_students} students in the academic database.

    The average student percentage is {average_percentage} percent.

    The highest recorded score is {top_score}.

    The highest C G P A is {top_cgpa}.

    There are {low_performers} students currently scoring below sixty percent.

    Please review quiz activity, attendance, reports, notifications, and students requiring academic mentoring.

    Have a productive day.
    """

    speak(admin_summary)

    st.session_state.admin_voice_pending = False
# ================= GRADE DISTRIBUTION DATA =================

grade_count = (
    df["Grade"]
    .value_counts()
    .reset_index()
)

grade_count.columns = ["Grade", "Students"]

# ================= PATH FUNCTIONS =================
def safe_filename(value):
    text = str(value).strip()
    text = re.sub(r'[<>:"/\\|?*]+', "", text)
    text = re.sub(r"\s+", "_", text)
    return text or "Student"


def find_student_document(student_row, document_type):
    """
    Finds files such as:
    Name_LIET-MLAI-046_gradecard.pdf
    Name_LIET-MLAI-046_certificate.pdf
    """

    name = safe_filename(student_row.get("Name", "Student"))
    verification_id = safe_filename(
        student_row.get("Verification_ID", "")
    )

    if document_type == "gradecard":
        folder = os.path.join("output", "gradecards")
    elif document_type == "certificate":
        folder = os.path.join("output", "certificates")
    else:
        raise ValueError("document_type must be gradecard or certificate")

    exact_path = os.path.join(
        folder,
        f"{name}_{verification_id}_{document_type}.pdf"
    )

    if os.path.exists(exact_path):
        return exact_path

    # Fallback for case differences or small filename variations
    for file_path in glob.glob(os.path.join(folder, "*.pdf")):
        filename = os.path.basename(file_path).lower()

        if (
            verification_id.lower() in filename
            and f"_{document_type}" in filename
        ):
            return file_path

    # Older filename fallback
    old_path = os.path.join(
        folder,
        f"{name}_{document_type}.pdf"
    )

    if os.path.exists(old_path):
        return old_path

    return None


def get_pdf_path(student_row):
    return find_student_document(student_row, "gradecard")


def get_gradecard(student_row):
    return find_student_document(student_row, "gradecard")


def get_certificate(student_row):
    return find_student_document(student_row, "certificate")


# ================= EMAILER =================
EMAILER = None

# ================= ROLE (NO LOGIN) =================
st.sidebar.success("👤 Admin")

if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.session_state.admin_voice_pending = False
    st.rerun()
# ================= MENU =================
menu = st.sidebar.radio(
    "Navigation",
    [
        "Home",
        
        "Analytics",
        "Module Analysis",
        "Low Performers",
       
        "Reports",
        "Certificates",
        "Email Center",
        "Top Performers",
        "📚 Quiz Management",
        "📢 Notifications",
        "💬 Chat Support",
        
        "Attendance",
       "🧠 AI Academic Officer"
    ]
)
if menu == "Home":
    summary = f"""
Good Morning Sir.

Welcome to LIET Smart ERP.

There are {len(df)} students.

Average percentage is {round(df['Percentage'].mean(),2)}.

Highest score is {df['Total'].max()}.

Highest CGPA is {df['CGPA'].max()}.

Have a productive day.
"""
    st.markdown("""
    <div style="
        padding:28px;
        border-radius:18px;
        background:linear-gradient(135deg,#003366,#0066cc,#00bcd4);
        color:white;
        margin-bottom:25px;">
        <h1 style="margin:0;">🎓 LIET Smart ERP Admin Dashboard</h1>
        <p style="margin:8px 0 0 0;font-size:18px;">
            AI-Powered Academic ERP + LMS Control Center
        </p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("🎤 Speak Today's Summary"):
        speak(summary)
    # ================= KPI CARDS =================
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("👨‍🎓 Students", len(df))
    c2.metric("📈 Average %", round(df["Percentage"].mean(), 2))
    c3.metric("🏆 Top Score", df["Total"].max())
    c4.metric("🎯 Top CGPA", df["CGPA"].max())

    st.markdown("---")

    # ================= QUICK ACTIONS =================
    st.subheader("⚡ Quick Academic Actions")

    a1, a2, a3 = st.columns(3)

    with a1:
        if st.button("🚀 Run Complete Pipeline", use_container_width=True):
            os.system("python scripts/merge_quizzes.py")
            os.system("python scripts/calculate_scores.py")
            os.system("python scripts/generate_scorecard.py")
            os.system("python scripts/certificate_generator.py")
            os.system("python scripts/send_bulk_emails.py")
            st.success("All reports generated successfully.")

    with a2:
        if st.button("🔄 Update Rankings From Quiz", use_container_width=True):
            result = os.system("python scripts/update_rankings_from_quiz.py")

            if result == 0:
                st.success("Rankings updated from quiz attempts.")
                st.info("Refresh app to see updated data.")
            else:
                st.error("Ranking update failed.")

    with a3:
        if st.button("🔁 Full Academic Refresh", use_container_width=True):
            with st.spinner("Updating rankings, gradecards and certificates..."):
                result = subprocess.run(
                    [sys.executable, "scripts/full_academic_refresh.py"],
                    capture_output=True,
                    text=True
                )

            if result.returncode == 0:
                st.success("Full academic refresh completed.")
                with st.expander("View Logs"):
                    st.code(result.stdout)
            else:
                st.error("Refresh failed.")
                st.code(result.stderr)

    st.markdown("---")

    # ================= AI + SYSTEM OVERVIEW =================
    left, right = st.columns([2, 1])

    with left:
        st.subheader("📊 Performance Distribution")

        bins = [0, 40, 60, 75, 90, 100]
        labels = ["0-40", "40-60", "60-75", "75-90", "90-100"]

        df["Percentile Range"] = pd.cut(
            df["Percentage"],
            bins=bins,
            labels=labels,
            include_lowest=True
        )

        pie_data = df["Percentile Range"].value_counts().reset_index()
        pie_data.columns = ["Range", "Students"]

        fig = px.pie(
            pie_data,
            names="Range",
            values="Students",
            hole=0.45,
            title="Student Performance Range"
        )

        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("🧠 AI Snapshot")

        try:
            quiz_ai = get_admin_quiz_summary(db)

            st.info(quiz_ai["summary_text"])

            if not quiz_ai["weak_students_df"].empty:
                st.warning(
                    f"Students needing mentoring: {len(quiz_ai['weak_students_df'])}"
                )

            if not quiz_ai["weak_topics_df"].empty:
                top_topic = quiz_ai["weak_topics_df"].iloc[0]["topic"]
                st.error(f"Weakest Topic: {top_topic}")

        except Exception as e:
            st.warning("AI quiz summary not available yet.")

        st.subheader("🟢 System Status")
        st.success("Firestore Connected")
        st.success("ERP Running")
        st.success("LMS Active")

    st.markdown("---")

    # ================= TOP STUDENTS =================
    st.subheader("🏆 Top Performing Students")

    top_students = df.sort_values("Rank").head(10)

    st.dataframe(
        top_students[
            ["Name", "Email", "Rank", "Badge", "Grade", "Percentage", "CGPA"]
        ],
        use_container_width=True
    )

    st.markdown("---")

    # ================= EMAIL REPORTS =================
    with st.expander("📧 Email Updated Reports", expanded=False):

        sender_email = st.text_input("Sender Gmail", key="refresh_email_sender")
        app_password = st.text_input(
            "Gmail App Password",
            type="password",
            key="refresh_email_pass"
        )

        col1, col2 = st.columns(2)

        with col1:
            send_gradecard = st.checkbox("Send Updated Gradecards", value=True)

        with col2:
            send_certificate = st.checkbox("Send Certificates", value=False)

        if st.button("📧 Email Updated Reports", use_container_width=True):
            if not sender_email or not app_password:
                st.error("Please enter Gmail and App Password.")
            else:
                from scripts.email_updated_reports import email_updated_reports

                with st.spinner("Sending updated reports..."):
                    email_updated_reports(
                        sender_email,
                        app_password,
                        send_gradecard,
                        send_certificate
                    )

                st.success("Email process completed. Check terminal/logs.")

    st.markdown("---")

    # ================= GAMIFICATION =================
    with st.expander("🏅 Gamification Leaderboard", expanded=False):
        admin_gamification_leaderboard(db)

    st.markdown("---")

    # ================= FULL STUDENT DATA =================
    with st.expander("👨‍🎓 View All Students Data", expanded=False):

        search_name = st.text_input("Search student by name")

        if search_name:
            filtered_df = df[df["Name"].str.contains(search_name, case=False)]
        else:
            filtered_df = df.sort_values("Rank")

        st.dataframe(filtered_df, use_container_width=True)
elif menu == "Top Performers":

    st.title("🏆 Hall of Fame")

    top3 = df.sort_values("Rank").head(3)

    c1,c2,c3 = st.columns(3)

    with c1:
        st.success(f"🥇 {top3.iloc[0]['Name']}")
        st.metric("Percentage", top3.iloc[0]["Percentage"])

    with c2:
        st.info(f"🥈 {top3.iloc[1]['Name']}")
        st.metric("Percentage", top3.iloc[1]["Percentage"])

    with c3:
        st.warning(f"🥉 {top3.iloc[2]['Name']}")
        st.metric("Percentage", top3.iloc[2]["Percentage"])

    st.dataframe(df.sort_values("Rank").head(10))
    


# ================= ANALYTICS =================
elif menu == "Analytics":

    st.title("📊 Analytics")

    fig = px.bar(df.sort_values("Percentage", ascending=False),
                 x="Name", y="Percentage",
                 color="Grade")
    st.plotly_chart(fig, use_container_width=True)

    fig2 = px.scatter(df, x="CGPA", y="Percentage", color="Rank")
    st.plotly_chart(fig2, use_container_width=True)
    st.subheader("🎓 Grade Distribution")

    fig3 = px.pie(
    grade_count,
    names="Grade",
    values="Students",
    hole=0.4,
    title="Grade Distribution"
)

    st.plotly_chart(fig3, use_container_width=True)
# ================= NOTIFICATIONS =================
elif menu == "📢 Notifications":
    admin_notification_panel(db, df)
    admin_notification_delete_panel(db)
# ================= MODULE ANALYSIS =================
elif menu == "Module Analysis":

    st.title("📚 Module Analysis")

    marks_cols = [c for c in df.columns if "_Marks" in c]

    module_avg = df[marks_cols].mean().reset_index()
    module_avg.columns = ["Module", "Avg Score"]

    st.dataframe(module_avg)

    fig = px.bar(module_avg, x="Module", y="Avg Score")
    st.plotly_chart(fig, use_container_width=True)

# ================= LOW PERFORMERS =================
elif menu == "Low Performers":

    st.title("⚠️ Low Performers")

    low = df[df["Percentage"] < 60]
    st.dataframe(low[["Name", "Percentage", "CGPA", "Grade", "Suggestion"]])



# ================= REPORTS =================
elif menu == "Reports":

    st.title("📄 Reports")

    student = st.selectbox("Select Student", df["Name"], key="report_student")
    selected_row = df[df["Name"] == student].iloc[0]
    path = get_pdf_path(selected_row)

    if path and os.path.exists(path):
        with open(path, "rb") as f:
            st.download_button(
                "Download Gradecard PDF",
                f,
                file_name=os.path.basename(path),
                mime="application/pdf"
            )
    else:
        st.error(
            "Gradecard PDF not found for this student. "
            "Please regenerate gradecards."
        )

    if os.path.exists("output/final_rankings.xlsx"):
        with open("output/final_rankings.xlsx", "rb") as f:
            st.download_button(
                "Download Excel Report",
                f,
                file_name="final_rankings.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                )
            )

# ================= CERTIFICATES =================
elif menu == "Certificates":

    st.title("🏆 Certificates Center")

    df["Badge"] = df["Rank"].apply(
        lambda x:
        "🥇 Gold" if x == 1
        else "🥈 Silver" if x <= 3
        else "🥉 Bronze" if x <= 10
        else "🏅 Participant"
    )

    st.dataframe(
        df[
            [
                "Name",
                "Verification_ID",
                "Rank",
                "Badge",
                "Percentage",
                "CGPA"
            ]
        ],
        use_container_width=True
    )

    student = st.selectbox(
        "Select Student",
        df["Name"],
        key="certificate_student"
    )

    selected_row = df[df["Name"] == student].iloc[0]
    cert_path = get_certificate(selected_row)

    if cert_path and os.path.exists(cert_path):
        with open(cert_path, "rb") as f:
            st.download_button(
                "Download Certificate",
                f,
                file_name=os.path.basename(cert_path),
                mime="application/pdf"
            )
    else:
        st.warning(
            "Certificate not generated for this student."
        )

    st.subheader("📦 Bulk Download")

    if st.button("Generate Certificate ZIP"):
        zip_path = "output/all_certificates.zip"
        added_files = 0

        with zipfile.ZipFile(
            zip_path,
            "w",
            zipfile.ZIP_DEFLATED
        ) as zipf:

            for _, student_row in df.iterrows():
                cert = get_certificate(student_row)

                if cert and os.path.exists(cert):
                    zipf.write(
                        cert,
                        os.path.basename(cert)
                    )
                    added_files += 1

        if added_files == 0:
            st.error("No certificate files found.")
        else:
            with open(zip_path, "rb") as f:
                st.download_button(
                    f"Download ZIP ({added_files} certificates)",
                    f,
                    file_name="all_certificates.zip",
                    mime="application/zip"
                )

# ================= EMAIL CENTER =================
elif menu == "Email Center":

    st.title("📧 LIET Email Center")
    st.caption(
        "Files are matched using Name + Verification ID, for example "
        "Akash_Kumar_Yadav_LIET-MLAI-054_gradecard.pdf"
    )

    sender = st.text_input(
        "Sender Gmail",
        key="email_center_sender"
    )

    app_pass = st.text_input(
        "Gmail App Password",
        type="password",
        key="email_center_password"
    )

    if sender and app_pass:
        EMAILER = Emailer(sender, app_pass)

    # ================= SINGLE EMAIL =================
    st.subheader("📨 Send to One Student")

    student = st.selectbox(
        "Select Student",
        df["Name"],
        key="email_student"
    )

    selected_row = df[df["Name"] == student].iloc[0]

    send_gradecard_single = st.checkbox(
        "Attach Gradecard",
        value=True,
        key="single_gradecard"
    )

    send_certificate_single = st.checkbox(
        "Attach Certificate",
        value=True,
        key="single_certificate"
    )

    gradecard_path = (
        get_gradecard(selected_row)
        if send_gradecard_single
        else None
    )

    certificate_path = (
        get_certificate(selected_row)
        if send_certificate_single
        else None
    )

    with st.expander("Check matched files", expanded=False):
        st.write(
            "Gradecard:",
            gradecard_path or "Not found / not selected"
        )
        st.write(
            "Certificate:",
            certificate_path or "Not found / not selected"
        )

    if st.button(
        "📤 Send Selected Documents",
        use_container_width=True
    ):
        if not EMAILER:
            st.error("Please enter Gmail and App Password.")
        else:
            sent_count = 0

            if (
                send_gradecard_single
                and gradecard_path
                and os.path.exists(gradecard_path)
            ):
                if EMAILER.send_pdf(
                    selected_row["Email"],
                    gradecard_path,
                    selected_row["Name"]
                ):
                    sent_count += 1

            if (
                send_certificate_single
                and certificate_path
                and os.path.exists(certificate_path)
            ):
                if EMAILER.send_pdf(
                    selected_row["Email"],
                    certificate_path,
                    selected_row["Name"]
                ):
                    sent_count += 1

            if sent_count:
                st.success(
                    f"{sent_count} document email(s) sent successfully."
                )
            else:
                st.error(
                    "No email was sent. Check email credentials "
                    "and generated PDF files."
                )

    st.markdown("---")

    # ================= BULK EMAIL =================
    st.subheader("🚀 Bulk Email System")

    col1, col2 = st.columns(2)

    with col1:
        bulk_gradecard = st.checkbox(
            "Send Gradecards",
            value=True,
            key="bulk_gradecard"
        )

    with col2:
        bulk_certificate = st.checkbox(
            "Send Certificates",
            value=True,
            key="bulk_certificate"
        )

    st.warning(
        "Bulk sending can take time. Do not refresh the page "
        "while emails are being sent."
    )

    if st.button(
        "🚀 Send Bulk Emails",
        use_container_width=True
    ):
        if not EMAILER:
            st.error("Please enter Gmail and App Password.")

        elif not bulk_gradecard and not bulk_certificate:
            st.error("Select at least one document type.")

        else:
            success = 0
            failed = 0
            missing = 0

            progress = st.progress(0)
            status = st.empty()

            total_students = len(df)

            for position, (_, student_row) in enumerate(
                df.iterrows(),
                start=1
            ):
                student_name = student_row["Name"]
                student_email = str(
                    student_row["Email"]
                ).strip()

                student_sent = False
                student_missing = True

                status.write(
                    f"Processing {position}/{total_students}: "
                    f"{student_name}"
                )

                if bulk_gradecard:
                    path = get_gradecard(student_row)

                    if path and os.path.exists(path):
                        student_missing = False

                        if EMAILER.send_pdf(
                            student_email,
                            path,
                            student_name
                        ):
                            student_sent = True
                        else:
                            failed += 1

                if bulk_certificate:
                    path = get_certificate(student_row)

                    if path and os.path.exists(path):
                        student_missing = False

                        if EMAILER.send_pdf(
                            student_email,
                            path,
                            student_name
                        ):
                            student_sent = True
                        else:
                            failed += 1

                if student_missing:
                    missing += 1
                elif student_sent:
                    success += 1

                progress.progress(
                    position / total_students
                )

            status.empty()

            st.success(
                f"Students emailed successfully: {success}"
            )

            if failed:
                st.error(
                    f"Document email failures: {failed}"
                )

            if missing:
                st.warning(
                    f"Students with missing documents: {missing}"
                )

# ================= QR ATTENDANCE SYSTEM =================
elif menu == "Attendance":

    st.title("📌 QR Attendance System")

    tab1, tab2 = st.tabs(["Generate QR", "Live Attendance Records"])

    # ================= GENERATE QR =================
    with tab1:
        st.subheader("🎯 Generate Attendance QR")

        class_name = st.text_input("Class / Batch", "LIET Bootcamp Training")
        module = st.text_input("Module / Subject", "Python Training")

        max_scans = st.number_input(
            "Maximum Students Allowed",
            min_value=1,
            max_value=500,
            value=30
        )

        if st.button("Generate QR"):
            token = str(uuid.uuid4())

            db.collection("attendance_sessions").document(token).set({
                "token": token,
                "class_name": class_name,
                "module": module,
                "max_scans": int(max_scans),
                "scanned_count": 0,
                "is_active": True,
                "attendees": {},
                "created_at": firestore.SERVER_TIMESTAMP
            })

            qr_img = qrcode.make(token)

            buffer = BytesIO()
            qr_img.save(buffer, format="PNG")

            st.success("✅ QR Generated Successfully")
            st.image(buffer.getvalue(), width=300)

            st.write("QR Token:")
            st.code(token)

            st.download_button(
                "⬇ Download QR Image",
                buffer.getvalue(),
                file_name="attendance_qr.png",
                mime="image/png"
            )

    # ================= LIVE RECORDS =================
    with tab2:
        st.subheader("📊 QR Attendance Sessions")

        sessions = db.collection("attendance_sessions").stream()

        session_rows = []

        for s in sessions:
            d = s.to_dict()
            session_rows.append({
                "Token": d.get("token"),
                "Class": d.get("class_name"),
                "Module": d.get("module"),
                "Max Scans": d.get("max_scans"),
                "Scanned": d.get("scanned_count"),
                "Active": d.get("is_active")
            })

        if len(session_rows) == 0:
            st.warning("No QR attendance session found.")
        else:
            session_df = pd.DataFrame(session_rows)
            st.dataframe(session_df, use_container_width=True)

            selected_token = st.selectbox(
                "Select QR Session",
                session_df["Token"].tolist()
            )

            session_doc = db.collection("attendance_sessions").document(selected_token).get()

            if session_doc.exists:
                data = session_doc.to_dict()
                attendees = data.get("attendees", {})

                st.markdown("---")
                st.subheader("👨‍🎓 Present Students")

                attendance_rows = []

                for student_key, info in attendees.items():
                    attendance_rows.append({
                        "Name": info.get("name"),
                        "Email": info.get("email"),
                        "Rank": info.get("rank"),
                        "Percentage": info.get("percentage"),
                        "Punch Time": info.get("punch_time")
                    })

                if attendance_rows:
                    att_df = pd.DataFrame(attendance_rows)
                    st.dataframe(att_df, use_container_width=True)

                    csv_data = att_df.to_csv(index=False).encode("utf-8")

                    st.download_button(
                        "⬇ Download Attendance CSV",
                        csv_data,
                        file_name="qr_attendance_report.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No student has punched attendance yet.")

                c1, c2 ,c3 = st.columns(3)

                with c1:
                    if st.button("🔒 Close This QR"):
                        db.collection("attendance_sessions").document(selected_token).update({
                            "is_active": False
                        })
                        st.success("QR Closed Successfully")
                        st.rerun()

                with c2:
                    if st.button("🔓 Reopen This QR"):
                        db.collection("attendance_sessions").document(selected_token).update({
                            "is_active": True
                        })
                        st.success("QR Reopened Successfully")
                        st.rerun()
                with c3:
                    if st.button("🗑 Delete qr"):
                        db.collection("attendance_sessions").document(selected_token).delete()
                        st.success("QR deleted")
                        st.rerun()        
elif menu == "🧠 AI Academic Officer":

    st.title("🧠 LLM-Powered AI Academic Officer")
    st.caption(
        "Student performance analysis, risk diagnosis, mentoring plan, "
        "future prediction and an interactive academic assistant."
    )

    os.makedirs("output/future_gradecards", exist_ok=True)

    # =====================================================
    # GEMINI CONFIGURATION
    # =====================================================
    def get_gemini_api_key():
        try:
            secret_key = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            secret_key = ""

        return (
            secret_key
            or os.getenv("GEMINI_API_KEY", "")
        ).strip()


    def get_gemini_client(api_key):
        if genai is None:
            raise ImportError(
                "google-genai is not installed. "
                "Run: pip install -U google-genai"
            )

        if not api_key:
            raise ValueError(
                "Gemini API key not found. Add GEMINI_API_KEY "
                "to .streamlit/secrets.toml or environment variables."
            )

        return genai.Client(
            api_key=api_key
        )


    def call_gemini(prompt, api_key):
        client = get_gemini_client(api_key)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        result = getattr(
            response,
            "text",
            ""
        )

        if not result:
            raise RuntimeError(
                "Gemini returned an empty response."
            )

        return result.strip()


    # =====================================================
    # NUMERIC HELPERS
    # =====================================================
    def safe_number(value, default=0.0):
        try:
            if pd.isna(value):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default


    def predict_student(row):
        percentage = safe_number(
            row.get("Percentage", 0)
        )

        attendance = safe_number(
            row.get("Attendance_%", 0)
        )

        cgpa = safe_number(
            row.get("CGPA", 0)
        )

        marks_cols = [
            column
            for column in df.columns
            if column.endswith("_Marks")
        ]

        assessment_scores = [
            safe_number(row.get(column, 0))
            for column in marks_cols
        ]

        consistency_score = 0

        if assessment_scores:
            score_series = pd.Series(
                assessment_scores,
                dtype=float
            )

            score_mean = score_series.mean()
            score_std = score_series.std(ddof=0)

            if score_mean > 0:
                consistency_score = max(
                    0,
                    100 - (
                        score_std / score_mean
                    ) * 100
                )

        predicted_percentage = (
            percentage * 0.55
            + attendance * 0.15
            + (cgpa * 10) * 0.20
            + consistency_score * 0.10
        )

        predicted_percentage = max(
            0,
            min(100, predicted_percentage)
        )

        predicted_cgpa = round(
            predicted_percentage / 10,
            2
        )

        if predicted_percentage >= 90:
            predicted_grade = "A+"
        elif predicted_percentage >= 80:
            predicted_grade = "A"
        elif predicted_percentage >= 70:
            predicted_grade = "B+"
        elif predicted_percentage >= 60:
            predicted_grade = "B"
        elif predicted_percentage >= 50:
            predicted_grade = "C"
        elif predicted_percentage >= 40:
            predicted_grade = "D"
        else:
            predicted_grade = "F"

        predicted_rank = int(
            pd.to_numeric(
                df["Percentage"],
                errors="coerce"
            ).fillna(0).gt(
                predicted_percentage
            ).sum() + 1
        )

        placement_score = round(
            percentage * 0.40
            + attendance * 0.20
            + cgpa * 10 * 0.25
            + consistency_score * 0.15,
            2
        )

        risk_points = 0

        if percentage < 60:
            risk_points += 2

        if attendance < 75:
            risk_points += 2

        if cgpa < 6:
            risk_points += 2

        if consistency_score < 60:
            risk_points += 1

        if risk_points >= 5:
            risk = "High Risk"
        elif risk_points >= 2:
            risk = "Medium Risk"
        else:
            risk = "Low Risk"

        return {
            "Predicted Percentage": round(
                predicted_percentage,
                2
            ),
            "Predicted CGPA": predicted_cgpa,
            "Predicted Grade": predicted_grade,
            "Predicted Rank": predicted_rank,
            "Placement Score": placement_score,
            "Consistency Score": round(
                consistency_score,
                2
            ),
            "Risk Level": risk
        }


    # =====================================================
    # STUDENT CONTEXT FOR LLM
    # =====================================================
    def get_student_context(row, prediction):
        marks_cols = [
            column
            for column in df.columns
            if column.endswith("_Marks")
        ]

        assessment_data = []

        for column in marks_cols:
            score = safe_number(
                row.get(column, 0)
            )

            readable_name = (
                column
                .replace("_Marks", "")
                .replace("_", " ")
            )

            assessment_data.append(
                {
                    "assessment": readable_name,
                    "score": score
                }
            )

        assessment_data.sort(
            key=lambda item: item["score"]
        )

        weakest = assessment_data[:5]
        strongest = list(
            reversed(
                assessment_data[-5:]
            )
        )

        context = {
            "name": str(
                row.get("Name", "Student")
            ),
            "email": str(
                row.get("Email", "")
            ),
            "roll_number": str(
                row.get("Roll No", "")
            ),
            "rank": safe_number(
                row.get("Rank", 0)
            ),
            "percentage": safe_number(
                row.get("Percentage", 0)
            ),
            "cgpa": safe_number(
                row.get("CGPA", 0)
            ),
            "attendance": safe_number(
                row.get("Attendance_%", 0)
            ),
            "grade": str(
                row.get("Grade", "")
            ),
            "percentile": safe_number(
                row.get("Percentile", 0)
            ),
            "suggestion": str(
                row.get("Suggestion", "")
            ),
            "weakest_assessments": weakest,
            "strongest_assessments": strongest,
            "prediction": prediction
        }

        return context


    def build_mentor_prompt(
        row,
        prediction,
        quiz_summary=""
    ):
        student_context = get_student_context(
            row,
            prediction
        )

        return f"""
You are the AI Academic Officer and placement mentor for
Lloyd Institute of Engineering & Technology.

Analyze the student strictly using the supplied academic data.
Do not invent marks, attendance, rank, achievements, or personal facts.
The numeric future prediction is an estimate, not a guarantee.

STUDENT DATA:
{json.dumps(student_context, indent=2)}

QUIZ INTELLIGENCE:
{quiz_summary or "No additional quiz intelligence available."}

Create a professional mentoring report in clear markdown with these sections:

## Executive Summary
Give a concise and honest overview.

## Key Strengths
List 3 evidence-based strengths.

## Priority Improvement Areas
List the weakest areas and explain why they matter.

## Risk Diagnosis
Explain the risk level using percentage, CGPA, attendance and consistency.

## 7-Day Recovery or Growth Plan
Create a day-wise practical plan. Each day must include:
- Concept revision
- Coding or practical task
- Assessment practice
- Time recommendation

## 30-Day Academic Roadmap
Give weekly goals for four weeks.

## Placement Readiness
Evaluate technical preparation, consistency and readiness.
Do not claim that placement is guaranteed.

## Mentor Message
Finish with an encouraging but realistic message addressed to the student.

Use simple language. Be specific, practical and concise.
"""


    # =====================================================
    # FUTURE GRADECARD
    # =====================================================
    def create_future_gradecard(
        row,
        prediction,
        llm_recommendation=""
    ):
        safe_name = (
            str(row["Name"])
            .strip()
            .replace(" ", "_")
        )

        verification_id = str(
            row.get(
                "Verification_ID",
                ""
            )
        ).strip()

        file_suffix = (
            f"_{verification_id}"
            if verification_id
            else ""
        )

        pdf_path = (
            "output/future_gradecards/"
            f"{safe_name}{file_suffix}"
            "_future_gradecard.pdf"
        )

        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=A4,
            leftMargin=42,
            rightMargin=42,
            topMargin=38,
            bottomMargin=38
        )

        pdf_styles = getSampleStyleSheet()
        story = []

        story.append(
            Paragraph(
                "LIET AI FUTURE ACADEMIC REPORT",
                pdf_styles["Title"]
            )
        )

        story.append(
            Paragraph(
                "ML & Agentic AI Bootcamp",
                pdf_styles["Heading2"]
            )
        )

        story.append(
            Spacer(1, 14)
        )

        student_details = [
            ["Student", row.get("Name", "")],
            ["Email", row.get("Email", "")],
            ["Roll No", row.get("Roll No", "")],
            [
                "Verification ID",
                row.get(
                    "Verification_ID",
                    "N/A"
                )
            ]
        ]

        info_table = Table(
            student_details,
            colWidths=[125, 330]
        )

        info_table.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#EAF2F8")
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#607D8B")
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (0, -1),
                    "Helvetica-Bold"
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                )
            ])
        )

        story.append(info_table)
        story.append(Spacer(1, 14))

        performance_data = [
            ["Metric", "Current", "Predicted"],
            [
                "Percentage",
                f"{safe_number(row.get('Percentage', 0)):.2f}%",
                f"{prediction['Predicted Percentage']:.2f}%"
            ],
            [
                "CGPA",
                f"{safe_number(row.get('CGPA', 0)):.2f}",
                f"{prediction['Predicted CGPA']:.2f}"
            ],
            [
                "Rank",
                str(int(safe_number(row.get("Rank", 0)))),
                str(prediction["Predicted Rank"])
            ],
            [
                "Grade",
                str(row.get("Grade", "")),
                prediction["Predicted Grade"]
            ],
            [
                "Attendance",
                f"{safe_number(row.get('Attendance_%', 0)):.2f}%",
                "Maintain / improve"
            ],
            [
                "Consistency",
                "-",
                f"{prediction['Consistency Score']:.2f}%"
            ],
            [
                "Placement Score",
                "-",
                f"{prediction['Placement Score']:.2f}"
            ],
            [
                "Risk Level",
                "-",
                prediction["Risk Level"]
            ]
        ]

        performance_table = Table(
            performance_data,
            colWidths=[150, 150, 150]
        )

        performance_table.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#003366")
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.6,
                    colors.HexColor("#455A64")
                ),
                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER"
                ),
                (
                    "BACKGROUND",
                    (0, 1),
                    (-1, -1),
                    colors.HexColor("#F4F8FC")
                )
            ])
        )

        story.append(performance_table)
        story.append(Spacer(1, 18))

        story.append(
            Paragraph(
                "AI Academic Officer Recommendation",
                pdf_styles["Heading2"]
            )
        )

        recommendation = (
            llm_recommendation
            or (
                f"{row.get('Name', 'The student')} is currently "
                f"at {prediction['Risk Level']} and should focus on "
                "attendance, weak assessments and consistent practice."
            )
        )

        # Basic markdown cleanup for ReportLab
        recommendation = (
            recommendation
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br/>")
        )

        story.append(
            Paragraph(
                recommendation,
                pdf_styles["BodyText"]
            )
        )

        story.append(Spacer(1, 14))

        story.append(
            Paragraph(
                "<i>This is an AI-assisted predictive report. "
                "Predictions are estimates based on available academic data.</i>",
                pdf_styles["Normal"]
            )
        )

        doc.build(story)

        return pdf_path


    # =====================================================
    # QUIZ INTELLIGENCE
    # =====================================================
    try:
        quiz_ai = get_admin_quiz_summary(db)
        quiz_summary_text = quiz_ai.get(
            "summary_text",
            ""
        )
    except Exception:
        quiz_ai = {
            "summary_text": "",
            "weak_topics_df": pd.DataFrame(),
            "weak_students_df": pd.DataFrame()
        }
        quiz_summary_text = ""

    with st.expander(
        "📚 Overall Quiz Intelligence",
        expanded=False
    ):
        if quiz_summary_text:
            st.info(quiz_summary_text)
        else:
            st.warning(
                "Quiz intelligence is not available yet."
            )

        weak_topics_df = quiz_ai.get(
            "weak_topics_df",
            pd.DataFrame()
        )

        weak_students_df = quiz_ai.get(
            "weak_students_df",
            pd.DataFrame()
        )

        if not weak_topics_df.empty:
            st.subheader("Weak Topics")
            st.dataframe(
                weak_topics_df,
                use_container_width=True
            )

        if not weak_students_df.empty:
            st.subheader(
                "Students Needing Mentoring"
            )

            st.dataframe(
                weak_students_df,
                use_container_width=True
            )


    # =====================================================
    # STUDENT SELECTION
    # =====================================================
    student_name = st.selectbox(
        "Select Student",
        df["Name"].tolist(),
        key="ai_officer_student"
    )

    selected_row = (
        df[df["Name"] == student_name]
        .iloc[0]
    )

    prediction = predict_student(
        selected_row
    )

    st.subheader("📊 Current Academic Summary")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Current Rank",
        int(
            safe_number(
                selected_row.get("Rank", 0)
            )
        )
    )

    c2.metric(
        "Percentage",
        f"{safe_number(selected_row.get('Percentage', 0)):.2f}%"
    )

    c3.metric(
        "CGPA",
        f"{safe_number(selected_row.get('CGPA', 0)):.2f}"
    )

    c4.metric(
        "Attendance",
        f"{safe_number(selected_row.get('Attendance_%', 0)):.2f}%"
    )

    st.subheader("🔮 Data-Based Prediction")

    p1, p2, p3, p4 = st.columns(4)

    p1.metric(
        "Predicted %",
        f"{prediction['Predicted Percentage']:.2f}%"
    )

    p2.metric(
        "Predicted CGPA",
        prediction["Predicted CGPA"]
    )

    p3.metric(
        "Predicted Rank",
        prediction["Predicted Rank"]
    )

    p4.metric(
        "Predicted Grade",
        prediction["Predicted Grade"]
    )

    d1, d2, d3 = st.columns(3)

    d1.metric(
        "Placement Score",
        prediction["Placement Score"]
    )

    d2.metric(
        "Consistency",
        f"{prediction['Consistency Score']:.2f}%"
    )

    risk = prediction["Risk Level"]

    if risk == "High Risk":
        d3.error(f"Risk Level: {risk}")
    elif risk == "Medium Risk":
        d3.warning(f"Risk Level: {risk}")
    else:
        d3.success(f"Risk Level: {risk}")

    st.caption(
        "Predictions are estimates based on current percentage, "
        "CGPA, attendance and assessment consistency."
    )


    # =====================================================
    # LLM MENTORING REPORT
    # =====================================================
    st.divider()
    st.subheader("✨ Gemini Academic Mentoring Report")

    api_key = get_gemini_api_key()

    if not api_key:
        st.warning(
            "Gemini API key is not configured. Add this to "
            ".streamlit/secrets.toml:\n\n"
            'GEMINI_API_KEY = "your_api_key"'
        )

    report_key = (
        "llm_report_"
        + str(
            selected_row.get(
                "Verification_ID",
                student_name
            )
        )
    )

    if st.button(
        "🧠 Generate Detailed AI Mentoring Report",
        use_container_width=True,
        disabled=not bool(api_key)
    ):
        try:
            with st.spinner(
                "Gemini is analyzing academic performance..."
            ):
                prompt = build_mentor_prompt(
                    selected_row,
                    prediction,
                    quiz_summary_text
                )

                st.session_state[
                    report_key
                ] = call_gemini(
                    prompt,
                    api_key
                )

            st.success(
                "AI mentoring report generated."
            )

        except Exception as error:
            st.error(
                f"Gemini analysis failed: {error}"
            )

    llm_report = st.session_state.get(
        report_key,
        ""
    )

    if llm_report:
        st.markdown(llm_report)

        st.download_button(
            "⬇ Download AI Mentoring Report",
            data=llm_report,
            file_name=(
                f"{str(student_name).replace(' ', '_')}"
                "_AI_mentoring_report.md"
            ),
            mime="text/markdown",
            use_container_width=True
        )


    # =====================================================
    # INTERACTIVE LLM MENTOR CHAT
    # =====================================================
    st.divider()
    st.subheader("💬 Ask the AI Academic Mentor")

    chat_key = (
        "academic_chat_"
        + str(
            selected_row.get(
                "Verification_ID",
                student_name
            )
        )
    )

    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    for chat_item in st.session_state[chat_key]:
        with st.chat_message(
            chat_item["role"]
        ):
            st.markdown(
                chat_item["content"]
            )

    user_question = st.chat_input(
        "Ask about weak areas, study plan, placement readiness, attendance or assessments..."
    )

    if user_question:
        st.session_state[chat_key].append(
            {
                "role": "user",
                "content": user_question
            }
        )

        with st.chat_message("user"):
            st.markdown(user_question)

        if not api_key:
            mentor_answer = (
                "Gemini API key is not configured. "
                "Please add GEMINI_API_KEY to Streamlit secrets."
            )
        else:
            try:
                student_context = get_student_context(
                    selected_row,
                    prediction
                )

                conversation = "\n\n".join(
                    (
                        f"{item['role'].upper()}: "
                        f"{item['content']}"
                    )
                    for item in st.session_state[
                        chat_key
                    ][-8:]
                )

                chat_prompt = f"""
You are an academic mentor for LIET.

Use only this student data:
{json.dumps(student_context, indent=2)}

Conversation:
{conversation}

Answer the latest student/admin question clearly.
Give practical steps and use the available academic evidence.
Do not invent facts and do not guarantee placement or future results.
Keep the response under 350 words.
"""

                with st.spinner(
                    "AI mentor is thinking..."
                ):
                    mentor_answer = call_gemini(
                        chat_prompt,
                        api_key
                    )

            except Exception as error:
                mentor_answer = (
                    f"AI mentor error: {error}"
                )

        st.session_state[chat_key].append(
            {
                "role": "assistant",
                "content": mentor_answer
            }
        )

        with st.chat_message("assistant"):
            st.markdown(mentor_answer)


    # =====================================================
    # REPORT GENERATION AND EMAIL
    # =====================================================
    st.divider()
    st.subheader("📄 Future Academic Report")

    action_col1, action_col2 = st.columns(2)

    with action_col1:
        if st.button(
            "📄 Generate Future Academic PDF",
            use_container_width=True
        ):
            pdf_path = create_future_gradecard(
                selected_row,
                prediction,
                llm_report
            )

            st.success(
                "Future academic PDF generated."
            )

            with open(pdf_path, "rb") as pdf_file:
                st.download_button(
                    "⬇ Download Future Academic PDF",
                    data=pdf_file.read(),
                    file_name=os.path.basename(
                        pdf_path
                    ),
                    mime="application/pdf",
                    use_container_width=True
                )

    with action_col2:
        sender = st.text_input(
            "Sender Gmail",
            key="ai_sender_email"
        )

        app_pass = st.text_input(
            "Gmail App Password",
            type="password",
            key="ai_sender_password"
        )

        if st.button(
            "📧 Generate & Email AI Report",
            use_container_width=True
        ):
            if not sender or not app_pass:
                st.error(
                    "Enter Gmail and App Password."
                )
            else:
                pdf_path = create_future_gradecard(
                    selected_row,
                    prediction,
                    llm_report
                )

                emailer = Emailer(
                    sender,
                    app_pass
                )

                sent = emailer.send_pdf(
                    selected_row["Email"],
                    pdf_path,
                    selected_row["Name"],
                    "Future Gradecard"
                )

                if sent:
                    st.success(
                        "AI academic report emailed successfully."
                    )
                else:
                    st.error(
                        "Email sending failed."
                    )


elif menu == "📚 Quiz Management":
    quiz_admin_panel(db)
elif menu == "💬 Chat Support":
    admin_chat_panel(db)