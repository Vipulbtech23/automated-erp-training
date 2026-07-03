import streamlit as st
import pandas as pd
import plotly.express as px
import os
import sys
import zipfile
import datetime
import uuid
import qrcode
from io import BytesIO
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore
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

    st.title("🔐 LIET ERP Admin Login")

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

# ================= AI INSIGHT =================
def ai_insight(row):
    if row["Rank"] <= 5:
        return "🏆 Outstanding performer. Ready for advanced projects."
    elif row["Percentage"] >= 75:
        return "🔥 Strong performance. Focus on projects."
    elif row["Percentage"] >= 60:
        return "👍 Good progress. Improve consistency."
    return "⚠️ Needs revision and practice."

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
        "Leaderboard",
        "Analytics",
        "Module Analysis",
        "Low Performers",
        "Student Search",
        "Reports",
        "Certificates",
        "Email Center",
        "Top Performers",
        "AI Insights",
        "Placement Readiness",
        "Download Center",
        "Attendance",
        "🤖 Automation Agent",
"🔮 Prediction Model"
    ]
)

# ================= HOME =================
if menu == "Home":

    st.title("🏫 LIET Training ERP Dashboard")

    # METRICS
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Students", len(df))
    c2.metric("Avg %", round(df["Percentage"].mean(), 2))
    c3.metric("Top Score", df["Total"].max())
    c4.metric("Top CGPA", df["CGPA"].max())

    # ALL STUDENTS
    st.subheader("👨‍🎓 All Students List")
    if st.button("🚀 Run Complete Pipeline"):

     os.system("python scripts/merge_quizzes.py")
     os.system("python scripts/calculate_scores.py")
     os.system("python scripts/generate_scorecard.py")
     os.system("python scripts/certificate_generator.py")

    st.success(
        "All Reports Generated Successfully"
    )
    st.dataframe(df.sort_values("Rank"))
    st.dataframe(
    df[
        ["Name",
         "Rank",
         "Badge",
         "Grade"]
    ]
)

    # PIE CHART (PERCENTILE DISTRIBUTION)
    st.subheader("📊 Performance Distribution")

    bins = [0, 40, 60, 75, 90, 100]
    labels = ["0-40", "40-60", "60-75", "75-90", "90-100"]

    df["Percentile Range"] = pd.cut(df["Percentage"], bins=bins, labels=labels, include_lowest=True)

    pie_data = df["Percentile Range"].value_counts().reset_index()
    pie_data.columns = ["Range", "Students"]

    fig = px.pie(
        pie_data,
        names="Range",
        values="Students",
        hole=0.4
    )

    st.plotly_chart(fig, use_container_width=True)
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
    

# ================= LEADERBOARD =================
elif menu == "Leaderboard":

    st.title("🏆 Top 10 Performers")

    top10 = df.sort_values("Rank").head(10)

    st.success(f"🥇 {top10.iloc[0]['Name']}")
    st.info(f"🥈 {top10.iloc[1]['Name']}")
    st.warning(f"🥉 {top10.iloc[2]['Name']}")

    st.dataframe(top10)
elif menu == "AI Insights":

    st.title("🤖 AI Performance Insights")

    insights = []

    for _, row in df.iterrows():

        insights.append({
            "Name": row["Name"],
            "Insight": ai_insight(row)
        })

    st.dataframe(pd.DataFrame(insights))
elif menu == "Placement Readiness":

    st.title("🎯 Placement Readiness Score")

    df["Placement Score"] = (
        (df["CGPA"] * 4) +
        (df["Percentage"] * 0.4) +
        (df["Attendance_%"] * 0.2)
    )

    st.dataframe(
        df[
            ["Name",
             "Placement Score",
             "CGPA",
             "Percentage",
             "Rank"]
        ].sort_values(
            "Placement Score",
            ascending=False
        )
    )
elif menu == "Download Center":

    st.title("📥 Download Center")

    zip_path = "output/all_gradecards.zip"

    if st.button("Create Gradecard ZIP"):

        with zipfile.ZipFile(zip_path, "w") as zipf:

            for _, row in df.iterrows():

                pdf = get_gradecard(row["Name"])

                if os.path.exists(pdf):
                    zipf.write(
                        pdf,
                        os.path.basename(pdf)
                    )

        with open(zip_path, "rb") as f:

            st.download_button(
                "Download All Gradecards",
                f,
                file_name="all_gradecards.zip"
            )   
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

# ================= STUDENT SEARCH =================
elif menu == "Student Search":

    st.title("🔍 Search Student")

    name = st.text_input("Enter Name")

    if name:
        res = df[df["Name"].str.contains(name, case=False)]
        st.dataframe(res)

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

                c1, c2 = st.columns(2)

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
elif menu == "🤖 Automation Agent":

    from scripts.automation_agent import run_agent

    st.title("🤖 LIET Automation Agent")

    st.info("Ye agent quizzes merge karega, scores calculate karega, gradecards aur certificates generate karega.")

    if st.button("🚀 Run Complete Automation Agent"):

        with st.spinner("Automation running... please wait"):
            results = run_agent()

        for script, success, output in results:
            if success:
                st.success(f"✅ {script} completed")
            else:
                st.error(f"❌ {script} failed")
                st.code(output)

        st.success("🎉 Automation Agent completed")

    if os.path.exists("output/agent_log.txt"):
        with open("output/agent_log.txt", "r", encoding="utf-8") as f:
            st.text_area("Agent Logs", f.read(), height=300)


elif menu == "🔮 Prediction Model":

    from scripts.automation_agent import prediction_model

    st.title("🔮 Student Future Performance Prediction")

    if st.button("Run Prediction Model"):

        pred_df = prediction_model()

        if pred_df is not None:
            st.success("✅ Prediction generated successfully")
            st.dataframe(pred_df, use_container_width=True)

            with open("output/predictions.xlsx", "rb") as f:
                st.download_button(
                    "Download Predictions Excel",
                    f,
                    file_name="predictions.xlsx"
                )
        else:
            st.error("final_rankings.xlsx not found. Run automation first.")                        

