import pandas as pd
from scipy.stats import percentileofscore

print("SCRIPT STARTED")

# ================= LOAD =================
master = pd.read_excel("output/master_performance.xlsx")

# ================= CLEAN COLUMNS =================
master.columns = master.columns.str.strip()

# ================= QUIZ COLUMNS =================
quiz_cols = [
    c for c in master.columns
    if c not in ["Email", "Name"]
]

print("\nQuiz Columns Found:")
print(quiz_cols)

# ================= EXTRACT MARKS =================
for c in quiz_cols:

    master[c + "_Marks"] = (
        master[c]
        .astype(str)
        .str.extract(r"(\d+\.?\d*)")[0]
    )

    master[c + "_Marks"] = pd.to_numeric(
        master[c + "_Marks"],
        errors="coerce"
    ).fillna(0)

# ================= MARKS COLUMNS =================
marks_cols = [c + "_Marks" for c in quiz_cols]

# ================= TOTAL =================
master["Total"] = master[marks_cols].sum(axis=1)

# ================= MAX MARKS =================
max_total = 0

for c in quiz_cols:

    max_marks = (
        master[c]
        .astype(str)
        .str.extract(r"/\s*(\d+\.?\d*)")[0]
    )

    max_marks = pd.to_numeric(
        max_marks,
        errors="coerce"
    )

    if max_marks.notna().any():
        max_total += max_marks.dropna().iloc[0]

# fallback
if max_total == 0:
    max_total = len(quiz_cols) * 15

print("\nMaximum Marks =", max_total)

# Save for gradecard
master["Max_Marks"] = max_total

# ================= PERCENTAGE =================
master["Percentage"] = round(
    (master["Total"] / max_total) * 100,
    2
)

# ================= ATTENDANCE =================
master["Present_Quizzes"] = (
    master[quiz_cols]
    .astype(str)
    .apply(
        lambda x: ~x.str.contains(
            "Absent",
            case=False,
            na=False
        )
    )
    .sum(axis=1)
)

master["Absent_Quizzes"] = (
    len(quiz_cols)
    - master["Present_Quizzes"]
)

master["Attendance_%"] = round(
    (master["Present_Quizzes"] / len(quiz_cols)) * 100,
    2
)

# ================= PERCENTILE =================
master["Percentile"] = master["Total"].apply(
    lambda x: percentileofscore(
        master["Total"],
        x,
        kind="rank"
    )
)

master["Percentile"] = round(
    master["Percentile"],
    2
)

# ================= CGPA =================
master["CGPA"] = round(
    (master["Percentage"] / 100) * 10,
    2
)

# ================= GRADE =================
def grade(p):

    if p >= 90:
        return "A+"
    elif p >= 80:
        return "A"
    elif p >= 70:
        return "B"
    elif p >= 60:
        return "C"
    elif p >= 50:
        return "D"
    else:
        return "F"

master["Grade"] = master["Percentage"].apply(grade)

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
master["Verification_ID"] = [
    f"LIET-MLAI-{str(i+1).zfill(3)}"
    for i in range(len(master))
]

# ================= SUGGESTION =================
def get_suggestion(rank, percentage):

    total_students = len(master)

    top10 = max(1, int(total_students * 0.10))
    top30 = max(1, int(total_students * 0.30))

    if rank <= top10:
        return (
            "Outstanding Performance. "
            "Excellent leadership and technical skills."
        )

    elif rank <= top30:
        return (
            "Very Good Performance. "
            "Continue working on advanced concepts."
        )

    elif percentage >= 60:
        return (
            "Good Progress. "
            "Improve consistency and practical implementation."
        )

    else:
        return (
            "Needs Improvement. "
            "Focus on revision and regular practice."
        )

master["Suggestion"] = master.apply(
    lambda x: get_suggestion(
        x["Rank"],
        x["Percentage"]
    ),
    axis=1
)

# ================= FINAL COLUMN ORDER =================
final_cols = [
    "Email",
    "Name"
]

final_cols.extend(marks_cols)

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
    "Present_Quizzes",
    "Absent_Quizzes",
    "Attendance_%"
])

master = master[final_cols]

# ================= SAVE =================
master.to_excel(
    "output/final_rankings.xlsx",
    index=False
)

print("\nSUCCESS")
print("Created: output/final_rankings.xlsx")

print("\nFinal Columns:")
print(master.columns.tolist())

print("\nPreview:")
print(master.head())