"""app.py — minimal Flask web app around redact.py.

One page: choose file, click "Redact PII", see a summary, download the
redacted DOCX and the audit JSON. No JS framework, no database, no
background workers.
"""

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from redact import SUPPORTED_EXTENSIONS, redact_document

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB upload cap

JOB_ROOT = os.path.join(tempfile.gettempdir(), "pii_redaction_jobs")
os.makedirs(JOB_ROOT, exist_ok=True)

# In-memory job registry: job_id -> {output_path, audit_path, filename}.
# Kept simple on purpose — good enough for a single-instance student
# project; not meant to survive a process restart.
JOBS = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/redact", methods=["POST"])
def redact_endpoint():
    if "file" not in request.files or not request.files["file"].filename:
        return jsonify({"error": "No file selected."}), 400

    upload = request.files["file"]
    ext = os.path.splitext(upload.filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type '{ext}'. Use .docx, .pdf, or .txt"}), 400

    filename = secure_filename(upload.filename) or "file"
    job_id = uuid.uuid4().hex
    work_dir = os.path.join(JOB_ROOT, job_id)
    os.makedirs(work_dir, exist_ok=True)

    input_path = os.path.join(work_dir, "input" + ext)
    output_path = os.path.join(work_dir, "redacted.docx")
    audit_path = os.path.join(work_dir, "audit.json")

    upload.save(input_path)
    try:
        stats = redact_document(input_path, output_path)
    except Exception as exc:
        return jsonify({"error": f"Redaction failed: {exc}"}), 500
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)  # never keep the raw upload after processing

    audit = {
        "job_id": job_id,
        "original_filename": filename,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
    }
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2)

    JOBS[job_id] = {"output_path": output_path, "audit_path": audit_path, "filename": filename}
    return jsonify({"job_id": job_id, "filename": filename, "stats": stats}), 200


@app.route("/download/<job_id>/docx")
def download_docx(job_id):
    job = JOBS.get(job_id)
    if not job or not os.path.exists(job["output_path"]):
        return jsonify({"error": "Unknown or expired job."}), 404
    base = os.path.splitext(job["filename"])[0]
    return send_file(job["output_path"], as_attachment=True, download_name=f"{base}_REDACTED.docx")


@app.route("/download/<job_id>/audit")
def download_audit(job_id):
    job = JOBS.get(job_id)
    if not job or not os.path.exists(job["audit_path"]):
        return jsonify({"error": "Unknown or expired job."}), 404
    base = os.path.splitext(job["filename"])[0]
    return send_file(job["audit_path"], as_attachment=True, download_name=f"{base}_audit.json")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
