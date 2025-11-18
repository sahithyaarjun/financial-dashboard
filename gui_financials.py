import mysql.connector
import matplotlib.pyplot as plt
import math
import tkinter as tk
from tkinter import ttk, messagebox

# ---------- DB CONFIG ----------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "abc",
    "database": "northwind"
}

quarters = ["q1_2025", "q4_2024", "q3_2024", "q2_2024", "q1_2024"]
quarter_labels = ["Jun 2025", "Mar 2025", "Dec 2024", "Sep 2024", "Jun 2024"]


# ---------- BASIC DB CONNECTION ----------
def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


# ---------- LOAD COMPANIES ----------
def load_companies():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT company_name FROM financials_company ORDER BY company_name")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]


# ---------- LOAD BREAKDOWNS ----------
def load_breakdowns():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT breakdown FROM financials_company ORDER BY breakdown")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]


# ---------- FETCH DATA FOR COMPANIES ----------
def fetch_data(companies, breakdown):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    data = {}

    for c in companies:
        cur.execute(
            """
            SELECT * FROM financials_company
            WHERE LOWER(company_name)=LOWER(%s)
              AND LOWER(breakdown)=LOWER(%s)
            """,
            (c, breakdown)
        )

        row = cur.fetchone()

        # Clear unread results ALWAYS
        try:
            cur.fetchall()
        except:
            pass

        if row:
            data[c] = [row[q] if row[q] is not None else float("nan") for q in quarters]
        else:
            data[c] = None

    cur.close()
    conn.close()
    return data


# ---------- PERCENTAGE DIFFERENCE ----------
def compute_percentage_diff(company_data):
    if len(company_data) != 2:
        return None

    (c1, v1), (c2, v2) = list(company_data.items())
    pct = {}

    for label, a, b in zip(quarter_labels, v1, v2):
        try:
            pct[label] = round(((a - b) / b) * 100, 2)
        except:
            pct[label] = None

    return c1, c2, pct


# ---------- PLOT GRAPH ----------
def plot_chart(company_data, breakdown, chart_type="line"):
    plt.figure(figsize=(12, 7))
    colors = ["blue", "green", "red", "purple", "orange", "black"]

    valid = [c for c, v in company_data.items() if v is not None]

    if not valid:
        messagebox.showwarning("No Data", "No matching records found in database.")
        return

    if chart_type == "line":
        for idx, company in enumerate(valid):
            vals = company_data[company]
            color = colors[idx % len(colors)]
            plt.plot(quarter_labels, vals, marker="o", linewidth=2,
                     color=color, label=company)

            # Value labels
            for q, y in zip(quarter_labels, vals):
                if y is not None and not math.isnan(y):
                    plt.text(q, y + (y * 0.02), f"{int(y)}",
                             color=color, fontsize=9, ha="center")

    else:  # BAR GRAPH
        x = range(len(quarter_labels))
        n = len(valid)
        width = 0.8 / n

        for idx, company in enumerate(valid):
            vals = company_data[company]
            color = colors[idx % len(colors)]
            positions = [i + idx * width for i in x]

            plt.bar(positions, vals, width=width, color=color,
                    label=company, edgecolor="black")

            # Value labels
            for xp, y in zip(positions, vals):
                if y is not None and not math.isnan(y):
                    plt.text(xp, y + (y * 0.02), f"{int(y)}",
                             ha="center", fontsize=8)

        plt.xticks([i + (n - 1)*width/2 for i in x], quarter_labels)

    plt.title(f"{breakdown} – Comparison", fontsize=14)
    plt.xlabel("Quarter")
    plt.ylabel("Value")
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()
    plt.show()


# ---------- GUI SHOW BUTTON ----------
def on_show():
    selection = company_listbox.curselection()

    if not selection:
        messagebox.showerror("Error", "Please select at least 1 company.")
        return

    companies = [company_listbox.get(i) for i in selection]
    breakdown = breakdown_var.get()

    if not breakdown:
        messagebox.showerror("Error", "Please select a breakdown.")
        return

    chart_type = chart_type_var.get()

    data = fetch_data(companies, breakdown)

    print("\n=== RAW DATA ===")
    for c, vals in data.items():
        print(c, ":", vals)

    # % DIFF when 2 companies ONLY
    if len(companies) == 2 and all(data[c] is not None for c in companies):
        c1, c2, pct = compute_percentage_diff(
            {companies[0]: data[companies[0]], companies[1]: data[companies[1]]}
        )

        print(f"\n% DIFFERENCE ({c1} vs {c2}):")
        for q, v in pct.items():
            print(f"{q}: {v}%")

    else:
        print("\n(% difference only shown when exactly 2 companies have data.)")

    plot_chart(data, breakdown, chart_type=chart_type)


# ---------- GUI INTERFACE ----------
root = tk.Tk()
root.title("Financial Comparison Tool")
root.geometry("900x500")


# Companies List
tk.Label(root, text="Select Companies (Ctrl+Click):").grid(row=0, column=0, padx=10, pady=5, sticky="w")

company_listbox = tk.Listbox(root, selectmode=tk.MULTIPLE, height=12, width=30)
company_listbox.grid(row=1, column=0, padx=10, pady=5, sticky="w")

for comp in load_companies():
    company_listbox.insert(tk.END, comp)


# Breakdown Dropdown
tk.Label(root, text="Select Breakdown:").grid(row=0, column=1, padx=10, pady=5, sticky="w")

breakdown_var = tk.StringVar()
breakdown_combo = ttk.Combobox(root, textvariable=breakdown_var, width=50)
breakdown_combo.grid(row=1, column=1, padx=10, pady=5)


# Reload breakdowns when clicked
def refresh_breakdowns(event):
    breakdown_combo['values'] = load_breakdowns()


breakdown_combo.bind("<Button-1>", refresh_breakdowns)


# Chart Type
chart_type_var = tk.StringVar(value="line")

tk.Label(root, text="Chart Type:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
tk.Radiobutton(root, text="Line Chart", variable=chart_type_var, value="line").grid(row=3, column=0, sticky="w", padx=10)
tk.Radiobutton(root, text="Bar Chart", variable=chart_type_var, value="bar").grid(row=4, column=0, sticky="w", padx=10)


# Show Button
show_btn = tk.Button(root, text="Show Chart", command=on_show, width=20, height=2)
show_btn.grid(row=3, column=1, padx=10, pady=20, sticky="w")


root.mainloop()
