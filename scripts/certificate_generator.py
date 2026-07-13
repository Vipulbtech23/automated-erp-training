import os
import re
from datetime import datetime

import pandas as pd
import qrcode

from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth


print("Starting Premium Certificate Generator...")


# ============================================================
# SETTINGS
# ============================================================
INPUT_FILE = "output/final_rankings.xlsx"

LOGO_PATH = "assets/mllogo.png"
SIGN_PATH = "assets/signature.png"
DEAN_SIGN_PATH = "assets/Dean_Signature.png"

CERTIFICATE_FOLDER = "output/certificates"
QR_FOLDER = "output/qr1"

PROGRAM_NAME = "ML & Agentic AI Bootcamp Training Programme"
COLLEGE_NAME = "LLOYD INSTITUTE OF ENGINEERING & TECHNOLOGY"
TRAINING_PERIOD = "15 June 2026 to 16 July 2026"

PAGE_SIZE = landscape(A4)
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE

os.makedirs(CERTIFICATE_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)


# ============================================================
# CHECK INPUT FILE
# ============================================================
if not os.path.exists(INPUT_FILE):
    raise FileNotFoundError(
        f"File not found: {INPUT_FILE}\n"
        "Please run calculate_scores.py first."
    )


# ============================================================
# LOAD STUDENT DATA
# ============================================================
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


required_columns = [
    "Name",
    "Rank",
    "Percentage",
    "CGPA"
]

missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing_columns:
    raise ValueError(
        "Missing required columns in final_rankings.xlsx: "
        f"{missing_columns}"
    )


if "Email" not in df.columns:
    df["Email"] = ""

if "Roll No" not in df.columns:
    df["Roll No"] = ""

if "Attendance_%" not in df.columns:
    df["Attendance_%"] = 0

if "Verification_ID" not in df.columns:
    df["Verification_ID"] = ""


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def clean_text(value, default=""):
    if pd.isna(value):
        return default

    text = str(value).strip()

    if text.lower() in ["nan", "none", "null"]:
        return default

    return text


def clean_roll_number(value):
    text = clean_text(value)

    if not text:
        return ""

    text = text.lstrip("'")
    text = re.sub(r"\.0$", "", text)

    return text


def safe_filename(value):
    text = clean_text(value, "Student")
    text = re.sub(r'[<>:"/\\|?*]+', "", text)
    text = re.sub(r"\s+", "_", text)
    return text or "Student"


def get_badge(rank):
    rank = int(safe_float(rank, 999999))

    if rank == 1:
        return "GOLD"
    elif rank <= 3:
        return "SILVER"
    elif rank <= 10:
        return "BRONZE"
    else:
        return "PARTICIPATION"


def get_badge_colors(badge):
    if badge == "GOLD":
        return {
            "main": colors.HexColor("#D4AF37"),
            "dark": colors.HexColor("#8A6D00"),
            "light": colors.HexColor("#FFF4BF")
        }

    if badge == "SILVER":
        return {
            "main": colors.HexColor("#BFC3C8"),
            "dark": colors.HexColor("#666B73"),
            "light": colors.HexColor("#F1F3F5")
        }

    if badge == "BRONZE":
        return {
            "main": colors.HexColor("#CD7F32"),
            "dark": colors.HexColor("#7A4319"),
            "light": colors.HexColor("#F7DDC3")
        }

    return {
        "main": colors.HexColor("#2E86C1"),
        "dark": colors.HexColor("#164A70"),
        "light": colors.HexColor("#D9EEF9")
    }


def build_certificate_id(row, index):
    existing_id = clean_text(
        row.get("Verification_ID", "")
    )

    if existing_id:
        return existing_id

    safe_name = safe_filename(
        row.get("Name", "Student")
    )

    rank = int(
        safe_float(
            row.get("Rank", index + 1),
            index + 1
        )
    )

    return (
        f"LIET-2026-"
        f"{safe_name[:4].upper()}-"
        f"{rank:03d}"
    )


def fit_font_size(
    canvas_obj,
    text,
    font_name,
    max_size,
    min_size,
    max_width
):
    size = max_size

    while size > min_size:
        width = stringWidth(
            text,
            font_name,
            size
        )

        if width <= max_width:
            return size

        size -= 0.5

    return min_size


# ============================================================
# QR CODE
# ============================================================
def generate_qr(data, filename):
    qr_path = os.path.join(
        QR_FOLDER,
        f"{filename}_qr.png"
    )

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=8,
        border=2
    )

    qr.add_data(data)
    qr.make(fit=True)

    qr_image = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    qr_image.save(qr_path)

    return qr_path


# ============================================================
# DECORATIVE FUNCTIONS
# ============================================================
def draw_background(c, badge_colors):
    # Soft ivory certificate background
    c.setFillColor(
        colors.HexColor("#FFFDF7")
    )
    c.rect(
        0,
        0,
        PAGE_WIDTH,
        PAGE_HEIGHT,
        fill=1,
        stroke=0
    )

    # Light corner panels
    c.setFillColor(
        badge_colors["light"]
    )

    corner_size = 95

    c.saveState()
    c.translate(0, PAGE_HEIGHT)
    c.rotate(-45)
    c.rect(
        -20,
        -35,
        corner_size,
        corner_size,
        fill=1,
        stroke=0
    )
    c.restoreState()

    c.saveState()
    c.translate(PAGE_WIDTH, 0)
    c.rotate(135)
    c.rect(
        -20,
        -35,
        corner_size,
        corner_size,
        fill=1,
        stroke=0
    )
    c.restoreState()


def draw_borders(c, badge_colors):
    # Main dark outer border
    c.setStrokeColor(
        colors.HexColor("#102A43")
    )
    c.setLineWidth(4)
    c.rect(
        18,
        18,
        PAGE_WIDTH - 36,
        PAGE_HEIGHT - 36
    )

    # Badge-colored second border
    c.setStrokeColor(
        badge_colors["main"]
    )
    c.setLineWidth(2)
    c.rect(
        27,
        27,
        PAGE_WIDTH - 54,
        PAGE_HEIGHT - 54
    )

    # Thin inner border
    c.setStrokeColor(
        colors.HexColor("#708090")
    )
    c.setLineWidth(0.7)
    c.rect(
        35,
        35,
        PAGE_WIDTH - 70,
        PAGE_HEIGHT - 70
    )

    # Decorative corner lines
    c.setStrokeColor(
        badge_colors["dark"]
    )
    c.setLineWidth(2)

    line_length = 52
    margin = 42

    # Bottom left
    c.line(
        margin,
        margin,
        margin + line_length,
        margin
    )
    c.line(
        margin,
        margin,
        margin,
        margin + line_length
    )

    # Bottom right
    c.line(
        PAGE_WIDTH - margin,
        margin,
        PAGE_WIDTH - margin - line_length,
        margin
    )
    c.line(
        PAGE_WIDTH - margin,
        margin,
        PAGE_WIDTH - margin,
        margin + line_length
    )

    # Top left
    c.line(
        margin,
        PAGE_HEIGHT - margin,
        margin + line_length,
        PAGE_HEIGHT - margin
    )
    c.line(
        margin,
        PAGE_HEIGHT - margin,
        margin,
        PAGE_HEIGHT - margin - line_length
    )

    # Top right
    c.line(
        PAGE_WIDTH - margin,
        PAGE_HEIGHT - margin,
        PAGE_WIDTH - margin - line_length,
        PAGE_HEIGHT - margin
    )
    c.line(
        PAGE_WIDTH - margin,
        PAGE_HEIGHT - margin,
        PAGE_WIDTH - margin,
        PAGE_HEIGHT - margin - line_length
    )


def draw_watermark(c):
    c.saveState()

    c.setFont(
        "Helvetica-Bold",
        54
    )

    c.setFillColor(
        colors.Color(
            0.74,
            0.78,
            0.82,
            alpha=0.12
        )
    )

    c.translate(
        PAGE_WIDTH / 2,
        PAGE_HEIGHT / 2
    )

    c.rotate(30)

    c.drawCentredString(
        0,
        0,
        "LIET"
    )

    c.restoreState()


def draw_logo(c):
    if os.path.exists(LOGO_PATH):
        c.drawImage(
            LOGO_PATH,
            PAGE_WIDTH / 2 - 38,
            PAGE_HEIGHT - 100,
            width=76,
            height=58,
            preserveAspectRatio=True,
            mask="auto"
        )


def draw_ornament(c, y, badge_colors):
    center_x = PAGE_WIDTH / 2

    c.setStrokeColor(
        badge_colors["main"]
    )
    c.setLineWidth(1.2)

    c.line(
        center_x - 180,
        y,
        center_x - 18,
        y
    )

    c.line(
        center_x + 18,
        y,
        center_x + 180,
        y
    )

    c.setFillColor(
        badge_colors["main"]
    )

    c.circle(
        center_x,
        y,
        4,
        fill=1,
        stroke=0
    )

    c.circle(
        center_x - 10,
        y,
        2,
        fill=1,
        stroke=0
    )

    c.circle(
        center_x + 10,
        y,
        2,
        fill=1,
        stroke=0
    )


def draw_badge_seal(c, badge, badge_colors):
    center_x = PAGE_WIDTH - 112
    center_y = 180

    # Ribbon tails
    c.setFillColor(
        badge_colors["dark"]
    )

    ribbon_path = c.beginPath()
    ribbon_path.moveTo(
        center_x - 30,
        center_y - 38
    )
    ribbon_path.lineTo(
        center_x - 8,
        center_y - 88
    )
    ribbon_path.lineTo(
        center_x + 1,
        center_y - 45
    )
    ribbon_path.close()

    c.drawPath(
        ribbon_path,
        fill=1,
        stroke=0
    )

    ribbon_path_2 = c.beginPath()
    ribbon_path_2.moveTo(
        center_x + 30,
        center_y - 38
    )
    ribbon_path_2.lineTo(
        center_x + 8,
        center_y - 88
    )
    ribbon_path_2.lineTo(
        center_x - 1,
        center_y - 45
    )
    ribbon_path_2.close()

    c.drawPath(
        ribbon_path_2,
        fill=1,
        stroke=0
    )

    # Outer seal
    c.setFillColor(
        badge_colors["main"]
    )
    c.setStrokeColor(
        badge_colors["dark"]
    )
    c.setLineWidth(2.5)

    c.circle(
        center_x,
        center_y,
        47,
        fill=1,
        stroke=1
    )

    # Inner seal
    c.setFillColor(
        badge_colors["light"]
    )
    c.setLineWidth(1.3)

    c.circle(
        center_x,
        center_y,
        37,
        fill=1,
        stroke=1
    )

    c.setFillColor(
        badge_colors["dark"]
    )

    c.setFont(
        "Helvetica-Bold",
        10
    )

    c.drawCentredString(
        center_x,
        center_y + 7,
        badge
    )

    c.setFont(
        "Helvetica-Bold",
        8
    )

    c.drawCentredString(
        center_x,
        center_y - 7,
        "CERTIFICATE"
    )


# ============================================================
# SIGNATURE SECTION
# ============================================================
def draw_signature_block(
    c,
    image_path,
    center_x,
    label
):
    if os.path.exists(image_path):
        c.drawImage(
            image_path,
            center_x - 63,
            70,
            width=126,
            height=48,
            preserveAspectRatio=True,
            mask="auto"
        )

    c.setStrokeColor(
        colors.HexColor("#333333")
    )
    c.setLineWidth(0.7)

    c.line(
        center_x - 70,
        67,
        center_x + 70,
        67
    )

    c.setFillColor(
        colors.HexColor("#1F2933")
    )

    c.setFont(
        "Helvetica-Bold",
        9
    )

    c.drawCentredString(
        center_x,
        53,
        label
    )


# ============================================================
# CERTIFICATE CREATION
# ============================================================
def create_certificate(row, index):
    name = clean_text(
        row.get("Name", "Student"),
        "Student"
    )

    safe_name = safe_filename(name)

    rank = int(
        safe_float(
            row.get("Rank", index + 1),
            index + 1
        )
    )

    percentage = safe_float(
        row.get("Percentage", 0)
    )

    cgpa = safe_float(
        row.get("CGPA", 0)
    )

    attendance = safe_float(
        row.get("Attendance_%", 0)
    )

    email = clean_text(
        row.get("Email", ""),
        "Not Available"
    )

    roll_number = clean_roll_number(
        row.get("Roll No", "")
    )

    badge = get_badge(rank)
    badge_colors = get_badge_colors(badge)

    cert_id = build_certificate_id(
        row,
        index
    )

    unique_name = safe_filename(
        f"{safe_name}_{cert_id}"
    )

    pdf_path = os.path.join(
        CERTIFICATE_FOLDER,
        f"{unique_name}_certificate.pdf"
    )

    qr_data = (
        "LIET CERTIFICATE VERIFICATION\n"
        f"Name: {name}\n"
        f"Roll No: {roll_number or 'N/A'}\n"
        f"Email: {email}\n"
        f"Programme: {PROGRAM_NAME}\n"
        f"Training Period: {TRAINING_PERIOD}\n"
        f"Rank: {rank}\n"
        f"Badge: {badge}\n"
        f"Percentage: {percentage:.2f}%\n"
        f"CGPA: {cgpa:.2f}\n"
        f"Attendance: {attendance:.2f}%\n"
        f"Certificate ID: {cert_id}\n"
        f"Issued: {datetime.now().strftime('%d-%m-%Y')}"
    )

    qr_path = generate_qr(
        qr_data,
        unique_name
    )

    c = canvas.Canvas(
        pdf_path,
        pagesize=PAGE_SIZE
    )

    c.setTitle(
        f"{name} - Certificate of Completion"
    )

    c.setAuthor(
        COLLEGE_NAME
    )

    c.setSubject(
        PROGRAM_NAME
    )


    # --------------------------------------------------------
    # BACKGROUND AND FRAME
    # --------------------------------------------------------
    draw_background(
        c,
        badge_colors
    )

    draw_watermark(c)

    draw_borders(
        c,
        badge_colors
    )

    draw_logo(c)


    # --------------------------------------------------------
    # COLLEGE NAME
    # --------------------------------------------------------
    c.setFillColor(
        colors.HexColor("#102A43")
    )

    c.setFont(
        "Helvetica-Bold",
        16
    )

    c.drawCentredString(
        PAGE_WIDTH / 2,
        PAGE_HEIGHT - 117,
        COLLEGE_NAME
    )

    c.setFillColor(
        colors.HexColor("#52616B")
    )

    c.setFont(
        "Helvetica",
        8.5
    )

    c.drawCentredString(
        PAGE_WIDTH / 2,
        PAGE_HEIGHT - 133,
        "Greater Noida, Uttar Pradesh"
    )


    # --------------------------------------------------------
    # MAIN CERTIFICATE TITLE
    # --------------------------------------------------------
    draw_ornament(
        c,
        PAGE_HEIGHT - 153,
        badge_colors
    )

    c.setFillColor(
        colors.HexColor("#102A43")
    )

    c.setFont(
        "Helvetica-Bold",
        28
    )

    c.drawCentredString(
        PAGE_WIDTH / 2,
        PAGE_HEIGHT - 190,
        "CERTIFICATE OF COMPLETION"
    )

    c.setFillColor(
        badge_colors["dark"]
    )

    c.setFont(
        "Helvetica-BoldOblique",
        10
    )

    c.drawCentredString(
        PAGE_WIDTH / 2,
        PAGE_HEIGHT - 210,
        f"{badge} CATEGORY"
    )


    # --------------------------------------------------------
    # PRESENTATION TEXT
    # --------------------------------------------------------
    c.setFillColor(
        colors.HexColor("#4A5568")
    )

    c.setFont(
        "Helvetica",
        11
    )

    c.drawCentredString(
        PAGE_WIDTH / 2,
        PAGE_HEIGHT - 239,
        "This certificate is proudly presented to"
    )


    # --------------------------------------------------------
    # STUDENT NAME
    # --------------------------------------------------------
    name_font_size = fit_font_size(
        c,
        name,
        "Helvetica-BoldOblique",
        max_size=27,
        min_size=16,
        max_width=470
    )

    c.setFillColor(
        colors.HexColor("#0B3C5D")
    )

    c.setFont(
        "Helvetica-BoldOblique",
        name_font_size
    )

    c.drawCentredString(
        PAGE_WIDTH / 2,
        PAGE_HEIGHT - 282,
        name
    )

    c.setStrokeColor(
        badge_colors["main"]
    )

    c.setLineWidth(1.1)

    c.line(
        PAGE_WIDTH / 2 - 235,
        PAGE_HEIGHT - 294,
        PAGE_WIDTH / 2 + 235,
        PAGE_HEIGHT - 294
    )


    # --------------------------------------------------------
    # PROGRAM DESCRIPTION
    # --------------------------------------------------------
    c.setFillColor(
        colors.HexColor("#3E4C59")
    )

    c.setFont(
        "Helvetica",
        10.8
    )

    c.drawCentredString(
        PAGE_WIDTH / 2,
        PAGE_HEIGHT - 322,
        "for successfully completing the"
    )

    c.setFillColor(
        colors.HexColor("#102A43")
    )

    c.setFont(
        "Helvetica-Bold",
        14
    )

    c.drawCentredString(
        PAGE_WIDTH / 2,
        PAGE_HEIGHT - 346,
        PROGRAM_NAME
    )

    c.setFillColor(
        colors.HexColor("#52616B")
    )

    c.setFont(
        "Helvetica",
        10
    )

    c.drawCentredString(
        PAGE_WIDTH / 2,
        PAGE_HEIGHT - 369,
        f"conducted from {TRAINING_PERIOD}"
    )


    # --------------------------------------------------------
    # PERFORMANCE PANEL
    # --------------------------------------------------------
    panel_x = 180
    panel_y = 147
    panel_width = 485
    panel_height = 72

    c.setFillColor(
        colors.HexColor("#F3F7FA")
    )

    c.setStrokeColor(
        colors.HexColor("#9FB3C8")
    )

    c.setLineWidth(0.8)

    c.roundRect(
        panel_x,
        panel_y,
        panel_width,
        panel_height,
        8,
        fill=1,
        stroke=1
    )

    labels = [
        ("RANK", f"#{rank}"),
        ("PERCENTAGE", f"{percentage:.2f}%"),
        ("CGPA", f"{cgpa:.2f}"),
        ("ATTENDANCE", f"{attendance:.2f}%")
    ]

    column_width = panel_width / len(labels)

    for item_index, (label, value) in enumerate(labels):
        center_x = (
            panel_x
            + column_width * item_index
            + column_width / 2
        )

        if item_index > 0:
            c.setStrokeColor(
                colors.HexColor("#CBD5E0")
            )
            c.line(
                panel_x + column_width * item_index,
                panel_y + 10,
                panel_x + column_width * item_index,
                panel_y + panel_height - 10
            )

        c.setFillColor(
            colors.HexColor("#52616B")
        )

        c.setFont(
            "Helvetica-Bold",
            7.5
        )

        c.drawCentredString(
            center_x,
            panel_y + 47,
            label
        )

        c.setFillColor(
            badge_colors["dark"]
        )

        c.setFont(
            "Helvetica-Bold",
            15
        )

        c.drawCentredString(
            center_x,
            panel_y + 23,
            value
        )


    # --------------------------------------------------------
    # BADGE SEAL
    # --------------------------------------------------------
    draw_badge_seal(
        c,
        badge,
        badge_colors
    )


    # --------------------------------------------------------
    # QR CODE
    # --------------------------------------------------------
    if os.path.exists(qr_path):
        c.setFillColor(
            colors.white
        )

        c.setStrokeColor(
            colors.HexColor("#9FB3C8")
        )

        c.roundRect(
            48,
            119,
            105,
            123,
            6,
            fill=1,
            stroke=1
        )

        c.drawImage(
            qr_path,
            59,
            137,
            width=83,
            height=83,
            preserveAspectRatio=True,
            mask="auto"
        )

        c.setFillColor(
            colors.HexColor("#52616B")
        )

        c.setFont(
            "Helvetica-Bold",
            6.5
        )

        c.drawCentredString(
            100,
            126,
            "SCAN TO VERIFY"
        )


    # --------------------------------------------------------
    # CERTIFICATE ID
    # --------------------------------------------------------
    c.setFillColor(
        colors.HexColor("#52616B")
    )

    c.setFont(
        "Helvetica",
        7.5
    )

    c.drawCentredString(
        PAGE_WIDTH / 2,
        128,
        f"Certificate ID: {cert_id}"
    )

    if roll_number:
        c.drawCentredString(
            PAGE_WIDTH / 2,
            116,
            f"Roll No: {roll_number}"
        )


    # --------------------------------------------------------
    # SIGNATURES
    # --------------------------------------------------------
    draw_signature_block(
        c,
        DEAN_SIGN_PATH,
        235,
        "Dean"
    )

    draw_signature_block(
        c,
        SIGN_PATH,
        PAGE_WIDTH - 235,
        "Training Coordinator"
    )


    # --------------------------------------------------------
    # FOOTER
    # --------------------------------------------------------
    c.setFillColor(
        colors.HexColor("#52616B")
    )

    c.setFont(
        "Helvetica-Oblique",
        7.5
    )

    c.drawCentredString(
        PAGE_WIDTH / 2,
        42,
        "Keep Learning - Keep Practicing - Keep Growing"
    )

    c.setFont(
        "Helvetica",
        6.5
    )

    c.drawCentredString(
        PAGE_WIDTH / 2,
        30,
        f"Issued on {datetime.now().strftime('%d %B %Y')}"
    )


    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------
    c.showPage()
    c.save()

    print(
        f"Certificate Generated: {pdf_path}"
    )


# ============================================================
# GENERATE ALL CERTIFICATES
# ============================================================
generated_count = 0

for index, row in df.iterrows():
    create_certificate(
        row,
        index
    )

    generated_count += 1


print("\n" + "=" * 72)
print("ALL PREMIUM CERTIFICATES GENERATED SUCCESSFULLY")
print(f"Total certificates generated: {generated_count}")
print(f"Output folder: {CERTIFICATE_FOLDER}")
print("=" * 72)