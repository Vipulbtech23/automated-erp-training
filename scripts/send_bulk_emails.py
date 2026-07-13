import os
import re
import glob
import time
import ssl
import smtplib
import pandas as pd

from email.message import EmailMessage


print("BULK EMAIL SYSTEM STARTED")


# =========================================================
# CONFIGURATION
# =========================================================
SENDER_EMAIL = ""
APP_PASSWORD = ""

DATA_FILE = "output/final_rankings.xlsx"

GRADECARD_DIR = "output/gradecards"
CERTIFICATE_DIR = "output/certificates"

SEND_GRADECARD = True
SEND_CERTIFICATE = True

STUDENT_PORTAL_URL = (
    "https://automated-erp-training-student.streamlit.app/"
)

LIET_WEBSITE_URL = "https://automated-erp-training-landingpage1.streamlit.app/"

DEFAULT_PASSWORD = "Lloyd@2025"

# Delay between emails to reduce Gmail rate-limit issues
EMAIL_DELAY_SECONDS = 2


# =========================================================
# VALIDATE CONFIGURATION
# =========================================================
if not SENDER_EMAIL.strip():
    raise ValueError(
        "SENDER_EMAIL is empty. Add your Gmail address."
    )

if not APP_PASSWORD.strip():
    raise ValueError(
        "APP_PASSWORD is empty. Add your Gmail App Password."
    )

if not os.path.exists(DATA_FILE):
    raise FileNotFoundError(
        f"Data file not found: {DATA_FILE}"
    )


# =========================================================
# LOAD DATA
# =========================================================
df = pd.read_excel(
    DATA_FILE,
    dtype={
        "Email": str,
        "Name": str,
        "Roll No": str,
        "Verification_ID": str
    }
)

df.columns = (
    df.columns
    .astype(str)
    .str.strip()
)


required_columns = [
    "Email",
    "Name",
    "Verification_ID"
]

missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing_columns:
    raise ValueError(
        f"Missing required columns: {missing_columns}"
    )


df["Email"] = (
    df["Email"]
    .fillna("")
    .astype(str)
    .str.strip()
    .str.lower()
)

df["Name"] = (
    df["Name"]
    .fillna("")
    .astype(str)
    .str.strip()
)

df["Verification_ID"] = (
    df["Verification_ID"]
    .fillna("")
    .astype(str)
    .str.strip()
)


# =========================================================
# HELPER FUNCTIONS
# =========================================================
def clean_text(value, default=""):
    if value is None:
        return default

    text = str(value).strip()

    if text.lower() in [
        "",
        "nan",
        "none",
        "null"
    ]:
        return default

    return text


def safe_filename(value):
    text = clean_text(
        value,
        "Student"
    )

    text = re.sub(
        r'[<>:"/\\|?*]+',
        "",
        text
    )

    text = re.sub(
        r"\s+",
        "_",
        text
    )

    return text or "Student"


def is_valid_email(email):
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

    return bool(
        re.match(
            pattern,
            email
        )
    )


# =========================================================
# FIND PDF FILE USING ACTUAL FILENAME FORMAT
# =========================================================
def find_student_pdf(
    folder,
    student_name,
    verification_id,
    document_type
):
    """
    Supported filenames:

    Shreyanshi_Yadav_LIET-MLAI-046_certificate.pdf
    Akash_Kumar_Yadav_LIET-MLAI-054_gradecard.pdf
    """

    safe_name = safe_filename(
        student_name
    )

    safe_verification_id = safe_filename(
        verification_id
    )

    expected_filename = (
        f"{safe_name}_"
        f"{safe_verification_id}_"
        f"{document_type}.pdf"
    )

    expected_path = os.path.join(
        folder,
        expected_filename
    )

    # Exact match first
    if os.path.exists(expected_path):
        return expected_path

    # Case-insensitive fallback
    search_pattern = os.path.join(
        folder,
        "*.pdf"
    )

    for file_path in glob.glob(search_pattern):

        filename = os.path.basename(
            file_path
        )

        if (
            safe_name.lower() in filename.lower()
            and safe_verification_id.lower() in filename.lower()
            and f"_{document_type}".lower() in filename.lower()
        ):
            return file_path

    # Verification ID based fallback
    for file_path in glob.glob(search_pattern):

        filename = os.path.basename(
            file_path
        )

        if (
            safe_verification_id.lower() in filename.lower()
            and f"_{document_type}".lower() in filename.lower()
        ):
            return file_path

    return None


# =========================================================
# CREATE DOCUMENT LIST FOR EMAIL
# =========================================================
def build_document_list(
    gradecard_path,
    certificate_path
):
    items = []

    if gradecard_path:
        items.append(
            f"""
            <div class="doc-item">
                <div class="doc-icon blue">📄</div>
                <div class="doc-details">
                    <div class="doc-title">
                        Performance Gradecard
                    </div>
                    <div class="doc-name">
                        {os.path.basename(gradecard_path)}
                    </div>
                </div>
            </div>
            """
        )

    if certificate_path:
        items.append(
            f"""
            <div class="doc-item">
                <div class="doc-icon gold">🏆</div>
                <div class="doc-details">
                    <div class="doc-title">
                        Training Completion Certificate
                    </div>
                    <div class="doc-name">
                        {os.path.basename(certificate_path)}
                    </div>
                </div>
            </div>
            """
        )

    return "".join(items)


# =========================================================
# SEND EMAIL
# =========================================================
def send_email(
    smtp,
    receiver_email,
    student_name,
    verification_id,
    gradecard_path=None,
    certificate_path=None
):
    attachments = []

    if (
        gradecard_path
        and os.path.exists(gradecard_path)
    ):
        attachments.append(
            gradecard_path
        )

    if (
        certificate_path
        and os.path.exists(certificate_path)
    ):
        attachments.append(
            certificate_path
        )

    if not attachments:
        print(
            f"No attachments found for {student_name}"
        )
        return False

    msg = EmailMessage()

    has_gradecard = gradecard_path is not None
    has_certificate = certificate_path is not None

    if has_gradecard and has_certificate:
        subject = (
            "🎓 Your LIET Bootcamp Gradecard & Certificate"
        )
        email_heading = (
            "Your Training Documents Are Ready"
        )
        email_subtitle = (
            "Official Gradecard and Certificate"
        )

    elif has_certificate:
        subject = (
            "🏆 Your LIET Training Certificate is Ready"
        )
        email_heading = (
            "Certificate of Completion"
        )
        email_subtitle = (
            "Official LIET Training Certificate"
        )

    else:
        subject = (
            "📄 Your LIET Bootcamp Performance Gradecard"
        )
        email_heading = (
            "Performance Gradecard"
        )
        email_subtitle = (
            "Official Bootcamp Performance Report"
        )

    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = receiver_email

    attached_file_names = "\n".join(
        f"- {os.path.basename(path)}"
        for path in attachments
    )

    plain_body = f"""
Dear {student_name},

Greetings from Lloyd Institute of Engineering & Technology.

Your LIET ML & Agentic AI Bootcamp documents have been generated successfully.

Attached Files:
{attached_file_names}

Verification ID:
{verification_id}

Student ERP Login:
Email: {receiver_email}
Password: {DEFAULT_PASSWORD}

Student ERP:
{STUDENT_PORTAL_URL}

Please download and keep these documents safely for academic, internship and placement purposes.

Regards,
LIET Bootcamp Training Team
Lloyd Institute of Engineering & Technology
Greater Noida, Uttar Pradesh

This is an automated email generated by LIET Smart ERP.
"""

    document_list_html = build_document_list(
        gradecard_path,
        certificate_path
    )

    html_body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<style>
* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    padding: 0;
    background: #eef3f8;
    font-family: Arial, Helvetica, sans-serif;
    color: #243447;
}}

.wrapper {{
    width: 100%;
    padding: 28px 12px;
}}

.container {{
    width: 100%;
    max-width: 720px;
    margin: 0 auto;
    background: #ffffff;
    border-radius: 18px;
    overflow: hidden;
    border: 1px solid #dce6ef;
    box-shadow: 0 12px 35px rgba(26, 54, 93, 0.16);
}}

.top-line {{
    height: 8px;
    background: linear-gradient(
        90deg,
        #003366,
        #0877c9,
        #00a5c8,
        #d4af37
    );
}}

.header {{
    padding: 38px 26px 32px;
    text-align: center;
    color: #ffffff;
    background: linear-gradient(
        135deg,
        #003366 0%,
        #0877c9 60%,
        #00a5c8 100%
    );
}}

.header-icon {{
    width: 72px;
    height: 72px;
    margin: 0 auto 14px;
    border-radius: 50%;
    background: rgba(255,255,255,0.18);
    border: 2px solid rgba(255,255,255,0.35);
    line-height: 72px;
    font-size: 34px;
}}

.header h1 {{
    margin: 0;
    font-size: 28px;
    line-height: 1.3;
}}

.header p {{
    margin: 9px 0 0;
    font-size: 15px;
    color: rgba(255,255,255,0.92);
}}

.college-name {{
    margin-top: 13px;
    font-size: 13px;
    font-weight: bold;
    letter-spacing: 0.4px;
}}

.content {{
    padding: 34px 36px;
}}

.greeting {{
    margin: 0 0 14px;
    color: #16324f;
    font-size: 23px;
}}

.text {{
    font-size: 15px;
    line-height: 1.8;
    color: #425466;
}}

.success-box {{
    margin: 22px 0;
    padding: 18px 20px;
    background: #eaf6ff;
    border-left: 6px solid #0877c9;
    border-radius: 12px;
}}

.success-box h3 {{
    margin: 0 0 8px;
    font-size: 17px;
    color: #17324d;
}}

.success-box p {{
    margin: 0;
    font-size: 14px;
    line-height: 1.7;
    color: #425466;
}}

.documents {{
    margin: 24px 0;
    border: 1px solid #dce6ef;
    border-radius: 14px;
    overflow: hidden;
}}

.documents-header {{
    padding: 14px 18px;
    background: #f1f6fb;
    border-bottom: 1px solid #dce6ef;
    color: #16324f;
    font-weight: bold;
}}

.documents-body {{
    padding: 8px 18px;
}}

.doc-item {{
    display: table;
    width: 100%;
    padding: 13px 0;
    border-bottom: 1px solid #edf1f5;
}}

.doc-item:last-child {{
    border-bottom: none;
}}

.doc-icon {{
    display: table-cell;
    width: 50px;
    height: 44px;
    vertical-align: middle;
    text-align: center;
    border-radius: 10px;
    font-size: 22px;
}}

.doc-icon.blue {{
    background: #eaf6ff;
}}

.doc-icon.gold {{
    background: #fff7d6;
}}

.doc-details {{
    display: table-cell;
    vertical-align: middle;
    padding-left: 14px;
}}

.doc-title {{
    font-size: 14px;
    font-weight: bold;
    color: #183b56;
}}

.doc-name {{
    margin-top: 5px;
    font-size: 12px;
    color: #6b7c93;
    word-break: break-word;
}}

.verification {{
    margin: 20px 0;
    padding: 14px 16px;
    border-radius: 10px;
    background: #f7f9fc;
    border: 1px dashed #aab8c7;
    font-size: 13px;
    color: #4a5b6b;
}}

.verification strong {{
    color: #0877c9;
}}

.login-box {{
    margin: 22px 0;
    padding: 20px;
    background: linear-gradient(
        135deg,
        #fff8e6,
        #fffdf7
    );
    border-left: 6px solid #f0a500;
    border-radius: 12px;
}}

.login-box h3 {{
    margin: 0 0 13px;
    color: #493600;
    font-size: 17px;
}}

.login-row {{
    padding: 6px 0;
    color: #4a4a4a;
    font-size: 14px;
}}

.button-wrap {{
    text-align: center;
    margin: 26px 0 12px;
}}

.button {{
    display: inline-block;
    margin: 6px;
    padding: 14px 25px;
    border-radius: 9px;
    text-decoration: none;
    font-size: 14px;
    font-weight: bold;
}}

.primary {{
    background: #0877c9;
    color: #ffffff !important;
}}

.secondary {{
    background: #ffffff;
    color: #003366 !important;
    border: 1px solid #9fb3c8;
}}

.notice {{
    margin-top: 22px;
    padding: 14px 16px;
    background: #f7f9fc;
    border-radius: 10px;
    color: #5d6b79;
    font-size: 13px;
    line-height: 1.65;
}}

.footer {{
    padding: 27px 24px;
    text-align: center;
    background: #003366;
    color: #ffffff;
}}

.footer-title {{
    font-size: 15px;
    font-weight: bold;
    margin-bottom: 7px;
}}

.footer-text {{
    font-size: 12px;
    line-height: 1.8;
    color: rgba(255,255,255,0.86);
}}

.footer-divider {{
    width: 55px;
    height: 2px;
    margin: 15px auto;
    background: #00a5c8;
}}

.auto-note {{
    font-size: 11px;
    line-height: 1.6;
    color: rgba(255,255,255,0.70);
}}

@media only screen and (max-width: 600px) {{
    .content {{
        padding: 26px 20px;
    }}

    .header {{
        padding: 30px 20px 26px;
    }}

    .header h1 {{
        font-size: 23px;
    }}

    .button {{
        display: block;
        margin: 10px 0;
    }}
}}
</style>
</head>

<body>

<div class="wrapper">

    <div class="container">

        <div class="top-line"></div>

        <div class="header">

            <div class="header-icon">🎓</div>

            <h1>{email_heading}</h1>

            <p>{email_subtitle}</p>

            <div class="college-name">
                LLOYD INSTITUTE OF ENGINEERING & TECHNOLOGY
            </div>

        </div>

        <div class="content">

            <h2 class="greeting">
                Dear {student_name},
            </h2>

            <p class="text">
                Greetings from
                <b>Lloyd Institute of Engineering & Technology,
                Greater Noida.</b>
            </p>

            <p class="text">
                Congratulations on successfully participating in the
                <b>ML & Agentic AI Bootcamp Training Programme.</b>
            </p>

            <div class="success-box">

                <h3>
                    Your official training documents are ready
                </h3>

                <p>
                    Your performance documents have been generated
                    successfully and are attached to this email.
                </p>

            </div>

            <div class="documents">

                <div class="documents-header">
                    Attached Documents
                </div>

                <div class="documents-body">

                    {document_list_html}

                </div>

            </div>

            <div class="verification">
                Verification ID:
                <strong>{verification_id}</strong>
            </div>

            <div class="login-box">

                <h3>
                    🎓 Student ERP Login Details
                </h3>

                <div class="login-row">
                    <b>Email:</b> {receiver_email}
                </div>

                <div class="login-row">
                    <b>Password:</b> {DEFAULT_PASSWORD}
                </div>

                <div class="login-row">
                    Access your dashboard, performance analytics,
                    gradecard, certificate and academic progress.
                </div>

            </div>

            <div class="button-wrap">

                <a
                    class="button primary"
                    href="{STUDENT_PORTAL_URL}"
                >
                    Open Student ERP
                </a>

                <a
                    class="button secondary"
                    href="{LIET_WEBSITE_URL}"
                >
                    Visit LIET Website
                </a>

            </div>

            <div class="notice">
                Please download and keep these documents safely for
                academic, internship and placement purposes.
            </div>

        </div>

        <div class="footer">

            <div class="footer-title">
                Lloyd Institute of Engineering & Technology
            </div>

            <div class="footer-text">
                Greater Noida, Uttar Pradesh<br>
                www.lloydcollege.in
            </div>

            <div class="footer-divider"></div>

            <div class="auto-note">
                This is an automated email generated by the
                LIET Smart ERP System.<br>
                Please do not reply directly to this email.
            </div>

        </div>

    </div>

</div>

</body>
</html>
"""

    msg.set_content(
        plain_body
    )

    msg.add_alternative(
        html_body,
        subtype="html"
    )

    for file_path in attachments:

        with open(
            file_path,
            "rb"
        ) as pdf_file:

            msg.add_attachment(
                pdf_file.read(),
                maintype="application",
                subtype="pdf",
                filename=os.path.basename(
                    file_path
                )
            )

    try:
        smtp.send_message(
            msg
        )

        print(
            f"Sent successfully: {student_name} - {receiver_email}"
        )

        for attachment in attachments:
            print(
                f"  Attached: {os.path.basename(attachment)}"
            )

        return True

    except Exception as error:
        print(
            f"Email failed for {student_name}: {error}"
        )
        return False


# =========================================================
# CONNECT TO GMAIL SMTP ONCE
# =========================================================
ssl_context = ssl.create_default_context()

success = 0
failed = 0
skipped = 0


try:

    with smtplib.SMTP_SSL(
        "smtp.gmail.com",
        465,
        context=ssl_context,
        timeout=60
    ) as smtp:

        smtp.login(
            SENDER_EMAIL,
            APP_PASSWORD
        )

        print(
            "Gmail SMTP login successful."
        )

        # =================================================
        # SEND BULK EMAILS
        # =================================================
        for _, row in df.iterrows():

            name = clean_text(
                row.get("Name", ""),
                "Student"
            )

            email = clean_text(
                row.get("Email", "")
            ).lower()

            verification_id = clean_text(
                row.get(
                    "Verification_ID",
                    ""
                )
            )

            if not email:
                print(
                    f"Skipping {name}: Email missing"
                )
                skipped += 1
                continue

            if not is_valid_email(email):
                print(
                    f"Skipping {name}: Invalid email - {email}"
                )
                skipped += 1
                continue

            if not verification_id:
                print(
                    f"Skipping {name}: Verification ID missing"
                )
                skipped += 1
                continue

            gradecard_path = None
            certificate_path = None

            if SEND_GRADECARD:

                gradecard_path = find_student_pdf(
                    folder=GRADECARD_DIR,
                    student_name=name,
                    verification_id=verification_id,
                    document_type="gradecard"
                )

                if not gradecard_path:
                    print(
                        f"Gradecard not found for {name}"
                    )

            if SEND_CERTIFICATE:

                certificate_path = find_student_pdf(
                    folder=CERTIFICATE_DIR,
                    student_name=name,
                    verification_id=verification_id,
                    document_type="certificate"
                )

                if not certificate_path:
                    print(
                        f"Certificate not found for {name}"
                    )

            sent = send_email(
                smtp=smtp,
                receiver_email=email,
                student_name=name,
                verification_id=verification_id,
                gradecard_path=gradecard_path,
                certificate_path=certificate_path
            )

            if sent:
                success += 1
            else:
                failed += 1

            time.sleep(
                EMAIL_DELAY_SECONDS
            )


except smtplib.SMTPAuthenticationError:
    print(
        "Gmail authentication failed. "
        "Use a valid Gmail App Password."
    )

except Exception as error:
    print(
        f"Bulk email system stopped: {error}"
    )


# =========================================================
# FINAL REPORT
# =========================================================
print("\n" + "=" * 65)
print("BULK EMAIL COMPLETED")
print(f"Success: {success}")
print(f"Failed: {failed}")
print(f"Skipped: {skipped}")
print("=" * 65)
