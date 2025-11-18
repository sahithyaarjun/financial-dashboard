from flask import Flask, render_template, request
import mysql.connector
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import math
import os

app = Flask(__name__)

# ---------- DB CONFIG ----------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "abc",      # change if needed
    "database": "northwind" # make sure this exists
}

quarters = ["q1_2025", "q4_2024", "q3_2024", "q2_2024", "q1_2024"]
quarter_labels = ["Jun 2025", "Mar 2025", "Dec 2024", "Sep 2024", "Jun 2024"]


def get_connection():
    """Create and return a DB connection."""
    return mysql.connector.connect(**DB_CONFIG)


# ---------- HELPERS TO LOAD OPTIONS ----------

def get_companies():
    """Return a list of distinct company names."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT company_name FROM financials_company ORDER BY company_name")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]


def get_breakdowns():
    """Return a list of distinct breakdown values."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT breakdown FROM financials_company ORDER BY breakdown")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]


# ---------- FETCH DATA ----------

def fetch_data(companies, breakdown):
    """
    Returns dict: {company: [q1_2025, q4_2024, ...]}
    If no row for that company+breakdown, value is None.
    """
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

        # clear remaining rows (safety)
        try:
            cur.fetchall()
        except Exception:
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
    """
    Only when exactly 2 companies have data.
    Returns (company1, company2, {quarter_label: pct})
    Formula: (c1 - c2) / c2 * 100
    """
    if len(company_data) != 2:
        return None

    (c1, v1), (c2, v2) = list(company_data.items())
    pct = {}

    for label, a, b in zip(quarter_labels, v1, v2):
        try:
            pct[label] = round(((a - b) / b) * 100, 2)
        except Exception:
            pct[label] = None

    return c1, c2, pct


# ---------- CHART GENERATION ----------

def generate_chart(company_data, breakdown, chart_type="line"):
    """
    Saves chart to static/chart.png and returns the filename.
    """
    valid = {c: v for c, v in company_data.items() if v is not None}
    if not valid:
        return None

    plt.figure(figsize=(10, 6))
    colors = ["blue", "green", "red", "purple", "orange", "black"]

    if chart_type == "line":
        for idx, (company, vals) in enumerate(valid.items()):
            color = colors[idx % len(colors)]
            plt.plot(quarter_labels, vals, marker="o", linewidth=2,
                     color=color, label=company)
    else:  # bar chart
        x = range(len(quarter_labels))
        n = len(valid)
        width = 0.8 / n

        for idx, (company, vals) in enumerate(valid.items()):
            color = colors[idx % len(colors)]
            positions = [i + idx * width for i in x]
            plt.bar(positions, vals, width=width,
                    label=company, edgecolor="black", color=color)

        plt.xticks(
            [i + (n - 1)*width/2 for i in x],
            quarter_labels
        )

    plt.title(f"{breakdown} – Comparison")
    plt.xlabel("Quarter")
    plt.ylabel("Value")
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()

    os.makedirs("static", exist_ok=True)
    chart_path = os.path.join("static", "chart.png")
    plt.savefig(chart_path)
    plt.close()

    return "chart.png"


# ---------- ROUTES ----------
def build_insights(pct_info, company_values):
    """
    Turn percentage differences into human-readable sentences.
    pct_info = (c1, c2, pct_dict)
    company_values = {company: [values per quarter]}
    """
    if not pct_info or not company_values:
        return []

    c1, c2, pct = pct_info
    v1 = company_values[c1]
    v2 = company_values[c2]

    insights = []

    # Per-quarter sentences
    for i, q in enumerate(quarter_labels):
        diff = pct.get(q)
        if diff is None or (isinstance(diff, float) and math.isnan(diff)):
            insights.append(f"For {q}, comparison is not available due to missing data.")
            continue

        if diff > 0:
            insights.append(f"In {q}, {c1} is {diff}% higher than {c2}.")
        elif diff < 0:
            insights.append(f"In {q}, {c1} is {abs(diff)}% lower than {c2}.")
        else:
            insights.append(f"In {q}, {c1} and {c2} have the same value.")

    # Overall summary
    valid_percents = [v for v in pct.values() if v is not None and not math.isnan(v)]
    if valid_percents:
        avg = round(sum(valid_percents) / len(valid_percents), 2)
        if avg > 0:
            overall = f"Overall, {c1} outperformed {c2} by an average of {avg}% across the available quarters."
        elif avg < 0:
            overall = f"Overall, {c1} underperformed {c2} by an average of {abs(avg)}% across the available quarters."
        else:
            overall = f"Overall, {c1} and {c2} performed equally on average across the available quarters."
        insights.append(overall)

    return insights



# Home / Landing page
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    companies_list = get_companies()
    breakdowns_list = get_breakdowns()

    selected_companies = []
    selected_breakdown = ""
    chart_file = None
    pct_info = None
    chart_type = "line"
    message = None

    if request.method == "POST":
        selected_companies = request.form.getlist("companies")
        selected_breakdown = request.form.get("breakdown", "")
        chart_type = request.form.get("chart_type", "line")

        if not selected_companies or not selected_breakdown:
            message = "Please select at least one company and a breakdown."
        else:
            data = fetch_data(selected_companies, selected_breakdown)
            valid_data = {c: v for c, v in data.items() if v is not None}

            if not valid_data:
                message = "No matching records found in database for that selection."
            else:
                chart_file = generate_chart(valid_data, selected_breakdown, chart_type=chart_type)

                if len(valid_data) == 2:
                    pct_info = compute_percentage_diff(valid_data)

    return render_template(
        "index.html",
        companies=companies_list,
        breakdowns=breakdowns_list,
        selected_companies=selected_companies,
        selected_breakdown=selected_breakdown,
        chart_file=chart_file,
        pct_info=pct_info,
        quarter_labels=quarter_labels,
        chart_type=chart_type,
        message=message
    )


@app.route("/compare", methods=["GET", "POST"])
def compare():
    companies_list = get_companies()
    breakdowns_list = get_breakdowns()

    selected_companies = []
    selected_breakdown = ""
    message = None
    pct_info = None
    company_values = None
    insights = []

    if request.method == "POST":
        selected_companies = request.form.getlist("companies")
        selected_breakdown = request.form.get("breakdown", "")

        if len(selected_companies) != 2:
            message = "Please select exactly two companies for comparison."
        elif not selected_breakdown:
            message = "Please select a breakdown."
        else:
            data = fetch_data(selected_companies, selected_breakdown)
            valid_data = {c: v for c, v in data.items() if v is not None}

            if len(valid_data) < 2:
                message = "Not enough data found for both companies."
            else:
                pct_info = compute_percentage_diff(valid_data)
                company_values = valid_data
                insights = build_insights(pct_info, company_values)

    return render_template(
        "compare.html",
        companies=companies_list,
        breakdowns=breakdowns_list,
        selected_companies=selected_companies,
        selected_breakdown=selected_breakdown,
        pct_info=pct_info,
        quarter_labels=quarter_labels,
        message=message,
        company_values=company_values,
        insights=insights,
    )




if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
