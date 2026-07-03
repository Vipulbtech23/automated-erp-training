import pandas as pd
import os
import qrcode
from datetime import datetime

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image
)

from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart

print("🚀 FINAL ADVANCED GRADECARD SYSTEM STARTED")

# =========================
# LOAD DATA
# =========================
df = pd.read_excel("output/final_rankings.xlsx")
df.columns = df.columns.str.strip()

styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    name="TitleCenter",
    parent=styles["Title"],
    alignment=1,
    fontSize=16,
    spaceAfter=4
)

subtitle_style = ParagraphStyle(
    name="SubtitleCenter",
    parent=styles["Normal"],
    alignment=1,
    fontSize=11,
    spaceAfter=6
)

normal = styles["Normal"]

LOGO_PATH = "assets/mllogo.png"
SIGN_PATH = "assets/signature.png"
DEAN_SIGN_PATH = "assets/Dean_Signature.png"
os.makedirs("output/gradecards", exist_ok=True)
os.makedirs("output/qrcodes", exist_ok=True)


# =========================
# CGPA FUNCTION
# =========================
def calculate_cgpa(percent):
    return round((percent / 100) * 10, 2)


# =========================
# SUGGESTION SYSTEM
# =========================
def get_suggestion(rank, percent):
    if rank == 1:
        return "🌟 Outstanding performance. Excellent for placements & advanced projects."
    elif percent >= 75:
        return "👍 Good performance. Focus on consistency & advanced problem solving."
    elif percent >= 60:
        return "⚠️ Average performance. Needs improvement in weak modules."
    else:
        return "❌ Below average. Strong revision and practice required."


# =========================
# GRAPH
# =========================
def create_chart(values):
    drawing = Drawing(220, 90)
    chart = VerticalBarChart()

    clean = [float(v) if str(v).replace('.', '', 1).isdigit() else 0 for v in values]
    if not clean:
        clean = [0]

    chart.data = [clean]
    chart.categoryAxis.categoryNames = [f"M{i+1}" for i in range(len(clean))]
    chart.valueAxis.valueMin = 0
    

    chart.barWidth = 8
    drawing.add(chart)
    return drawing


# =========================
# QR
# =========================
def generate_qr(data, name):
    path = f"output/qrcodes/{name}.png"
    qrcode.make(data).save(path)
    return path


# =========================
# WATERMARK
# =========================
def draw_watermark(c, doc):
    c.saveState()
    c.setFont("Helvetica-Bold", 60)
    c.setFillColorRGB(0.8, 0.8, 0.8)
    c.translate(300, 400)
    c.rotate(45)
    c.drawCentredString(0, 0, "LIET TRAINING")
    c.restoreState()


# =========================
# BORDER + SIGNATURE (UPDATED)
# =========================
# =========================
# BORDER + LOGO + TWO SIGNATURES
# =========================
def draw_decor(c, doc):

    # Outer Border
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.2)
    c.rect(15, 15, A4[0]-30, A4[1]-30)

    # -------------------------------
    # Header Logos (Left + Right)
    # -------------------------------

    if os.path.exists(LOGO_PATH):
        c.drawImage(
            LOGO_PATH,
            25,
            A4[1]-90,
            width=55,
            height=55,
            preserveAspectRatio=True,
            mask='auto'
        )

        c.drawImage(
            LOGO_PATH,
            A4[0]-80,
            A4[1]-90,
            width=55,
            height=55,
            preserveAspectRatio=True,
            mask='auto'
        )

    # -------------------------------
    # Footer Line
    # -------------------------------

    c.setStrokeColor(colors.grey)
    c.line(35,95,A4[0]-35,95)

    # =====================================================
    # LEFT SIDE → DEAN SIGNATURE
    # =====================================================

    if os.path.exists(DEAN_SIGN_PATH):

        c.drawImage(
            DEAN_SIGN_PATH,
            55,
            35,
            width=120,
            height=55,
            preserveAspectRatio=True,
            mask='auto'
        )

    c.setFont("Helvetica-Bold",9)
    c.drawCentredString(
        115,
        28,
        "Dean Signature"
    )

    # =====================================================
    # RIGHT SIDE → TRAINING COORDINATOR
    # =====================================================

    if os.path.exists(SIGN_PATH):

        c.drawImage(
            SIGN_PATH,
            A4[0]-180,
            35,
            width=120,
            height=55,
            preserveAspectRatio=True,
            mask='auto'
        )

    c.setFont("Helvetica-Bold",9)
    c.drawCentredString(
        A4[0]-120,
        28,
        "Training Coordinator"
    )

# =========================
# GENERATE GRADECARDS
# =========================
for idx, row in df.iterrows():

    name = str(row["Name"])
    safe = name.replace(" ", "_")

    pdf_path = f"output/gradecards/{safe}_gradecard.pdf"

    quiz_cols = [
        c for c in df.columns
        if "_Marks" in c and c != "Max_Marks"
    ]

    quiz_scores = []
    total_obtained = 0
    total_max_marks = 0

    # =========================
    # DYNAMIC MAX MARKS FIX
    # =========================
    quiz_scores = []
    for c in quiz_cols:
        try:
            val = float(row[c])
        except:
            val = 0

        quiz_scores.append(val)

    total_obtained = row["Total"]
    total_max_marks = row["Max_Marks"]
    percentage = row["Percentage"]
    cgpa = row["CGPA"]

    verification_id = row["Verification_ID"]
    suggestion = row["Suggestion"]
    qr_data = f"""
LIET BOOTCAMP RESULT
Name: {name}
Email: {row.get('Email','N/A')}
Rank: {row['Rank']}
Grade: {row['Grade']}
Percentage: {row['Percentage']}
CGPA: {row['CGPA']}
Attendance: {row['Attendance_%']}
Verification: {row['Verification_ID']}
"""

    qr_path = generate_qr(qr_data, safe)

    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    story = []

    # =========================
    # HEADER
    # =========================
    story.append(Paragraph(
        "LLOYD INSTITUTE OF ENGINEERING & TECHNOLOGY",
        title_style
    ))

    story.append(Paragraph(
        "ML & AGENTIC AI BOOTCAMP TRAINING PROGRAMME",
        subtitle_style
    ))
    story.append(Paragraph(
        "15 JUNE 2026 TO 16 JULY 2026",
        subtitle_style
    ))


    if os.path.exists(LOGO_PATH):
        img = Image(LOGO_PATH, 80, 80)
        img.hAlign = "CENTER"
        story.append(img)

    story.append(Spacer(1, 10))

    # =========================
    # STUDENT INFO
    # =========================
    info = [
    ["Name", name],
    ["Email", row.get("Email", "N/A")],
    ["Rank", row["Rank"]],
    ["Grade", row["Grade"]],
    ["Percentage", f"{row['Percentage']:.2f}%"],
    ["CGPA", row["CGPA"]],
    ["Attendance", f"{row['Attendance_%']:.2f}%"],
    ["Total Marks", row["Total"]],
    ["Max Marks", row["Max_Marks"]],
    ["Percentile", f"{row['Percentile']:.2f}"],
    ["Verification ID", row["Verification_ID"]]
    ]
    table = Table(info, colWidths=[160, 260])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))

    story.append(table)
    story.append(Spacer(1, 10))

    # =========================
    # MODULE TABLE
    # =========================
    story.append(Paragraph("<b>Module Performance</b>", normal))

    module_table = [["Module", "Score"]]
    for i, c in enumerate(quiz_cols):
        module_table.append([c.replace("_Marks", ""), quiz_scores[i]])

    t = Table(module_table, colWidths=[250, 120])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))

    story.append(t)
    story.append(Spacer(1, 10))

    # GRAPH
    story.append(create_chart(quiz_scores))

    # =========================
    # SUGGESTION BOX
    # =========================
    suggestion_table = Table(
        [["Performance Feedback", row["Suggestion"]]],
        colWidths=[120, 300]
    )

    suggestion_table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("BACKGROUND", (0,0), (0,0), colors.HexColor("#003366")),
        ("TEXTCOLOR", (0,0), (0,0), colors.white),
        ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold")
    ]))

    story.append(Spacer(1, 10))
    story.append(suggestion_table)

    # QR
    qr = Image(qr_path, 90, 90)
    qr.hAlign = "CENTER"
    story.append(Spacer(1, 10))
    story.append(qr)

    story.append(Spacer(1, 15))

    # FOOTER
    story.append(Paragraph(
        f"<para align=center><font size=8>"
        f"Generated on {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}"
        f"</font></para>",
        normal
    ))

    doc.build(
        story,
        onFirstPage=lambda c, d: (draw_watermark(c, d), draw_decor(c, d))
    )
    print("🏁 FINAL ADVANCED GRADECARDS GENERATED SUCCESSFULLY")