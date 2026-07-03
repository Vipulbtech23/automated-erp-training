"""
========================================================
🏆 PROFESSIONAL CERTIFICATE GENERATOR - LIET ERP SYSTEM
========================================================

This script generates BEAUTIFUL, PROFESSIONAL certificates
for all students based on final_rankings.xlsx data.

Features:
--------------------------------------------------------
✔ College Logo Integration
✔ Student Name Styling
✔ Rank / CGPA / Percentage Display
✔ Training Period Mention
✔ QR Code Verification System
✔ Signature of Training Coordinator
✔ Unique Certificate ID
✔ Clean Border Layout
✔ Auto PDF Generation for all students

Author: LIET ERP System
Date: 2026
========================================================
"""

# ================= IMPORT LIBRARIES =================
import pandas as pd
import os
import qrcode
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
def get_badge(rank):
    """
    This function assigns certificate level
    based on student rank.
    """

    if rank == 1:
        return "GOLD"
    elif rank <= 3:
        return "SILVER"
    elif rank <= 10:
        return "BRONZE"
    else:
        return "PARTICIPATION"

print("🚀 Starting Professional Certificate Generator System...")

# ================= LOAD STUDENT DATA =================
df = pd.read_excel("output/final_rankings.xlsx")

# Clean column names (important for safety)
df.columns = df.columns.str.strip()

# ================= ASSET PATHS =================
LOGO_PATH = "assets/mllogo.png"
SIGN_PATH = "assets/signature.png"

# Create output folder if not exists
os.makedirs("output/certificates", exist_ok=True)
os.makedirs("output/qr1", exist_ok=True)

# =====================================================
# 📌 QR CODE GENERATOR FUNCTION
# =====================================================
def generate_qr(data, filename):
    """
    This function generates a QR code image
    which stores student verification data.
    """

    qr_path = f"output/qr1/{filename}_qr.png"

    qr = qrcode.make(data)
    qr.save(qr_path)

    return qr_path


# =====================================================
# 📌 CERTIFICATE CREATION FUNCTION
# =====================================================
def create_certificate(row):
    """
    This function creates a single professional certificate
    for each student using ReportLab canvas.
    """

    # ================= STUDENT DATA =================
    name = str(row["Name"])
    safe_name = name.replace(" ", "_")

    rank = row["Rank"]
    percentage = row["Percentage"]
    cgpa = row["CGPA"]
    badge = get_badge(rank)
    email = row.get("Email", "Not Available")

    # Unique certificate ID
    cert_id = f"LIET-2026-{safe_name[:4].upper()}-{rank}"

    # Output PDF path
    pdf_path = f"output/certificates/{safe_name}_certificate.pdf"

    # Create canvas (A4 landscape style feel)
    c = canvas.Canvas(pdf_path, pagesize=(900, 600))


    # =====================================================
    # 🟦 BORDER DESIGN (Outer Frame)
    # =====================================================
    c.setLineWidth(2)
    c.rect(25, 25, 850, 550)


    # =====================================================
    # 🏫 COLLEGE LOGO (TOP CENTER)
    # =====================================================
    if os.path.exists(LOGO_PATH):
        c.drawImage(LOGO_PATH, 400, 500, width=100, height=70, mask='auto')


    # =====================================================
    # 🏆 MAIN TITLE
    # =====================================================
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(450, 460, "CERTIFICATE OF COMPLETION")


    # =====================================================
    # 🏫 SUB TITLE (COLLEGE NAME)
    # =====================================================
    c.setFont("Helvetica", 14)
    c.drawCentredString(
        450,
        430,
        "LLOYD INSTITUTE OF ENGINEERING & TECHNOLOGY"
    )


    # =====================================================
    # 🎓 STUDENT NAME SECTION (MOST IMPORTANT)
    # =====================================================
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(450, 380, name)


    # =====================================================
    # 📘 TRAINING DESCRIPTION
    # =====================================================
    c.setFont("Helvetica", 12)
    c.drawCentredString(
        450,
        350,
        "has successfully completed the AI & Machine Learning Training Program"
    )


    # =====================================================
    # 📅 TRAINING PERIOD (IMPORTANT REQUIREMENT)
    # =====================================================
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(
        450,
        320,
        "Training Period: 15 June 2026 to 15 July 2026"
    )


    # =====================================================
    # 📊 PERFORMANCE DETAILS
    # =====================================================
    c.setFont("Helvetica", 12)
    c.drawCentredString(
        450,
        290,
        f"Rank: {rank}   |  Badge: {badge}| Percentage: {percentage}%   |   CGPA: {cgpa}"
    )


    # =====================================================
    # 🆔 CERTIFICATE ID
    # =====================================================
    c.drawCentredString(
        450,
        260,
        f"Certificate ID: {cert_id}"
    )

    # ================= BADGE DISPLAY =================
    c.setFont("Helvetica-Bold", 18)

    if badge == "GOLD":
        c.setFillColorRGB(1, 0.84, 0)  # gold color
    elif badge == "SILVER":
        c.setFillColorRGB(0.75, 0.75, 0.75)  # silver color
    elif badge == "BRONZE":
        c.setFillColorRGB(0.8, 0.5, 0.2)  # bronze color
    else:
        c.setFillColorRGB(0.2, 0.6, 1)  # blue

    c.drawCentredString(450, 230, f"🏅 {badge} CERTIFICATE")
    # =====================================================
    # 📱 QR CODE GENERATION (RIGHT SIDE)
    # =====================================================
    qr_data = f"""
    NAME: {name}
    RANK: {rank}
    BADGE: {badge}
    CGPA: {cgpa}
    CERTIFICATE ID: {cert_id}
    ISSUED: {datetime.now().strftime('%d-%m-%Y')}
    """

    qr_path = generate_qr(qr_data, safe_name)

    if os.path.exists(qr_path):
        c.drawImage(qr_path, 750, 80, width=120, height=120)


    # =====================================================
    # ✍️ SIGNATURE SECTION (BOTTOM LEFT)
    # =====================================================
    if os.path.exists(SIGN_PATH):
        c.drawImage(SIGN_PATH, 120, 90, width=140, height=70, mask='auto')

    c.setFont("Helvetica", 10)
    c.drawString(120, 75, "Training Coordinator Signature")


    # =====================================================
    # 📌 FOOTER MESSAGE
    # =====================================================
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(
        450,
        40,
        "Keep Learning • Keep Practicing • Keep Growing 🚀"
    )


    # =====================================================
    # SAVE CERTIFICATE
    # =====================================================
    c.save()

    print(f"✅ Certificate Generated: {pdf_path}")


# =====================================================
# 🚀 LOOP ALL STUDENTS AND GENERATE CERTIFICATES
# =====================================================
for _, row in df.iterrows():
    create_certificate(row)

print("🏁 ALL PROFESSIONAL CERTIFICATES GENERATED SUCCESSFULLY")