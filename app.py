import os
import csv
import io
import hmac
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, flash, session, Response

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

PLASTIC_TYPES = [
    ("bottles", "Bottles"),
    ("sachets", "Sachets"),
    ("bags", "Bags"),
    ("straws", "Straws"),
    ("styrofoam", "Styrofoam"),
    ("other", "Other"),
]

QUANTITIES = [
    "Small (1-10 pieces)",
    "Medium (11-50 pieces)",
    "Large (51-100 pieces)",
    "Very large (100+ pieces)",
]


def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row  # lets us access columns by name
    return conn


def init_db():
    """Create the table if missing and add GPS columns to older databases."""
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT NOT NULL,
            plastic_type TEXT NOT NULL,
            quantity_estimate TEXT NOT NULL,
            status TEXT DEFAULT 'sighted',
            date_reported TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(reports)")]
    if "latitude" not in columns:
        conn.execute("ALTER TABLE reports ADD COLUMN latitude REAL")
    if "longitude" not in columns:
        conn.execute("ALTER TABLE reports ADD COLUMN longitude REAL")
    conn.commit()
    conn.close()


init_db()


@app.context_processor
def inject_globals():
    return {
        "is_admin": session.get("is_admin", False),
        "plastic_types": PLASTIC_TYPES,
        "quantities": QUANTITIES,
    }


def parse_coord(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Please log in as admin to do that.", "error")
            return redirect("/login")
        return view(*args, **kwargs)
    return wrapped


# ---------- Public pages ----------

@app.route("/")
def report_form():
    return render_template("report_form.html")


@app.route("/submit", methods=["POST"])
def submit_report():
    location = request.form["location"].strip()
    plastic_type = request.form["plastic_type"]
    quantity_estimate = request.form["quantity_estimate"]
    latitude = parse_coord(request.form.get("latitude"))
    longitude = parse_coord(request.form.get("longitude"))

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO reports (location, plastic_type, quantity_estimate, latitude, longitude) "
        "VALUES (?, ?, ?, ?, ?)",
        (location, plastic_type, quantity_estimate, latitude, longitude),
    )
    conn.commit()
    conn.close()

    flash("Report submitted successfully! Thank you for helping.", "success")
    return redirect("/")


@app.route("/reports")
def view_reports():
    conn = get_db_connection()
    reports = conn.execute("SELECT * FROM reports ORDER BY date_reported DESC").fetchall()
    conn.close()
    return render_template("view_reports.html", reports=reports)


@app.route("/map")
def reports_map():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT report_id, location, plastic_type, quantity_estimate, status, date_reported, "
        "latitude, longitude FROM reports "
        "WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    conn.close()

    pins = [dict(row) for row in rows]
    return render_template("map.html", pins=pins, unpinned=total - len(pins))


@app.route("/dashboard")
def dashboard():
    conn = get_db_connection()

    type_data = conn.execute(
        "SELECT plastic_type, COUNT(*) as total FROM reports GROUP BY plastic_type").fetchall()

    location_data = conn.execute(
        "SELECT location, COUNT(*) as total FROM reports GROUP BY location").fetchall()

    totals = conn.execute(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN status = 'cleaned' THEN 1 ELSE 0 END) AS cleaned FROM reports").fetchone()

    this_month = conn.execute(
        "SELECT COUNT(*) FROM reports "
        "WHERE strftime('%Y-%m', date_reported, '+8 hours') = strftime('%Y-%m', 'now', '+8 hours')"
    ).fetchone()[0]

    # Week starts on Monday; +8 hours converts the stored UTC time to Philippine time
    weekly = conn.execute(
        "SELECT date(date_reported, '+8 hours', 'weekday 0', '-6 days') AS period, COUNT(*) AS total "
        "FROM reports GROUP BY period ORDER BY period").fetchall()

    monthly = conn.execute(
        "SELECT strftime('%Y-%m', date_reported, '+8 hours') AS period, COUNT(*) AS total "
        "FROM reports GROUP BY period ORDER BY period").fetchall()

    conn.close()

    total = totals["total"] or 0
    cleaned = totals["cleaned"] or 0
    pending = total - cleaned
    cleanup_rate = round(cleaned / total * 100, 1) if total else 0

    return render_template("dashboard.html",
        type_labels=[row["plastic_type"] for row in type_data],
        type_values=[row["total"] for row in type_data],
        location_labels=[row["location"] for row in location_data],
        location_values=[row["total"] for row in location_data],
        total=total,
        pending=pending,
        cleaned=cleaned,
        cleanup_rate=cleanup_rate,
        this_month=this_month,
        weekly_labels=[row["period"] for row in weekly],
        weekly_values=[row["total"] for row in weekly],
        monthly_labels=[row["period"] for row in monthly],
        monthly_values=[row["total"] for row in monthly],
        zip=zip
    )


# ---------- Admin login ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("is_admin"):
        return redirect("/reports")

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user_ok = hmac.compare_digest(username.encode(), ADMIN_USERNAME.encode())
        pass_ok = hmac.compare_digest(password.encode(), ADMIN_PASSWORD.encode())
        if user_ok and pass_ok:
            session["is_admin"] = True
            flash("Welcome back, admin!", "success")
            return redirect("/reports")
        flash("Incorrect username or password.", "error")
        return redirect("/login")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("is_admin", None)
    flash("You have been logged out.", "success")
    return redirect("/")


# ---------- Admin actions ----------

@app.route("/mark_cleaned/<int:report_id>", methods=["POST"])
@admin_required
def mark_cleaned(report_id):
    conn = get_db_connection()
    conn.execute("UPDATE reports SET status = 'cleaned' WHERE report_id = ?", (report_id,))
    conn.commit()
    conn.close()
    flash("Report marked as cleaned.", "success")
    return redirect("/reports")


@app.route("/edit/<int:report_id>", methods=["GET", "POST"])
@admin_required
def edit_report(report_id):
    conn = get_db_connection()

    if request.method == "POST":
        status = request.form.get("status", "sighted")
        if status not in ("sighted", "cleaned"):
            status = "sighted"
        conn.execute(
            "UPDATE reports SET location = ?, plastic_type = ?, quantity_estimate = ?, "
            "status = ?, latitude = ?, longitude = ? WHERE report_id = ?",
            (
                request.form["location"].strip(),
                request.form["plastic_type"],
                request.form["quantity_estimate"],
                status,
                parse_coord(request.form.get("latitude")),
                parse_coord(request.form.get("longitude")),
                report_id,
            ),
        )
        conn.commit()
        conn.close()
        flash("Report updated successfully.", "success")
        return redirect("/reports")

    report = conn.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,)).fetchone()
    conn.close()

    if report is None:
        flash("Report not found.", "error")
        return redirect("/reports")

    return render_template("edit_report.html", report=report)


@app.route("/delete/<int:report_id>", methods=["POST"])
@admin_required
def delete_report(report_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM reports WHERE report_id = ?", (report_id,))
    conn.commit()
    conn.close()
    flash("Report deleted.", "success")
    return redirect("/reports")


def csv_safe(value):
    """Stop Excel from treating text like '=1+1' as a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


@app.route("/export.csv")
@admin_required
def export_csv():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT report_id, location, plastic_type, quantity_estimate, status, "
        "date_reported, latitude, longitude FROM reports ORDER BY date_reported DESC"
    ).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)