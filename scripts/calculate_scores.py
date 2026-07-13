import pandas as pd
from scipy.stats import percentileofscore
import re
import os

print("🚀 CALCULATE SCORES SCRIPT STARTED")

# ================= FILE PATH =================
input_file = "output/master_performance.xlsx"
output_file = "output/final_rankings.xlsx"

# ================= CHECK INPUT FILE =================
if not os.path.exists(input_file):
    raise FileNotFoundError(
        f"❌ File not found: {input_file}\n"
        "Pehle merge_quizzes.py run karo."
    )

# ================= LOAD DATA =================
master = pd.read_excel(input_file)

# ================= CLEAN COLUMN NAMES =================
master.columns = (
    master.columns
    .astype(str)
    .str.strip()
)

print("\nColumns Found:")
print(master.columns.tolist())

# ================= REQUIRED STUDENT COLUMNS =================
required_student_cols = [
    "Email",
    "Name"
]

for column in required_student_cols:
    if column not in master.columns:
        raise ValueError(
            f"❌ Required column '{column}' master file mein nahi mili."
        )

# Roll No missing ho to create kar do
if "Roll No" not in master.columns:
    print("⚠️ Roll No column nahi mili. Blank column create ki gayi.")
    master["Roll No"] = ""

# ================= CLEAN STUDENT DATA =================
master["Email"] = (
    master["Email"]
    .fillna("")
    .astype(str)
    .str.strip()
    .str.lower()
)

master["Name"] = (
    master["Name"]
    .fillna("")
    .astype(str)
    .str.strip()
)

master["Roll No"] = (
    master["Roll No"]
    .fillna("")
    .astype(str)
    .str.strip()
    .replace({
        "nan": "",
        "None": "",
        "none": ""
    })
)

# ================= ASSESSMENT COLUMNS =================
# Sirf Assessment1 se Assessment20 columns select honge

assessment_cols = []

for number in range(1, 21):

    column_name = f"Assessment{number}"

    if column_name in master.columns:
        assessment_cols.append(column_name)

print("\nAssessment Columns Found:")
print(assessment_cols)

if len(assessment_cols) == 0:
    raise ValueError(
        "❌ Assessment1 se Assessment20 tak koi assessment column nahi mila."
    )

# Missing assessment columns information
missing_assessments = [
    f"Assessment{number}"
    for number in range(1, 21)
    if f"Assessment{number}" not in master.columns
]

if missing_assessments:
    print("\n⚠️ Missing Assessment Columns:")
    print(missing_assessments)

print(
    f"\n✅ Total Assessments Found: {len(assessment_cols)}"
)

# ================= SCORE EXTRACTION FUNCTION =================
def extract_obtained_marks(value):

    if pd.isna(value):
        return 0.0

    text = str(value).strip()

    if text == "":
        return 0.0

    if "absent" in text.lower():
        return 0.0

    # Examples handled:
    # 10
    # 10.5
    # 10/15
    # 10 / 15
    # Score: 10/15

    match = re.search(
        r"(\d+(?:\.\d+)?)",
        text
    )

    if match:
        return float(match.group(1))

    return 0.0


# ================= MAX MARKS EXTRACTION =================
def extract_max_marks(series):

    # First try formats such as 10/15
    for value in series:

        if pd.isna(value):
            continue

        text = str(value).strip()

        match = re.search(
            r"/\s*(\d+(?:\.\d+)?)",
            text
        )

        if match:
            return float(match.group(1))

    # Default maximum marks per assessment
    return 15.0


# ================= CREATE MARKS COLUMNS =================
marks_cols = []

assessment_max_marks = {}

for assessment in assessment_cols:

    marks_column = f"{assessment}_Marks"

    master[marks_column] = master[assessment].apply(
        extract_obtained_marks
    )

    marks_cols.append(marks_column)

    max_marks = extract_max_marks(
        master[assessment]
    )

    assessment_max_marks[assessment] = max_marks

    print(
        f"{assessment}: Maximum Marks = {max_marks}"
    )

# ================= TOTAL OBTAINED MARKS =================
master["Total"] = (
    master[marks_cols]
    .sum(axis=1)
    .round(2)
)

# ================= TOTAL MAXIMUM MARKS =================
max_total = sum(
    assessment_max_marks.values()
)

print(
    f"\n✅ Total Maximum Marks = {max_total}"
)

master["Max_Marks"] = max_total

# ================= PERCENTAGE =================
if max_total > 0:

    master["Percentage"] = (
        (master["Total"] / max_total) * 100
    ).round(2)

else:

    master["Percentage"] = 0.0

# Percentage maximum 100 rakho
master["Percentage"] = master["Percentage"].clip(
    lower=0,
    upper=100
)

# ================= ATTENDANCE FUNCTION =================
def is_present(value):

    if pd.isna(value):
        return False

    text = str(value).strip().lower()

    if text == "":
        return False

    if text in [
        "absent",
        "nan",
        "none",
        "na",
        "n/a"
    ]:
        return False

    return True


# ================= PRESENT ASSESSMENTS =================
master["Present_Assessments"] = (
    master[assessment_cols]
    .apply(
        lambda row: sum(
            is_present(value)
            for value in row
        ),
        axis=1
    )
)

# ================= ABSENT ASSESSMENTS =================
master["Absent_Assessments"] = (
    len(assessment_cols)
    - master["Present_Assessments"]
)

# ================= ATTENDANCE PERCENTAGE =================
master["Attendance_%"] = (
    (
        master["Present_Assessments"]
        / len(assessment_cols)
    ) * 100
).round(2)

# ================= PERCENTILE =================
if len(master) > 0:

    total_scores = master["Total"].tolist()

    master["Percentile"] = master["Total"].apply(
        lambda score: percentileofscore(
            total_scores,
            score,
            kind="rank"
        )
    ).round(2)

else:

    master["Percentile"] = 0.0

# ================= CGPA =================
master["CGPA"] = (
    master["Percentage"] / 10
).round(2)

# ================= GRADE FUNCTION =================
def calculate_grade(percentage):

    if percentage >= 90:
        return "A+"

    elif percentage >= 80:
        return "A"

    elif percentage >= 70:
        return "B+"

    elif percentage >= 60:
        return "B"

    elif percentage >= 50:
        return "C"

    elif percentage >= 40:
        return "D"

    else:
        return "F"


master["Grade"] = master["Percentage"].apply(
    calculate_grade
)

# ================= RANK =================
master["Rank"] = (
    master["Total"]
    .rank(
        ascending=False,
        method="min"
    )
    .astype(int)
)

# ================= VERIFICATION ID =================
# Rank ke according pehle sort karenge
master = master.sort_values(
    by=[
        "Rank",
        "Name"
    ],
    ascending=[
        True,
        True
    ]
).reset_index(drop=True)

master["Verification_ID"] = [
    f"LIET-MLAI-{str(index + 1).zfill(3)}"
    for index in range(len(master))
]

# ================= PERFORMANCE SUGGESTION =================
def get_suggestion(rank, percentage, attendance):

    total_students = len(master)

    top_10_percent = max(
        1,
        round(total_students * 0.10)
    )

    top_30_percent = max(
        1,
        round(total_students * 0.30)
    )

    if attendance < 50:

        return (
            "Low attendance. Attend assessments regularly "
            "and focus on completing missed evaluations."
        )

    elif rank <= top_10_percent:

        return (
            "Outstanding Performance. Excellent technical "
            "understanding and consistent assessment results."
        )

    elif rank <= top_30_percent:

        return (
            "Very Good Performance. Continue practicing "
            "advanced concepts and practical implementation."
        )

    elif percentage >= 60:

        return (
            "Good Progress. Improve consistency, revision "
            "and practical problem-solving skills."
        )

    elif percentage >= 40:

        return (
            "Average Performance. Focus on weak assessments "
            "and practise concepts regularly."
        )

    else:

        return (
            "Needs Improvement. Revise fundamental concepts, "
            "complete missed assessments and practise daily."
        )


master["Suggestion"] = master.apply(
    lambda row: get_suggestion(
        row["Rank"],
        row["Percentage"],
        row["Attendance_%"]
    ),
    axis=1
)

# ================= FINAL COLUMN ORDER =================
final_cols = [
    "Email",
    "Name",
    "Roll No"
]

# Assessment marks
final_cols.extend(marks_cols)

# Performance columns
final_cols.extend([
    "Total",
    "Max_Marks",
    "Percentage",
    "CGPA",
    "Percentile",
    "Rank",
    "Grade",
    "Verification_ID",
    "Suggestion",
    "Present_Assessments",
    "Absent_Assessments",
    "Attendance_%"
])

master = master[final_cols]

# ================= OUTPUT FOLDER =================
os.makedirs(
    "output",
    exist_ok=True
)

# ================= SAVE FINAL FILE =================
master.to_excel(
    output_file,
    index=False
)

# ================= FINAL RESULT =================
print("\n" + "=" * 70)
print("✅ SCORE CALCULATION COMPLETED SUCCESSFULLY")
print(f"✅ Created: {output_file}")
print(f"✅ Total Students: {len(master)}")
print(f"✅ Assessments Processed: {len(assessment_cols)}")
print(f"✅ Total Maximum Marks: {max_total}")

print("\nFinal Columns:")
print(master.columns.tolist())

print("\nPreview:")
print(master.head())

print("=" * 70)