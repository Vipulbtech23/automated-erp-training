import pandas as pd
import glob
import os
import re

print("🚀 MERGE ASSESSMENTS STARTED")

# =========================================================
# SETTINGS
# =========================================================
DATA_FOLDER = "data"
OUTPUT_FOLDER = "output"
OUTPUT_FILE = "output/master_performance.xlsx"
TOTAL_ASSESSMENTS = 20

# =========================================================
# GET CSV FILES
# =========================================================
files = glob.glob(
    os.path.join(DATA_FOLDER, "*.csv")
)

if len(files) == 0:
    raise FileNotFoundError(
        "❌ data folder mein koi CSV file nahi mili."
    )


# =========================================================
# GET ASSESSMENT NUMBER FROM FILE NAME
# =========================================================
def get_assessment_number(file_path):

    filename = os.path.splitext(
        os.path.basename(file_path)
    )[0]

    # Supports:
    # Assessment 1.csv
    # Assessment1.csv
    # Assessment_1.csv
    # Assessment-1.csv
    match = re.search(
        r"(\d+)",
        filename
    )

    if not match:
        raise ValueError(
            f"❌ Assessment number file name mein nahi mila: {filename}"
        )

    assessment_number = int(
        match.group(1)
    )

    if assessment_number < 1 or assessment_number > TOTAL_ASSESSMENTS:
        raise ValueError(
            f"❌ Assessment number 1 se {TOTAL_ASSESSMENTS} "
            f"ke beech hona chahiye: {filename}"
        )

    return assessment_number


# =========================================================
# SORT FILES ASSESSMENT NUMBER-WISE
# =========================================================
files.sort(
    key=get_assessment_number
)

print("\nFiles Found:")

for file in files:
    print(
        f"Assessment {get_assessment_number(file)} -> "
        f"{os.path.basename(file)}"
    )


# =========================================================
# NORMALIZE COLUMN NAME
# =========================================================
def normalize_column_name(column_name):

    column_name = str(
        column_name
    ).strip().lower()

    # Remove spaces and special characters
    column_name = re.sub(
        r"[^a-z0-9]+",
        "",
        column_name
    )

    return column_name


# =========================================================
# COLUMN ALIASES
# =========================================================
COLUMN_ALIASES = {

    "Email": [
        "email",
        "emailaddress",
        "emailid",
        "studentemail",
        "studentemailaddress"
    ],

    "Name": [
        "name",
        "studentname",
        "fullname",
        "studentfullname"
    ],

    "Roll No": [
        "rollno",
        "rollnumber",
        "rollnum",
        "studentrollno",
        "studentrollnumber",
        "universityrollno",
        "universityrollnumber",
        "enrollmentno",
        "enrollmentnumber",
        "registrationno",
        "registrationnumber",
        "admissionno",
        "admissionnumber"
    ],

    "Total score": [
        "totalscore",
        "score",
        "marks",
        "totalmarks",
        "points",
        "obtainedmarks"
    ]
}


# =========================================================
# FIND ACTUAL COLUMN
# =========================================================
def find_column(df, standard_name):

    normalized_columns = {
        normalize_column_name(column): column
        for column in df.columns
    }

    for alias in COLUMN_ALIASES[standard_name]:

        normalized_alias = normalize_column_name(
            alias
        )

        if normalized_alias in normalized_columns:
            return normalized_columns[
                normalized_alias
            ]

    return None


# =========================================================
# CLEAN ROLL NUMBER
# =========================================================
def clean_roll_number(value):

    if pd.isna(value):
        return ""

    value = str(
        value
    ).strip()

    if value.lower() in [
        "",
        "nan",
        "none",
        "null",
        "na",
        "n/a"
    ]:
        return ""

    # Remove Excel apostrophe
    value = value.lstrip("'")

    # Remove unnecessary spaces
    value = re.sub(
        r"\s+",
        "",
        value
    )

    # Remove trailing .0
    value = re.sub(
        r"\.0$",
        "",
        value
    )

    # Convert scientific notation
    # Example: 2.3015300123E+10
    if re.fullmatch(
        r"\d+(\.\d+)?[eE][+-]?\d+",
        value
    ):
        try:
            value = format(
                float(value),
                ".0f"
            )
        except ValueError:
            pass

    return value


# =========================================================
# CLEAN EMAIL
# =========================================================
def clean_email(value):

    if pd.isna(value):
        return ""

    value = str(
        value
    ).strip().lower()

    if value in [
        "",
        "nan",
        "none"
    ]:
        return ""

    return value


# =========================================================
# CLEAN NAME
# =========================================================
def clean_name(value):

    if pd.isna(value):
        return ""

    value = str(
        value
    ).strip()

    if value.lower() in [
        "",
        "nan",
        "none"
    ]:
        return ""

    return value


# =========================================================
# CLEAN SCORE
# =========================================================
def clean_score(value):

    if pd.isna(value):
        return ""

    value = str(
        value
    ).strip()

    if value.lower() in [
        "",
        "nan",
        "none"
    ]:
        return ""

    return value


# =========================================================
# STUDENT DETAIL MAPS
# =========================================================
# Email ke basis par latest valid Name aur Roll No save honge.

roll_number_map = {}
name_map = {}

master = None
processed_assessments = []


# =========================================================
# PROCESS EACH CSV
# =========================================================
for file in files:

    assessment_number = get_assessment_number(
        file
    )

    assessment_column = (
        f"Assessment{assessment_number}"
    )

    print("\n" + "=" * 70)
    print(f"📖 Reading: {file}")
    print(f"📌 Assessment Number: {assessment_number}")

    # =====================================================
    # READ CSV AS TEXT
    # =====================================================
    try:

        df = pd.read_csv(
            file,
            dtype=str,
            keep_default_na=False,
            encoding="utf-8-sig"
        )

    except UnicodeDecodeError:

        df = pd.read_csv(
            file,
            dtype=str,
            keep_default_na=False,
            encoding="latin1"
        )

    # =====================================================
    # CLEAN COLUMN NAMES
    # =====================================================
    df.columns = [
        str(column).strip()
        for column in df.columns
    ]

    print("\nAvailable Columns:")
    print(df.columns.tolist())

    # =====================================================
    # FIND REQUIRED COLUMNS
    # =====================================================
    email_column = find_column(
        df,
        "Email"
    )

    name_column = find_column(
        df,
        "Name"
    )

    roll_column = find_column(
        df,
        "Roll No"
    )

    score_column = find_column(
        df,
        "Total score"
    )

    print("\nDetected Columns:")
    print("Email Column:", email_column)
    print("Name Column:", name_column)
    print("Roll No Column:", roll_column)
    print("Score Column:", score_column)

    # =====================================================
    # CHECK REQUIRED COLUMNS
    # =====================================================
    missing_columns = []

    if email_column is None:
        missing_columns.append("Email")

    if name_column is None:
        missing_columns.append("Name")

    if score_column is None:
        missing_columns.append("Total score")

    if missing_columns:
        raise ValueError(
            f"\n❌ Missing columns in {file}: {missing_columns}\n"
            f"Available columns: {df.columns.tolist()}"
        )

    # =====================================================
    # RENAME TO STANDARD NAMES
    # =====================================================
    rename_mapping = {
        email_column: "Email",
        name_column: "Name",
        score_column: "Total score"
    }

    if roll_column is not None:
        rename_mapping[
            roll_column
        ] = "Roll No"

    df.rename(
        columns=rename_mapping,
        inplace=True
    )

    # If Roll No not detected
    if "Roll No" not in df.columns:

        print(
            "⚠️ Roll No column detect nahi hui. "
            "Blank Roll No column create ki ja rahi hai."
        )

        df["Roll No"] = ""

    # =====================================================
    # KEEP ONLY REQUIRED COLUMNS
    # =====================================================
    df = df[
        [
            "Email",
            "Name",
            "Roll No",
            "Total score"
        ]
    ].copy()

    # =====================================================
    # CLEAN VALUES
    # =====================================================
    df["Email"] = df["Email"].apply(
        clean_email
    )

    df["Name"] = df["Name"].apply(
        clean_name
    )

    df["Roll No"] = df["Roll No"].apply(
        clean_roll_number
    )

    df["Total score"] = df[
        "Total score"
    ].apply(
        clean_score
    )

    # =====================================================
    # REMOVE BLANK EMAIL ROWS
    # =====================================================
    blank_email_count = (
        df["Email"] == ""
    ).sum()

    if blank_email_count > 0:

        print(
            f"⚠️ {blank_email_count} blank email rows remove ki gayi."
        )

        df = df[
            df["Email"] != ""
        ].copy()

    # =====================================================
    # REMOVE DUPLICATE EMAILS IN SAME CSV
    # =====================================================
    duplicate_count = df.duplicated(
        subset=["Email"],
        keep="last"
    ).sum()

    if duplicate_count > 0:

        print(
            f"⚠️ {duplicate_count} duplicate emails mile. "
            "Last record rakha gaya."
        )

        df = df.drop_duplicates(
            subset=["Email"],
            keep="last"
        )

    # =====================================================
    # DEBUG ROLL NUMBER PREVIEW
    # =====================================================
    print("\nRoll Number Preview:")

    print(
        df[
            [
                "Name",
                "Email",
                "Roll No"
            ]
        ].head(15).to_string(index=False)
    )

    # =====================================================
    # SAVE LATEST VALID NAME AND ROLL NUMBER
    # =====================================================
    for _, student_row in df.iterrows():

        student_email = clean_email(
            student_row["Email"]
        )

        student_name = clean_name(
            student_row["Name"]
        )

        student_roll = clean_roll_number(
            student_row["Roll No"]
        )

        if student_email:

            if student_name:
                name_map[
                    student_email
                ] = student_name

            if student_roll:
                roll_number_map[
                    student_email
                ] = student_roll

    # =====================================================
    # RENAME SCORE COLUMN
    # =====================================================
    df.rename(
        columns={
            "Total score": assessment_column
        },
        inplace=True
    )

    print(
        f"\n✅ Created Column: {assessment_column}"
    )

    print(
        f"✅ Students Found: {len(df)}"
    )

    processed_assessments.append(
        assessment_number
    )

    # =====================================================
    # MERGE
    # =====================================================
    if master is None:

        master = df.copy()

    else:

        master = pd.merge(
            master,
            df,
            on="Email",
            how="outer",
            suffixes=("_old", "_new")
        )

        # =================================================
        # MERGE NAME
        # =================================================
        old_name = (
            master["Name_old"]
            .apply(clean_name)
            .replace("", pd.NA)
        )

        new_name = (
            master["Name_new"]
            .apply(clean_name)
            .replace("", pd.NA)
        )

        # Latest CSV name gets priority
        master["Name"] = (
            new_name
            .combine_first(old_name)
            .fillna("")
        )

        # =================================================
        # MERGE ROLL NUMBER
        # =================================================
        old_roll = (
            master["Roll No_old"]
            .apply(clean_roll_number)
            .replace("", pd.NA)
        )

        new_roll = (
            master["Roll No_new"]
            .apply(clean_roll_number)
            .replace("", pd.NA)
        )

        # Latest valid Roll No gets priority
        master["Roll No"] = (
            new_roll
            .combine_first(old_roll)
            .fillna("")
        )

        master.drop(
            columns=[
                "Name_old",
                "Name_new",
                "Roll No_old",
                "Roll No_new"
            ],
            inplace=True
        )


# =========================================================
# CREATE ALL ASSESSMENT COLUMNS
# =========================================================
for assessment_number in range(
    1,
    TOTAL_ASSESSMENTS + 1
):

    assessment_column = (
        f"Assessment{assessment_number}"
    )

    if assessment_column not in master.columns:

        print(
            f"⚠️ {assessment_column} file nahi mili. "
            "Absent column create kiya gaya."
        )

        master[
            assessment_column
        ] = "Absent"


# =========================================================
# APPLY FINAL CORRECT STUDENT DETAILS
# =========================================================
master["Email"] = master[
    "Email"
].apply(
    clean_email
)

master["Name"] = master.apply(
    lambda row: name_map.get(
        row["Email"],
        clean_name(row["Name"])
    ),
    axis=1
)

master["Roll No"] = master.apply(
    lambda row: roll_number_map.get(
        row["Email"],
        clean_roll_number(
            row["Roll No"]
        )
    ),
    axis=1
)


# =========================================================
# ASSESSMENT COLUMNS
# =========================================================
assessment_columns = [
    f"Assessment{number}"
    for number in range(
        1,
        TOTAL_ASSESSMENTS + 1
    )
]


# =========================================================
# FILL ABSENT VALUES
# =========================================================
for column in assessment_columns:

    master[column] = (
        master[column]
        .replace("", pd.NA)
        .fillna("Absent")
    )


# =========================================================
# FINAL COLUMN ORDER
# =========================================================
final_columns = [
    "Email",
    "Name",
    "Roll No"
] + assessment_columns

master = master[
    final_columns
]


# =========================================================
# SORT STUDENTS
# =========================================================
master = master.sort_values(
    by=[
        "Roll No",
        "Name"
    ],
    na_position="last"
).reset_index(drop=True)


# =========================================================
# SAVE OUTPUT
# =========================================================
os.makedirs(
    OUTPUT_FOLDER,
    exist_ok=True
)

master.to_excel(
    OUTPUT_FILE,
    index=False
)


# =========================================================
# FINAL RESULT
# =========================================================
print("\n" + "=" * 70)
print("✅ MASTER FILE CREATED SUCCESSFULLY")
print(f"✅ Saved: {OUTPUT_FILE}")
print(f"✅ Total Students: {len(master)}")

print(
    f"✅ Processed Assessments: "
    f"{sorted(processed_assessments)}"
)

missing_assessments = [
    number
    for number in range(
        1,
        TOTAL_ASSESSMENTS + 1
    )
    if number not in processed_assessments
]

if missing_assessments:

    print(
        f"⚠️ Missing Assessment Files: "
        f"{missing_assessments}"
    )

else:

    print(
        "✅ All 20 assessment files found."
    )

print("\nFinal Roll Number Preview:")

print(
    master[
        [
            "Name",
            "Email",
            "Roll No"
        ]
    ].head(30).to_string(index=False)
)

print("\nFinal Columns:")
print(master.columns.tolist())

print("=" * 70)