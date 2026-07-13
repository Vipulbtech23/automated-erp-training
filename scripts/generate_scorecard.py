import os
import re
from datetime import datetime

import pandas as pd
import qrcode

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    KeepTogether
)

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle
)

from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie


print("FINAL FASCINATING GRADECARD SYSTEM STARTED")


# =========================================================
# PATH SETTINGS
# =========================================================
INPUT_FILE = "output/final_rankings.xlsx"

LOGO_PATH = "assets/mllogo.png"
SIGN_PATH = "assets/signature.png"
DEAN_SIGN_PATH = "assets/Dean_Signature.png"

# Same avatar PNG will appear on every student's gradecard
AVATAR_PATH = "assets/avatar.png"

GRADECARD_FOLDER = "output/gradecards"
QR_FOLDER = "output/qrcodes"

TOTAL_ASSESSMENTS = 20

os.makedirs(GRADECARD_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)


# =========================================================
# CHECK INPUT FILE
# =========================================================
if not os.path.exists(INPUT_FILE):
    raise FileNotFoundError(
        f"File not found: {INPUT_FILE}\n"
        "Pehle calculate_scores.py run karo."
    )


# =========================================================
# LOAD DATA
# =========================================================
df = pd.read_excel(
    INPUT_FILE,
    dtype={
        "Email": str,
        "Name": str,
        "Roll No": str
    }
)

df.columns = (
    df.columns
    .astype(str)
    .str.strip()
)

print("\nColumns found:")
print(df.columns.tolist())


# =========================================================
# REQUIRED COLUMNS
# =========================================================
required_columns = [
    "Email",
    "Name",
    "Total",
    "Max_Marks",
    "Percentage",
    "CGPA",
    "Percentile",
    "Rank",
    "Grade",
    "Verification_ID",
    "Suggestion",
    "Attendance_%"
]

missing_required = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing_required:
    raise ValueError(
        "Required columns missing in final_rankings.xlsx: "
        f"{missing_required}"
    )

if "Roll No" not in df.columns:
    print("Roll No column not found. Blank Roll No column created.")
    df["Roll No"] = ""


# =========================================================
# FIND ASSESSMENT COLUMNS NUMBER-WISE
# =========================================================
assessment_columns = [
    f"Assessment{number}_Marks"
    for number in range(1, TOTAL_ASSESSMENTS + 1)
    if f"Assessment{number}_Marks" in df.columns
]

if not assessment_columns:
    raise ValueError(
        "Assessment1_Marks se Assessment20_Marks tak "
        "koi assessment column nahi mila."
    )

print("\nAssessment columns found:")
print(assessment_columns)
print(f"Total assessments found: {len(assessment_columns)}")


# =========================================================
# REPORTLAB STYLES
# =========================================================
styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    name="GradecardTitle",
    parent=styles["Title"],
    alignment=TA_CENTER,
    fontName="Helvetica-Bold",
    fontSize=14,
    leading=16,
    textColor=colors.HexColor("#0B3C5D"),
    spaceAfter=2
)

subtitle_style = ParagraphStyle(
    name="GradecardSubtitle",
    parent=styles["Normal"],
    alignment=TA_CENTER,
    fontName="Helvetica-Bold",
    fontSize=8.5,
    leading=10,
    textColor=colors.HexColor("#1D2731"),
    spaceAfter=1
)

section_heading_style = ParagraphStyle(
    name="SectionHeading",
    parent=styles["Normal"],
    alignment=TA_LEFT,
    fontName="Helvetica-Bold",
    fontSize=8.5,
    leading=10,
    textColor=colors.HexColor("#0B3C5D"),
    spaceAfter=3
)

small_style = ParagraphStyle(
    name="SmallText",
    parent=styles["Normal"],
    alignment=TA_LEFT,
    fontName="Helvetica",
    fontSize=7,
    leading=8.5
)

small_bold_style = ParagraphStyle(
    name="SmallBoldText",
    parent=small_style,
    fontName="Helvetica-Bold"
)

center_small_style = ParagraphStyle(
    name="CenterSmallText",
    parent=styles["Normal"],
    alignment=TA_CENTER,
    fontName="Helvetica",
    fontSize=7,
    leading=8.5
)

center_small_bold_style = ParagraphStyle(
    name="CenterSmallBoldText",
    parent=center_small_style,
    fontName="Helvetica-Bold"
)

feedback_style = ParagraphStyle(
    name="FeedbackText",
    parent=styles["Normal"],
    alignment=TA_LEFT,
    fontName="Helvetica",
    fontSize=7,
    leading=9
)

footer_style = ParagraphStyle(
    name="FooterText",
    parent=styles["Normal"],
    alignment=TA_CENTER,
    fontName="Helvetica",
    fontSize=6.3,
    leading=7.5,
    textColor=colors.HexColor("#444444")
)


# =========================================================
# HELPER FUNCTIONS
# =========================================================
def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_filename(value):
    text = str(value).strip()
    text = re.sub(r'[<>:"/\\|?*]+', "", text)
    text = re.sub(r"\s+", "_", text)
    return text or "Student"


def format_number(value):
    number = safe_float(value)

    if float(number).is_integer():
        return str(int(number))

    return f"{number:.2f}"


def clean_roll_number(value):
    if pd.isna(value):
        return ""

    value = str(value).strip()

    if value.lower() in ["", "nan", "none", "null", "n/a"]:
        return ""

    value = value.lstrip("'")
    value = re.sub(r"\.0$", "", value)

    return value


# =========================================================
# QR CODE
# =========================================================
def generate_qr(data, file_name):
    qr_path = os.path.join(
        QR_FOLDER,
        f"{file_name}.png"
    )

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=7,
        border=2
    )

    qr.add_data(data)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    image.save(qr_path)

    return qr_path


# =========================================================
# STUDENT AVATAR
# =========================================================
def get_student_avatar():
    if os.path.exists(AVATAR_PATH):
        avatar = Image(
            AVATAR_PATH,
            width=68,
            height=68
        )
        avatar.hAlign = "CENTER"
        return avatar

    return Table(
        [[Paragraph("STUDENT<br/>AVATAR", center_small_bold_style)]],
        colWidths=[68],
        rowHeights=[68],
        style=TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#8FA6B8")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EDF3F7")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE")
        ])
    )


# =========================================================
# ASSESSMENT BAR CHART
# =========================================================
def create_bar_chart(scores):
    drawing = Drawing(330, 105)
    chart = VerticalBarChart()

    clean_scores = [
        safe_float(score)
        for score in scores
    ]

    if not clean_scores:
        clean_scores = [0]

    chart.x = 30
    chart.y = 22
    chart.height = 68
    chart.width = 285

    chart.data = [clean_scores]

    chart.categoryAxis.categoryNames = [
        str(number)
        for number in range(1, len(clean_scores) + 1)
    ]

    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 5
    chart.categoryAxis.labels.dy = -7

    chart.valueAxis.valueMin = 0

    maximum_score = max(clean_scores) if clean_scores else 0

    chart.valueAxis.valueMax = max(
        15,
        int(maximum_score) + 2
    )

    chart.valueAxis.valueStep = 5
    chart.valueAxis.labels.fontSize = 5.5

    chart.barWidth = 8
    chart.groupSpacing = 2

    chart.bars[0].fillColor = colors.HexColor("#2878B5")
    chart.bars[0].strokeColor = colors.HexColor("#0B3C5D")

    drawing.add(chart)

    drawing.add(
        String(
            165,
            2,
            "Assessment Number",
            fontName="Helvetica",
            fontSize=6,
            textAnchor="middle",
            fillColor=colors.HexColor("#444444")
        )
    )

    return drawing


# =========================================================
# PIE CHART
# =========================================================
def create_pie_chart(obtained_marks, maximum_marks):
    obtained_marks = max(
        safe_float(obtained_marks),
        0
    )

    maximum_marks = max(
        safe_float(maximum_marks),
        0
    )

    remaining_marks = max(
        maximum_marks - obtained_marks,
        0
    )

    if maximum_marks <= 0:
        obtained_marks = 0
        remaining_marks = 1

    drawing = Drawing(145, 105)

    pie = Pie()

    pie.x = 37
    pie.y = 17
    pie.width = 72
    pie.height = 72

    pie.data = [
        obtained_marks,
        remaining_marks
    ]

    pie.labels = [
        "Obtained",
        "Remaining"
    ]

    pie.simpleLabels = 0
    pie.sideLabels = 1

    pie.slices.strokeWidth = 0.4
    pie.slices.strokeColor = colors.white

    pie.slices[0].fillColor = colors.HexColor("#18A999")
    pie.slices[1].fillColor = colors.HexColor("#DDE4EA")

    pie.slices[0].popout = 3

    pie.slices.fontName = "Helvetica-Bold"
    pie.slices.fontSize = 5.5

    drawing.add(pie)

    percentage = (
        (obtained_marks / maximum_marks) * 100
        if maximum_marks > 0
        else 0
    )

    drawing.add(
        String(
            73,
            3,
            f"{percentage:.1f}% Score",
            fontName="Helvetica-Bold",
            fontSize=7,
            textAnchor="middle",
            fillColor=colors.HexColor("#0B3C5D")
        )
    )

    return drawing


# =========================================================
# COMPACT ASSESSMENT TABLE
# =========================================================
def create_assessment_table(scores):
    rows = [
        [
            "Assessment",
            "Marks",
            "Assessment",
            "Marks"
        ]
    ]

    total_assessments = len(scores)
    midpoint = (total_assessments + 1) // 2

    left_scores = scores[:midpoint]
    right_scores = scores[midpoint:]

    for index in range(midpoint):
        left_number = index + 1
        left_score = format_number(
            left_scores[index]
        )

        if index < len(right_scores):
            right_number = midpoint + index + 1
            right_score = format_number(
                right_scores[index]
            )
            right_name = f"Assessment {right_number}"
        else:
            right_name = ""
            right_score = ""

        rows.append([
            f"Assessment {left_number}",
            left_score,
            right_name,
            right_score
        ])

    table = Table(
        rows,
        colWidths=[
            120,
            50,
            120,
            50
        ],
        rowHeights=15
    )

    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#0B3C5D")
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold"
            ),
            (
                "FONTNAME",
                (0, 1),
                (-1, -1),
                "Helvetica"
            ),
            (
                "ALIGN",
                (0, 0),
                (-1, 0),
                "CENTER"
            ),
            (
                "ALIGN",
                (1, 1),
                (1, -1),
                "CENTER"
            ),
            (
                "ALIGN",
                (3, 1),
                (3, -1),
                "CENTER"
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                6.5
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.35,
                colors.HexColor("#607D8B")
            ),
            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [
                    colors.white,
                    colors.HexColor("#F3F7FA")
                ]
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                4
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                4
            )
        ])
    )

    return table


# =========================================================
# PERFORMANCE SUMMARY CARDS
# =========================================================
def create_performance_summary(
    percentage,
    cgpa,
    rank,
    grade,
    attendance
):
    summary_data = [
        [
            "PERCENTAGE",
            "CGPA",
            "RANK",
            "GRADE",
            "ATTENDANCE"
        ],
        [
            f"{percentage:.2f}%",
            f"{cgpa:.2f}",
            f"#{rank}",
            grade,
            f"{attendance:.2f}%"
        ]
    ]

    summary_table = Table(
        summary_data,
        colWidths=[
            94,
            94,
            94,
            94,
            94
        ],
        rowHeights=[
            17,
            24
        ]
    )

    summary_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#0B3C5D")
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),
            (
                "BACKGROUND",
                (0, 1),
                (-1, 1),
                colors.HexColor("#EAF2F8")
            ),
            (
                "TEXTCOLOR",
                (0, 1),
                (-1, 1),
                colors.HexColor("#0B3C5D")
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, -1),
                "Helvetica-Bold"
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, 0),
                6.2
            ),
            (
                "FONTSIZE",
                (0, 1),
                (-1, 1),
                9
            ),
            (
                "ALIGN",
                (0, 0),
                (-1, -1),
                "CENTER"
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.HexColor("#9BB3C3")
            )
        ])
    )

    return summary_table


# =========================================================
# WATERMARK
# =========================================================
def draw_watermark(canvas, doc):
    canvas.saveState()

    canvas.setFont(
        "Helvetica-Bold",
        50
    )

    canvas.setFillColor(
        colors.Color(
            0.80,
            0.84,
            0.88,
            alpha=0.18
        )
    )

    canvas.translate(
        A4[0] / 2,
        A4[1] / 2
    )

    canvas.rotate(45)

    canvas.drawCentredString(
        0,
        0,
        "LIET TRAINING"
    )

    canvas.restoreState()


# =========================================================
# PAGE DECORATION
# =========================================================
def draw_decor(canvas, doc):
    canvas.saveState()

    # Outer border
    canvas.setStrokeColor(
        colors.HexColor("#0B3C5D")
    )

    canvas.setLineWidth(1.3)

    canvas.rect(
        15,
        15,
        A4[0] - 30,
        A4[1] - 30
    )

    # Inner border
    canvas.setStrokeColor(
        colors.HexColor("#9BB3C3")
    )

    canvas.setLineWidth(0.5)

    canvas.rect(
        20,
        20,
        A4[0] - 40,
        A4[1] - 40
    )

    # Header accent line
    canvas.setStrokeColor(
        colors.HexColor("#18A999")
    )

    canvas.setLineWidth(2)

    canvas.line(
        35,
        A4[1] - 92,
        A4[0] - 35,
        A4[1] - 92
    )

    # Header logos
    if os.path.exists(LOGO_PATH):
        canvas.drawImage(
            LOGO_PATH,
            28,
            A4[1] - 78,
            width=43,
            height=43,
            preserveAspectRatio=True,
            mask="auto"
        )

        canvas.drawImage(
            LOGO_PATH,
            A4[0] - 71,
            A4[1] - 78,
            width=43,
            height=43,
            preserveAspectRatio=True,
            mask="auto"
        )

    # Footer separator
    canvas.setStrokeColor(
        colors.HexColor("#9BB3C3")
    )

    canvas.setLineWidth(0.5)

    canvas.line(
        35,
        78,
        A4[0] - 35,
        78
    )

    # Dean signature
    if os.path.exists(DEAN_SIGN_PATH):
        canvas.drawImage(
            DEAN_SIGN_PATH,
            55,
            27,
            width=110,
            height=43,
            preserveAspectRatio=True,
            mask="auto"
        )

    canvas.setFillColor(colors.black)
    canvas.setFont(
        "Helvetica-Bold",
        7.5
    )

    canvas.drawCentredString(
        110,
        21,
        "Dean Signature"
    )

    # Training coordinator signature
    if os.path.exists(SIGN_PATH):
        canvas.drawImage(
            SIGN_PATH,
            A4[0] - 165,
            27,
            width=110,
            height=43,
            preserveAspectRatio=True,
            mask="auto"
        )

    canvas.drawCentredString(
        A4[0] - 110,
        21,
        "Training Coordinator"
    )

    canvas.restoreState()


def page_design(canvas, doc):
    draw_watermark(canvas, doc)
    draw_decor(canvas, doc)


# =========================================================
# GENERATE GRADECARD FOR EACH STUDENT
# =========================================================
generated_count = 0

for index, row in df.iterrows():

    student_name = str(
        row.get("Name", "Student")
    ).strip()

    roll_number = clean_roll_number(
        row.get("Roll No", "")
    )

    student_email = str(
        row.get("Email", "N/A")
    ).strip()

    safe_name = safe_filename(
        student_name
    )

    verification_id = str(
        row.get(
            "Verification_ID",
            f"LIET-{index + 1:03d}"
        )
    ).strip()

    unique_file_name = safe_filename(
        f"{safe_name}_{verification_id}"
    )

    pdf_path = os.path.join(
        GRADECARD_FOLDER,
        f"{unique_file_name}_gradecard.pdf"
    )

    assessment_scores = [
        safe_float(
            row.get(column, 0)
        )
        for column in assessment_columns
    ]

    total_obtained = safe_float(
        row.get("Total", 0)
    )

    total_maximum = safe_float(
        row.get("Max_Marks", 0)
    )

    percentage = safe_float(
        row.get("Percentage", 0)
    )

    cgpa = safe_float(
        row.get("CGPA", 0)
    )

    percentile = safe_float(
        row.get("Percentile", 0)
    )

    attendance = safe_float(
        row.get("Attendance_%", 0)
    )

    rank = int(
        safe_float(
            row.get("Rank", 0)
        )
    )

    grade = str(
        row.get("Grade", "N/A")
    )

    suggestion = str(
        row.get(
            "Suggestion",
            "Continue regular practice and revision."
        )
    )


    # =====================================================
    # QR DATA
    # =====================================================
    qr_data = (
        "LIET BOOTCAMP RESULT\n"
        f"Name: {student_name}\n"
        f"Roll No: {roll_number or 'N/A'}\n"
        f"Email: {student_email}\n"
        f"Rank: {rank}\n"
        f"Grade: {grade}\n"
        f"Percentage: {percentage:.2f}%\n"
        f"CGPA: {cgpa:.2f}\n"
        f"Attendance: {attendance:.2f}%\n"
        f"Verification ID: {verification_id}"
    )

    qr_path = generate_qr(
        qr_data,
        unique_file_name
    )


    # =====================================================
    # PDF DOCUMENT
    # =====================================================
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,

        leftMargin=45,
        rightMargin=45,
        topMargin=32,
        bottomMargin=82,

        title=f"{student_name} Gradecard",
        author="Lloyd Institute of Engineering & Technology",
        subject="ML and Agentic AI Bootcamp Gradecard"
    )

    story = []


    # =====================================================
    # HEADER
    # =====================================================
    story.append(
        Paragraph(
            "LLOYD INSTITUTE OF ENGINEERING & TECHNOLOGY",
            title_style
        )
    )

    story.append(
        Paragraph(
            "ML & AGENTIC AI BOOTCAMP TRAINING PROGRAMME",
            subtitle_style
        )
    )

    story.append(
        Paragraph(
            "15 JUNE 2026 TO 16 JULY 2026",
            subtitle_style
        )
    )

    story.append(
        Spacer(1, 5)
    )


    # =====================================================
    # STUDENT DETAILS WITH AVATAR
    # =====================================================
    avatar = get_student_avatar()

    details_data = [
        [
            Paragraph("<b>Name</b>", small_style),
            Paragraph(student_name, small_style),
            Paragraph("<b>Roll No</b>", small_style),
            Paragraph(roll_number or "N/A", small_style)
        ],
        [
            Paragraph("<b>Email</b>", small_style),
            Paragraph(student_email, small_style),
            Paragraph("<b>Verification ID</b>", small_style),
            Paragraph(verification_id, small_style)
        ],
        [
            Paragraph("<b>Total Marks</b>", small_style),
            Paragraph(
                f"{format_number(total_obtained)} / "
                f"{format_number(total_maximum)}",
                small_style
            ),
            Paragraph("<b>Percentile</b>", small_style),
            Paragraph(f"{percentile:.2f}", small_style)
        ]
    ]

    details_table = Table(
        details_data,
        colWidths=[
            68,
            135,
            78,
            122
        ],
        rowHeights=[
            22,
            28,
            22
        ]
    )

    details_table.setStyle(
        TableStyle([
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.HexColor("#607D8B")
            ),
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#E8F0F5")
            ),
            (
                "BACKGROUND",
                (2, 0),
                (2, -1),
                colors.HexColor("#E8F0F5")
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                4
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                4
            )
        ])
    )

    student_profile_table = Table(
        [
            [
                avatar,
                details_table
            ]
        ],
        colWidths=[
            72,
            403
        ]
    )

    student_profile_table.setStyle(
        TableStyle([
            (
                "BOX",
                (0, 0),
                (-1, -1),
                0.7,
                colors.HexColor("#0B3C5D")
            ),
            (
                "BACKGROUND",
                (0, 0),
                (0, 0),
                colors.HexColor("#F1F6F9")
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),
            (
                "ALIGN",
                (0, 0),
                (0, 0),
                "CENTER"
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                5
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                5
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                5
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                5
            )
        ])
    )

    story.append(student_profile_table)
    story.append(Spacer(1, 5))


    # =====================================================
    # PERFORMANCE SUMMARY
    # =====================================================
    story.append(
        create_performance_summary(
            percentage,
            cgpa,
            rank,
            grade,
            attendance
        )
    )

    story.append(
        Spacer(1, 5)
    )


    # =====================================================
    # ASSESSMENT TABLE
    # =====================================================
    story.append(
        Paragraph(
            "Assessment Performance",
            section_heading_style
        )
    )

    story.append(
        create_assessment_table(
            assessment_scores
        )
    )

    story.append(
        Spacer(1, 4)
    )


    # =====================================================
    # BAR CHART + PIE CHART
    # =====================================================
    story.append(
        Paragraph(
            "Visual Performance Analysis",
            section_heading_style
        )
    )

    chart_table = Table(
        [
            [
                create_bar_chart(
                    assessment_scores
                ),
                create_pie_chart(
                    total_obtained,
                    total_maximum
                )
            ]
        ],
        colWidths=[
            330,
            145
        ],
        rowHeights=[
            107
        ]
    )

    chart_table.setStyle(
        TableStyle([
            (
                "BOX",
                (0, 0),
                (-1, -1),
                0.5,
                colors.HexColor("#9BB3C3")
            ),
            (
                "LINEAFTER",
                (0, 0),
                (0, 0),
                0.5,
                colors.HexColor("#9BB3C3")
            ),
            (
                "BACKGROUND",
                (0, 0),
                (-1, -1),
                colors.HexColor("#FAFCFD")
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),
            (
                "ALIGN",
                (0, 0),
                (-1, -1),
                "CENTER"
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                0
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                0
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                1
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                1
            )
        ])
    )

    story.append(chart_table)
    story.append(Spacer(1, 4))


    # =====================================================
    # FEEDBACK AND QR
    # =====================================================
    feedback_content = Paragraph(
        suggestion,
        feedback_style
    )

    qr_image = Image(
        qr_path,
        width=64,
        height=64
    )

    qr_image.hAlign = "CENTER"

    feedback_qr_table = Table(
        [
            [
                Paragraph(
                    "<b>PERFORMANCE FEEDBACK</b>",
                    center_small_bold_style
                ),
                Paragraph(
                    "<b>RESULT VERIFICATION</b>",
                    center_small_bold_style
                )
            ],
            [
                feedback_content,
                qr_image
            ]
        ],
        colWidths=[
            392,
            83
        ],
        rowHeights=[
            17,
            69
        ]
    )

    feedback_qr_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#0B3C5D")
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
                0.4,
                colors.HexColor("#607D8B")
            ),
            (
                "BACKGROUND",
                (0, 1),
                (-1, 1),
                colors.HexColor("#F6F9FB")
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),
            (
                "ALIGN",
                (1, 0),
                (1, -1),
                "CENTER"
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                6
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                6
            )
        ])
    )

    story.append(
        KeepTogether([
            feedback_qr_table,
            Spacer(1, 2),
            Paragraph(
                (
                    "Scan the QR code to verify the student's result. "
                    f"Generated on "
                    f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}"
                ),
                footer_style
            )
        ])
    )


    # =====================================================
    # BUILD PDF
    # =====================================================
    doc.build(
        story,
        onFirstPage=page_design,
        onLaterPages=page_design
    )

    generated_count += 1

    print(
        f"Generated {generated_count}: "
        f"{student_name}"
    )


print("\n" + "=" * 70)
print("FINAL FASCINATING GRADECARD GENERATION COMPLETED")
print(f"Total gradecards generated: {generated_count}")
print(f"Gradecards folder: {GRADECARD_FOLDER}")
print(f"QR codes folder: {QR_FOLDER}")
print("=" * 70)