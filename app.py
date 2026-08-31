from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row # lets us access columns by name
    return conn

@app.route("/")
def report_form():
    return render_template("report_form.html")

@app.route("/submit", methods=["POST"])
def submit_report():
    location = request.form["location"]
    plastic_type = request.form["plastic_type"]
    quantity_estimate = request.form["quantity_estimate"]

    conn = get_db_connection()
    conn.execute("INSERT INTO reports (location, plastic_type, quantity_estimate) VALUES (?, ?, ?)",
    (location, plastic_type, quantity_estimate))
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/reports")
def view_reports():
    conn = get_db_connection()
    reports = conn.execute("SELECT * FROM reports ORDER BY date_reported DESC").fetchall()
    conn.close()
    return render_template("view_reports.html", reports=reports)

@app.route("/mark_cleaned/<int:report_id>")
def mark_cleaned(report_id):
    conn = get_db_connection()
    conn.execute("UPDATE reports SET status = 'cleaned' WHERE report_id = ?", (report_id,))
    conn.commit()
    conn.close()
    return redirect("/reports")

@app.route("/dashboard")
def dashboard():
    conn = get_db_connection()

    type_data = conn.execute(
    "SELECT plastic_type, COUNT(*) as total FROM reports GROUP BY plastic_type").fetchall()

    location_data = conn.execute(
    "SELECT location, COUNT(*) as total FROM reports GROUP BY location").fetchall()

    conn.close()

    type_labels = [row["plastic_type"] for row in type_data]
    type_values = [row["total"] for row in type_data]

    location_labels = [row["location"] for row in location_data]
    location_values = [row["total"] for row in location_data]

    return render_template("dashboard.html",
        type_labels=type_labels,
        type_values=type_values,
        location_labels=location_labels,
        location_values=location_values)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=500)