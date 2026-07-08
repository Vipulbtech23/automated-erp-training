try:
    import streamlit as st
except ImportError:
    print("streamlit not installed. Run: pip install streamlit")
    raise

import pandas as pd
from quiz.gamification import admin_gamification_leaderboard
import plotly.express as px
import os
import sys
import zipfile
import datetime
import uuid
import qrcode
import subprocess
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


ATTENDANCE_FILE = "output/attendance.csv"
# ================= ROOT =================
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(ROOT_DIR)

from scripts.send_email import Emailer

# ================= CONFIG =================
st.set_page_config(page_title="LIET ERP", layout="wide")
# ================= FIREBASE =================
def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(BASE_DIR / "firebase_key.json")
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firebase()
# ================= LOGIN =================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "liet123"

if not st.session_state.logged_in:

    st.title("🔐 LIET ERP Admin login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            st.session_state.logged_in = True
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
# ================= GRADE DISTRIBUTION DATA =================

grade_count = (
    df["Grade"]
    .value_counts()
    .reset_index()
)

grade_count.columns = ["Grade", "Students"]

# ================= PATH FUNCTIONS =================
def get_pdf_path(name):
    safe = name.strip().replace(" ", "_")
    return os.path.join("output", "gradecards", f"{safe}_gradecard.pdf")

def get_certificate(name):
    safe = name.strip().replace(" ", "_")
    return f"output/certificates/{safe}_certificate.pdf"

def get_gradecard(name):
    safe = name.strip().replace(" ", "_")
    return f"output/gradecards/{safe}_gradecard.pdf"


# ================= EMAILER =================
EMAILER = None

# ================= ROLE (NO LOGIN) =================
st.sidebar.success("👤 Admin")

if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
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
        
        "Attendance",
       "🧠 AI Academic Officer"
    ]
)
if menu == "Home":

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

    student = st.selectbox("Select Student", df["Name"])
    path = get_pdf_path(student)

    if os.path.exists(path):
        with open(path, "rb") as f:
            st.download_button("Download PDF", f, file_name=os.path.basename(path))
    else:
        st.error("PDF not found")

    with open("output/final_rankings.xlsx", "rb") as f:
        st.download_button("Download Excel", f, file_name="report.xlsx")

# ================= CERTIFICATES =================
elif menu == "Certificates":

    st.title("🏆 Certificates Center")

    df["Badge"] = df["Rank"].apply(lambda x: "🥇 Gold" if x == 1 else "🥈 Silver" if x <= 3 else "🥉 Bronze" if x <= 10 else "🏅 Participant")

    st.dataframe(df[["Name", "Rank", "Badge", "Percentage", "CGPA"]])

    student = st.selectbox("Select Student", df["Name"])
    cert_path = get_certificate(student)

    if os.path.exists(cert_path):
        with open(cert_path, "rb") as f:
            st.download_button("Download Certificate", f, file_name=os.path.basename(cert_path))
    else:
        st.warning("Certificate not generated yet")

    # ZIP DOWNLOAD
    st.subheader("📦 Bulk Download")

    if st.button("Generate ZIP"):
        zip_path = "certificates_all.zip"

        with zipfile.ZipFile(zip_path, "w") as zipf:
            for _, row in df.iterrows():
                cert = get_certificate(row["Name"])
                if os.path.exists(cert):
                    zipf.write(cert, os.path.basename(cert))

        with open(zip_path, "rb") as f:
            st.download_button("Download ZIP", f, file_name="all_certificates.zip")

# ================= EMAIL CENTER =================
elif menu == "Email Center":

    st.title("📧 Email System")

    sender = st.text_input("Gmail")
    app_pass = st.text_input("App Password", type="password")

    if sender and app_pass:
        EMAILER = Emailer(sender, app_pass)

    student = st.selectbox("Student", df["Name"])
    email_type = st.radio("Document Type", ["Gradecard", "Certificate"])

    # ================= SINGLE EMAIL =================
    if st.button("Send Email") and EMAILER:

        row = df[df["Name"] == student].iloc[0]

        pdf_path = get_gradecard(student) if email_type == "Gradecard" else get_certificate(student)

        if os.path.exists(pdf_path):
            EMAILER.send_pdf(row["Email"], pdf_path, student)
            st.success("Email sent successfully")
        else:
            st.error("File not found")

    st.markdown("---")

    # ================= BULK EMAIL (ADDED) =================
    st.subheader("🚀 Bulk Email System")

    bulk_type = st.selectbox("Bulk Document Type", ["Gradecard", "Certificate"])

    if st.button("Send Bulk Emails") and EMAILER:

        success, failed = 0, 0

        for _, row in df.iterrows():

            try:
                pdf_path = (
                    get_gradecard(row["Name"])
                    if bulk_type == "Gradecard"
                    else get_certificate(row["Name"])
                )

                if pd.notna(row["Email"]) and os.path.exists(pdf_path):

                    EMAILER.send_pdf(
                        row["Email"],
                        pdf_path,
                        row["Name"]
                    )
                    success += 1
                else:
                    failed += 1

            except:
                failed += 1

        st.success(f"✅ Success: {success}")
        st.error(f"❌ Failed: {failed}")
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

    st.title("🧠 AI Academic Officer")
    st.info("Predict future performance, analyze quiz intelligence, generate future gradecards, and email reports.")

    os.makedirs("output/future_gradecards", exist_ok=True)

    quiz_ai = get_admin_quiz_summary(db)

    st.subheader("📚 Quiz Intelligence")

    st.text_area(
        "AI Quiz Summary",
        quiz_ai["summary_text"],
        height=180
    )

    if not quiz_ai["weak_topics_df"].empty:
        st.subheader("⚠️ Weak Topics")
        st.dataframe(quiz_ai["weak_topics_df"], use_container_width=True)

    if not quiz_ai["weak_students_df"].empty:
        st.subheader("🚨 Students Needing Mentoring")
        st.dataframe(quiz_ai["weak_students_df"], use_container_width=True)

    st.divider()

    def predict_student(row):
        percentage = float(row["Percentage"])
        attendance = float(row["Attendance_%"])
        cgpa = float(row["CGPA"])

        predicted_percentage = (
            percentage * 0.65 +
            attendance * 0.15 +
            (cgpa * 10) * 0.20
        )

        predicted_cgpa = round(predicted_percentage / 10, 2)

        if predicted_percentage >= 90:
            predicted_grade = "A+"
        elif predicted_percentage >= 80:
            predicted_grade = "A"
        elif predicted_percentage >= 70:
            predicted_grade = "B"
        elif predicted_percentage >= 60:
            predicted_grade = "C"
        else:
            predicted_grade = "Needs Improvement"

        placement_score = round(
            (cgpa * 4) +
            (percentage * 0.4) +
            (attendance * 0.2),
            2
        )

        predicted_rank = int(df["Percentage"].gt(predicted_percentage).sum() + 1)

        risk = "Low Risk"
        if attendance < 75 or predicted_percentage < 60:
            risk = "High Risk"
        elif predicted_percentage < 70:
            risk = "Medium Risk"

        return {
            "Predicted Percentage": round(predicted_percentage, 2),
            "Predicted CGPA": predicted_cgpa,
            "Predicted Grade": predicted_grade,
            "Predicted Rank": predicted_rank,
            "Placement Score": placement_score,
            "Risk Level": risk
        }

    def create_future_gradecard(row, prediction):
        safe_name = row["Name"].strip().replace(" ", "_")
        pdf_path = f"output/future_gradecards/{safe_name}_future_gradecard.pdf"

        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("LIET AI FUTURE GRADECARD", styles["Title"]))
        story.append(Spacer(1, 15))

        story.append(Paragraph(f"<b>Name:</b> {row['Name']}", styles["Normal"]))
        story.append(Paragraph(f"<b>Email:</b> {row['Email']}", styles["Normal"]))
        story.append(Spacer(1, 12))

        data = [
            ["Metric", "Current", "Predicted"],
            ["Percentage", f"{row['Percentage']}%", f"{prediction['Predicted Percentage']}%"],
            ["CGPA", row["CGPA"], prediction["Predicted CGPA"]],
            ["Rank", row["Rank"], prediction["Predicted Rank"]],
            ["Grade", row["Grade"], prediction["Predicted Grade"]],
            ["Attendance", f"{row['Attendance_%']}%", "-"],
            ["Placement Score", "-", prediction["Placement Score"]],
            ["Risk Level", "-", prediction["Risk Level"]],
        ]

        table = Table(data, colWidths=[150, 150, 150])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f2f6ff")),
        ]))

        story.append(table)
        story.append(Spacer(1, 20))

        recommendation = f"""
        Based on current academic summary, {row['Name']} is expected to achieve 
        {prediction['Predicted Grade']} grade with approximately 
        {prediction['Predicted Percentage']}%. 
        Current risk level is {prediction['Risk Level']}. 
        Student should focus on weak modules, attendance improvement, and consistent quiz performance.
        """

        story.append(Paragraph("<b>AI Academic Officer Recommendation:</b>", styles["Heading2"]))
        story.append(Paragraph(recommendation, styles["Normal"]))
        story.append(Spacer(1, 15))
        story.append(Paragraph("<i>This is an AI-generated predictive academic report.</i>", styles["Normal"]))

        doc.build(story)
        return pdf_path

    student_name = st.selectbox("Select Student", df["Name"])
    selected_row = df[df["Name"] == student_name].iloc[0]
    prediction = predict_student(selected_row)

    st.subheader("📊 Current Academic Summary")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Rank", selected_row["Rank"])
    c2.metric("Percentage", f"{selected_row['Percentage']}%")
    c3.metric("CGPA", selected_row["CGPA"])
    c4.metric("Attendance", f"{selected_row['Attendance_%']}%")

    st.subheader("🔮 Future Prediction")

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Predicted %", f"{prediction['Predicted Percentage']}%")
    p2.metric("Predicted CGPA", prediction["Predicted CGPA"])
    p3.metric("Predicted Rank", prediction["Predicted Rank"])
    p4.metric("Predicted Grade", prediction["Predicted Grade"])

    st.info(f"🎯 Placement Score: {prediction['Placement Score']}")
    st.warning(f"⚠ Risk Level: {prediction['Risk Level']}")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📄 Generate Future Gradecard"):
            pdf_path = create_future_gradecard(selected_row, prediction)
            st.success("Future gradecard generated successfully.")

            with open(pdf_path, "rb") as f:
                st.download_button(
                    "⬇ Download Future Gradecard",
                    f,
                    file_name=os.path.basename(pdf_path)
                )

    with col2:
        sender = st.text_input("Sender Gmail")
        app_pass = st.text_input("Gmail App Password", type="password")

        if st.button("📧 Generate & Email Future Gradecard"):

            if not sender or not app_pass:
                st.error("Please enter Gmail and App Password.")
            else:
                pdf_path = create_future_gradecard(selected_row, prediction)

                emailer = Emailer(sender, app_pass)
                sent = emailer.send_pdf(
                    selected_row["Email"],
                    pdf_path,
                    selected_row["Name"],
                    "Future Gradecard"
                )

                if sent:
                    st.success("Future gradecard emailed successfully.")
                else:
                    st.error("Email failed.")


elif menu == "📚 Quiz Management":
    quiz_admin_panel(db)
         