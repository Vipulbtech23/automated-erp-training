import os
import pandas as pd
from pathlib import Path
from scripts.send_email import Emailer

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = BASE_DIR / "output" / "final_rankings.xlsx"
GRADECARD_DIR = BASE_DIR / "output" / "gradecards"
CERTIFICATE_DIR = BASE_DIR / "output" / "certificates"


def safe_name(name):
    return str(name).strip().replace(" ", "_")


def email_updated_reports(sender_email, app_password, send_gradecard=True, send_certificate=True):
    if not DATA_FILE.exists():
        print("final_rankings.xlsx not found")
        return False

    df = pd.read_excel(DATA_FILE)
    df.columns = df.columns.str.strip()

    df["Email"] = df["Email"].astype(str).str.strip().str.lower()
    df["Name"] = df["Name"].astype(str).str.strip()

    emailer = Emailer(sender_email, app_password)

    success = 0
    failed = 0

    for _, row in df.iterrows():
        name = row["Name"]
        email = row["Email"]

        if not email or email == "nan":
            print(f"Skipping {name}: invalid email")
            failed += 1
            continue

        if send_gradecard:
            gradecard_path = GRADECARD_DIR / f"{safe_name(name)}_gradecard.pdf"

            if gradecard_path.exists():
                sent = emailer.send_pdf(
                    email,
                    str(gradecard_path),
                    name,
                    "Updated Gradecard"
                )

                success += 1 if sent else 0
                failed += 0 if sent else 1
            else:
                print(f"Gradecard missing for {name}")
                failed += 1

        if send_certificate:
            certificate_path = CERTIFICATE_DIR / f"{safe_name(name)}_certificate.pdf"

            if certificate_path.exists():
                sent = emailer.send_pdf(
                    email,
                    str(certificate_path),
                    name,
                    "Certificate"
                )

                success += 1 if sent else 0
                failed += 0 if sent else 1
            else:
                print(f"Certificate missing for {name}")
                failed += 1

    print("Bulk Email Completed")
    print("Success:", success)
    print("Failed:", failed)

    return True


if __name__ == "__main__":
    sender = os.getenv("LIET_EMAIL")
    password = os.getenv("LIET_EMAIL_PASSWORD")

    if not sender or not password:
        print("Missing LIET_EMAIL or LIET_EMAIL_PASSWORD environment variables")
    else:
        email_updated_reports(sender, password)