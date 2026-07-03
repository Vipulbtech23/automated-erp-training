import pandas as pd
from datetime import datetime
import os

FILE = "data/attendance.csv"

def init_file():
    if not os.path.exists(FILE):
        df = pd.DataFrame(columns=["StudentID", "Date", "Time", "Status"])
        df.to_csv(FILE, index=False)

def mark_attendance(student_id):
    init_file()

    df = pd.read_csv(FILE)

    today = datetime.now().strftime("%Y-%m-%d")
    time = datetime.now().strftime("%H:%M:%S")

    # prevent duplicate entry
    if not ((df["StudentID"] == student_id) & (df["Date"] == today)).any():

        new_row = {
            "StudentID": student_id,
            "Date": today,
            "Time": time,
            "Status": "Present"
        }

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_csv(FILE, index=False)

        return True

    return False