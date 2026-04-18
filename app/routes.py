from flask import Blueprint, render_template
from app.db import get_db

main = Blueprint("main", __name__)

@main.route("/")
def home():
    return render_template("index.html")

@main.route("/test-db")
def test_db():
    db = get_db()

    user_count = db.users.count_documents({})
    course_count = db.courses.count_documents({})
    question_count = db.questions.count_documents({})

    return {
        "message": "MongoDB connection successful",
        "users": user_count,
        "courses": course_count,
        "questions": question_count
    }