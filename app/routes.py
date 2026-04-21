from flask import Blueprint, render_template, session, request, redirect, url_for, flash
from app.auth import login_required
from app.store import courses, questions

main = Blueprint("main", __name__)


@main.route("/")
def home():
    return render_template("index.html")


@main.route("/student/dashboard")
@login_required(role="student")
def student_dashboard():
    return render_template("student/dashboard.html", user=session.get("user"))


@main.route("/lecturer/dashboard")
@login_required(role="lecturer")
def lecturer_dashboard():
    lecturer = session.get("user")
    lecturer_courses = [course for course in courses if course["lecturer_id"] == lecturer["id"]]
    return render_template(
        "lecturer/dashboard.html",
        user=lecturer,
        courses=lecturer_courses
    )


@main.route("/admin/dashboard")
@login_required(role="admin")
def admin_dashboard():
    return render_template("admin/dashboard.html", user=session.get("user"))


@main.route("/lecturer/courses/create", methods=["GET", "POST"])
@login_required(role="lecturer")
def create_course():
    if request.method == "POST":
        course_code = request.form.get("course_code", "").strip().upper()
        course_title = request.form.get("course_title", "").strip()

        if not course_code or not course_title:
            flash("Course code and title are required.", "error")
            return redirect(url_for("main.create_course"))

        existing_course = next((course for course in courses if course["course_code"] == course_code), None)
        if existing_course:
            flash("Course code already exists.", "error")
            return redirect(url_for("main.create_course"))

        new_course = {
            "id": len(courses) + 1,
            "course_code": course_code,
            "course_title": course_title,
            "lecturer_id": session["user"]["id"]
        }

        courses.append(new_course)
        flash("Course created successfully.", "success")
        return redirect(url_for("main.lecturer_dashboard"))

    return render_template("lecturer/create_course.html", user=session.get("user"))


@main.route("/lecturer/questions/create", methods=["GET", "POST"])
@login_required(role="lecturer")
def create_question():
    lecturer = session.get("user")
    lecturer_courses = [course for course in courses if course["lecturer_id"] == lecturer["id"]]

    if request.method == "POST":
        course_id = request.form.get("course_id", "").strip()
        topic = request.form.get("topic", "").strip()
        difficulty_level = request.form.get("difficulty_level", "").strip().lower()
        question_text = request.form.get("question_text", "").strip()
        option_a = request.form.get("option_a", "").strip()
        option_b = request.form.get("option_b", "").strip()
        option_c = request.form.get("option_c", "").strip()
        option_d = request.form.get("option_d", "").strip()
        correct_option = request.form.get("correct_option", "").strip().upper()
        explanation = request.form.get("explanation", "").strip()

        if not all([course_id, topic, difficulty_level, question_text, option_a, option_b, option_c, option_d, correct_option]):
            flash("All required fields must be filled.", "error")
            return redirect(url_for("main.create_question"))

        valid_course = next(
            (course for course in lecturer_courses if str(course["id"]) == course_id),
            None
        )

        if not valid_course:
            flash("Invalid course selected.", "error")
            return redirect(url_for("main.create_question"))

        if correct_option not in ["A", "B", "C", "D"]:
            flash("Correct option must be A, B, C, or D.", "error")
            return redirect(url_for("main.create_question"))

        new_question = {
            "id": len(questions) + 1,
            "course_id": int(course_id),
            "topic": topic,
            "difficulty_level": difficulty_level,
            "question_text": question_text,
            "option_a": option_a,
            "option_b": option_b,
            "option_c": option_c,
            "option_d": option_d,
            "correct_option": correct_option,
            "explanation": explanation,
            "lecturer_id": lecturer["id"]
        }

        questions.append(new_question)
        flash("Question added successfully.", "success")
        return redirect(url_for("main.view_questions"))

    return render_template(
        "lecturer/create_question.html",
        user=lecturer,
        courses=lecturer_courses
    )


@main.route("/lecturer/questions")
@login_required(role="lecturer")
def view_questions():
    lecturer = session.get("user")
    lecturer_courses = [course for course in courses if course["lecturer_id"] == lecturer["id"]]
    lecturer_course_ids = [course["id"] for course in lecturer_courses]

    lecturer_questions = [
        question for question in questions
        if question["course_id"] in lecturer_course_ids
    ]

    course_map = {course["id"]: course for course in lecturer_courses}

    return render_template(
        "lecturer/view_questions.html",
        user=lecturer,
        questions=lecturer_questions,
        course_map=course_map
    )