
import os
import csv
import io
import json
import sqlite3
from flask import Flask, request, jsonify, g

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 700 * 1024 * 1024

DB_PATH = os.environ.get("DB_PATH", "csv_api.db")
API_KEY = os.environ.get("API_KEY", "")

# Number of rows saved in one database batch
BATCH_SIZE = 1000


def get_db():
    if "db" not in g:
        folder = os.path.dirname(DB_PATH)
        if folder:
            os.makedirs(folder, exist_ok=True)

        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row

    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def authorized():
    return bool(API_KEY) and (
        request.headers.get("X-API-Key") == API_KEY
    )


def create_table():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL
        )
    """)
    db.commit()


@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "name": "CSV API",
        "endpoints": [
            "/api/health",
            "/admin/upload",
            "/api/count",
            "/api/records?page=1&per_page=20"
        ]
    })


@app.route("/api/health")
def health():
    return jsonify({"status": "success"})


@app.route("/admin/upload", methods=["POST"])
def upload_csv():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    if "file" not in request.files:
        return jsonify({"error": "CSV file missing"}), 400

    file = request.files["file"]

    if not file.filename.lower().endswith(".csv"):
        return jsonify({"error": "Only CSV files allowed"}), 400

    db = get_db()
    create_table()

    inserted = 0
    batch = []

    try:
        stream = io.TextIOWrapper(
            file.stream,
            encoding="utf-8-sig",
            errors="strict",
            newline=""
        )

        reader = csv.DictReader(stream)

        if not reader.fieldnames:
            return jsonify({"error": "CSV headers missing"}), 400

        headers = [
            (header or "").strip()
            for header in reader.fieldnames
        ]

        if not all(headers) or len(set(headers)) != len(headers):
            return jsonify({
                "error": "CSV headers must be non-empty and unique"
            }), 400

        for row in reader:
            clean_row = {
                headers[i]: (value or "").strip()
                for i, value in enumerate(row.values)
                if i < len(headers)
            }

            batch.append((
                json.dumps(clean_row, ensure_ascii=False),
            ))

            if len(batch) >= BATCH_SIZE:
                db.executemany(
                    "INSERT INTO records (data) VALUES (?)",
                    batch
                )
                db.commit()
                inserted += len(batch)
                batch.clear()

        if batch:
            db.executemany(
                "INSERT INTO records (data) VALUES (?)",
                batch
            )
            db.commit()
            inserted += len(batch)

        return jsonify({
            "status": "success",
            "inserted_records": inserted,
            "batch_size": BATCH_SIZE
        })

    except Exception:
        db.rollback()
        app.logger.exception("CSV import failed")
        return jsonify({
            "error": "CSV import failed. Check encoding and CSV format."
        }), 400


@app.route("/api/count")
def count_records():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    create_table()

    total = db.execute(
        "SELECT COUNT(*) FROM records"
    ).fetchone()[0]

    return jsonify({"total_records": total})


@app.route("/api/records")
def get_records():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(
            100,
            max(1, int(request.args.get("per_page", 20)))
        )
    except ValueError:
        return jsonify({"error": "Invalid page parameters"}), 400

    db = get_db()
    create_table()

    offset = (page - 1) * per_page

    rows = db.execute(
        """
        SELECT id, data
        FROM records
        ORDER BY id
        LIMIT ? OFFSET ?
        """,
        (per_page, offset)
    ).fetchall()

    return jsonify({
        "page": page,
        "per_page": per_page,
        "records": [
            {
                "id": row["id"],
                **json.loads(row["data"])
            }
            for row in rows
        ]
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
