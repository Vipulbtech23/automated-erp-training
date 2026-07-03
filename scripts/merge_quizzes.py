import pandas as pd
import glob
import os

print("🚀 MERGE QUIZZES STARTED")

# ================= GET FILES =================
files = glob.glob("data/*.csv")
files.sort(key=os.path.getmtime)

print("\nFiles Found:")
for f in files:
    print(os.path.basename(f))

if len(files) == 0:
    print("❌ No CSV files found!")
    exit()

master = None

# ================= TRAINING MODULE MAPPING =================
MODULES = {
    "Quiz1": "Python Fundamentals",
    "Quiz2": "NumPy & Pandas",
    "Quiz3": "Data Visualization",
    "Quiz4": "Machine Learning",
    "Quiz5": "Deep Learning",
    "Quiz6": "Agentic AI"
}

# ================= PROCESS FILES =================
for file in files:

    print(f"\nReading: {file}")

    df = pd.read_csv(file)

    # ================= CLEAN COLUMN NAMES =================
    df.columns = df.columns.str.strip()

    required_cols = ["Email", "Name", "Total score"]

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(
                f"Missing column '{col}' in {file}"
            )

    df = df[required_cols].copy()

    # ================= CLEAN DATA =================
    df["Email"] = (
        df["Email"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df["Name"] = (
        df["Name"]
        .astype(str)
        .str.strip()
    )

    # ================= QUIZ NAME =================
    filename = os.path.basename(file).replace(".csv", "")

    # Example:
    # Quiz1_15_6_26
    quiz_number = filename.split("_")[0]

    module_name = MODULES.get(
        quiz_number,
        quiz_number
    )

    column_name = f"{quiz_number}_{module_name}"

    df.rename(
        columns={
            "Total score": column_name
        },
        inplace=True
    )

    print(f"Created Column: {column_name}")

    # ================= MERGE =================
    if master is None:

        master = df

    else:

        master = pd.merge(
            master,
            df,
            on=["Email", "Name"],
            how="outer"
        )

# ================= ABSENT STUDENTS =================
quiz_cols = [
    c for c in master.columns
    if c not in ["Email", "Name"]
]

for c in quiz_cols:
    master[c] = master[c].fillna("Absent")

# ================= SAVE =================
os.makedirs("output", exist_ok=True)

output_file = "output/master_performance.xlsx"

master.to_excel(
    output_file,
    index=False
)

print("\n✅ MASTER FILE CREATED")
print("Saved:", output_file)

print("\nColumns:")
print(master.columns.tolist())

print("\nPreview:")
print(master.head())