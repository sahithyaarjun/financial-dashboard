import os
import pandas as pd
import mysql.connector

excel_folder = r"C:\Users\Sahithya Arjun\Desktop\companyexcel"

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="abc",
    database="northwind"
)
cursor = db.cursor()

def clean_numeric(x):
    if pd.isna(x) or x == "" or x == "-":
        return None
    s = str(x).strip()
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    s = s.replace(",", "")
    try:
        return float(s)
    except:
        return None

quarter_cols = ["q1_2025", "q4_2024", "q3_2024", "q2_2024", "q1_2024"]

def process_file(path):
    filename = os.path.basename(path)
    company_name = os.path.splitext(filename)[0].title()

    print(f"\n📥 Loading: {filename}")

    # Read CSV or Excel automatically
    if path.endswith(".csv"):
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)

    df.columns = [str(c).strip().lower() for c in df.columns]

    print("Detected columns:", df.columns.tolist())

    if "breakdown" not in df.columns:
        print("❌ Missing 'breakdown' column")
        return

    for q in quarter_cols:
        if q not in df.columns:
            df[q] = None

    for _, row in df.iterrows():
        breakdown = row["breakdown"]

        values = [clean_numeric(row.get(q)) for q in quarter_cols]

        cursor.execute("""
            INSERT INTO financials_company
            (company_name, breakdown, q1_2025, q4_2024, q3_2024, q2_2024, q1_2024)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (company_name, breakdown, *values))

    db.commit()
    print(f"✔ Inserted rows for {company_name}")

def main():
    print("Files found:", os.listdir(excel_folder))

    for file in os.listdir(excel_folder):
        if file.endswith(".xlsx") or file.endswith(".csv"):
            process_file(os.path.join(excel_folder, file))

    print("\n🎉 Import finished!")

main()
