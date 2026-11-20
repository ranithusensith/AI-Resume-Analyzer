import os
import re
import tempfile

from flask import Flask, render_template, request
from PyPDF2 import PdfReader
from docx import Document
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB upload limit

ALLOWED_EXTENSIONS = {".pdf", ".docx"}

TECH_SKILLS = [
    "python", "java", "javascript", "html", "css", "sql", "mysql",
    "flask", "django", "react", "git", "github", "c++", "c#",
]


# ---------- Text extraction ----------

def extract_pdf_text(path):
    text = ""
    reader = PdfReader(path)
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text


def extract_docx_text(path):
    doc = Document(path)
    return "\n".join(para.text for para in doc.paragraphs)


# ---------- Analysis ----------

def extract_skills(text):
    found = []
    for skill in TECH_SKILLS:
        # Whole-word match, so "java" won't match "javascript"
        # and "git" won't match "github"
        pattern = r"(?<![\w+#])" + re.escape(skill) + r"(?![\w+#])"
        if re.search(pattern, text, re.IGNORECASE):
            found.append(skill.title())
    return found


def analyze_resume(text):
    text = text.lower()
    score = 0
    sections = {
        "skills": "skills" in text,
        "education": "education" in text,
        "experience": "experience" in text,
        "projects": "project" in text,
    }
    for present in sections.values():
        if present:
            score += 25
    return score, sections


def generate_feedback(sections):
    feedback = []
    messages = {
        "skills": ("Skills section detected", "Add a dedicated skills section."),
        "education": ("Education section detected", "Include your education details."),
        "experience": ("Experience section detected", "Add work experience or internships."),
        "projects": ("Projects section detected", "Include relevant projects."),
    }
    for section, (found_msg, missing_msg) in messages.items():
        feedback.append(found_msg if sections[section] else missing_msg)
    return feedback


def get_resume_statistics(text, skills):
    return {
        "word_count": len(text.split()),
        "skills_count": len(skills),
    }


def get_rating(score):
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    return "Needs Improvement"


# ---------- Routes ----------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("resume")
    if not file or file.filename == "":
        return "No file selected.", 400

    # Sanitize the filename to prevent path traversal (e.g. "../../app.py")
    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return "Only PDF and DOCX files are supported.", 400

    # Process in a temp folder that is deleted automatically,
    # so uploaded resumes are never stored on the server
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, filename)
        file.save(path)
        try:
            if ext == ".pdf":
                text = extract_pdf_text(path)
            else:
                text = extract_docx_text(path)
        except Exception:
            return "Could not read this file. Please upload a valid PDF or DOCX.", 400

    if not text.strip():
        return "No text found. Scanned (image-only) PDFs are not supported yet.", 400

    score, sections = analyze_resume(text)
    feedback = generate_feedback(sections)
    skills = extract_skills(text)
    stats = get_resume_statistics(text, skills)

    return render_template(
        "result.html",
        score=score,
        rating=get_rating(score),
        feedback=feedback,
        skills=skills,
        stats=stats,
    )


@app.errorhandler(413)
def file_too_large(error):
    return "File too large. Maximum size is 5 MB.", 413


if __name__ == "__main__":
    # Debug mode only when explicitly enabled: FLASK_DEBUG=1 python3 app.py
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
