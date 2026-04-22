from flask import Blueprint, render_template, session, request, redirect, url_for, flash
from app.auth import login_required, users
from app.store import courses, questions, quiz_sessions

main = Blueprint("main", __name__)


def get_next_question(course_id, answered_question_ids, current_difficulty):
    available_questions = [
        q for q in questions
        if q["course_id"] == course_id and q["id"] not in answered_question_ids
    ]

    if not available_questions:
        return None

    same_level = [q for q in available_questions if q["difficulty_level"] == current_difficulty]
    if same_level:
        return same_level[0]

    if current_difficulty == "medium":
        fallback_order = ["easy", "hard"]
    elif current_difficulty == "easy":
        fallback_order = ["medium", "hard"]
    else:
        fallback_order = ["medium", "easy"]

    for level in fallback_order:
        level_questions = [q for q in available_questions if q["difficulty_level"] == level]
        if level_questions:
            return level_questions[0]

    return available_questions[0]


def update_difficulty(current_difficulty, is_correct):
    levels = ["easy", "medium", "hard"]
    index = levels.index(current_difficulty)

    if is_correct and index < len(levels) - 1:
        return levels[index + 1]
    if not is_correct and index > 0:
        return levels[index - 1]

    return current_difficulty


def estimate_ability(correct_count, total_answered):
    if total_answered == 0:
        return "Beginner"

    percentage = (correct_count / total_answered) * 100

    if percentage >= 80:
        return "Advanced"
    elif percentage >= 50:
        return "Intermediate"
    return "Beginner"


@main.route("/")
def home():
    return render_template("index.html")


@main.route("/student/dashboard")
@login_required(role="student")
def student_dashboard():
    student = session.get("user")
    available_courses = courses

    student_attempts = [
        quiz for quiz in quiz_sessions
        if quiz["student_id"] == student["id"] and quiz["status"] == "completed"
    ]

    total_attempts = len(student_attempts)
    average_score = 0

    if total_attempts > 0:
        average_score = sum(quiz["score"] for quiz in student_attempts) / total_attempts

    latest_ability = student_attempts[-1]["ability_estimate"] if student_attempts else "Beginner"

    return render_template(
        "student/dashboard.html",
        user=student,
        courses=available_courses,
        attempts=student_attempts,
        total_attempts=total_attempts,
        average_score=round(average_score, 2),
        latest_ability=latest_ability
    )


@main.route("/student/quiz/start/<int:course_id>")
@login_required(role="student")
def start_quiz(course_id):
    course = next((c for c in courses if c["id"] == course_id), None)
    if not course:
        flash("Course not found.", "error")
        return redirect(url_for("main.student_dashboard"))

    course_questions = [q for q in questions if q["course_id"] == course_id]
    if not course_questions:
        flash("No questions available for this course yet.", "error")
        return redirect(url_for("main.student_dashboard"))

    first_question = get_next_question(course_id, [], "medium")
    if not first_question:
        flash("Unable to start quiz.", "error")
        return redirect(url_for("main.student_dashboard"))

    quiz_session = {
        "id": len(quiz_sessions) + 1,
        "student_id": session["user"]["id"],
        "student_name": session["user"]["full_name"],
        "course_id": course_id,
        "status": "in_progress",
        "current_difficulty": "medium",
        "answered_questions": [],
        "responses": [],
        "score": 0,
        "ability_estimate": "Beginner"
    }

    quiz_sessions.append(quiz_session)
    session["active_quiz_id"] = quiz_session["id"]

    return redirect(url_for("main.take_quiz"))


@main.route("/student/quiz", methods=["GET", "POST"])
@login_required(role="student")
def take_quiz():
    active_quiz_id = session.get("active_quiz_id")
    if not active_quiz_id:
        flash("No active quiz session found.", "error")
        return redirect(url_for("main.student_dashboard"))

    quiz = next((q for q in quiz_sessions if q["id"] == active_quiz_id), None)
    if not quiz or quiz["status"] != "in_progress":
        flash("Quiz session is no longer active.", "error")
        return redirect(url_for("main.student_dashboard"))

    if request.method == "POST":
        question_id = int(request.form.get("question_id"))
        selected_option = request.form.get("selected_option", "").strip().upper()

        question = next((q for q in questions if q["id"] == question_id), None)
        if not question:
            flash("Question not found.", "error")
            return redirect(url_for("main.take_quiz"))

        is_correct = selected_option == question["correct_option"]

        quiz["answered_questions"].append(question_id)
        quiz["responses"].append({
            "question_id": question_id,
            "question_text": question["question_text"],
            "selected_option": selected_option,
            "correct_option": question["correct_option"],
            "is_correct": is_correct,
            "explanation": question["explanation"],
            "difficulty_level": question["difficulty_level"],
            "topic": question["topic"]
        })

        if is_correct:
            quiz["score"] += 1

        total_answered = len(quiz["responses"])
        correct_count = sum(1 for response in quiz["responses"] if response["is_correct"])

        quiz["ability_estimate"] = estimate_ability(correct_count, total_answered)
        quiz["current_difficulty"] = update_difficulty(quiz["current_difficulty"], is_correct)

        course_questions = [q for q in questions if q["course_id"] == quiz["course_id"]]
        if len(quiz["answered_questions"]) >= min(5, len(course_questions)):
            quiz["status"] = "completed"
            session.pop("active_quiz_id", None)
            flash("Quiz completed successfully.", "success")
            return redirect(url_for("main.quiz_result", quiz_id=quiz["id"]))

    next_question = get_next_question(
        quiz["course_id"],
        quiz["answered_questions"],
        quiz["current_difficulty"]
    )

    if not next_question:
        quiz["status"] = "completed"
        session.pop("active_quiz_id", None)
        return redirect(url_for("main.quiz_result", quiz_id=quiz["id"]))

    course = next((c for c in courses if c["id"] == quiz["course_id"]), None)

    return render_template(
        "student/take_quiz.html",
        user=session.get("user"),
        quiz=quiz,
        question=next_question,
        course=course,
        question_number=len(quiz["responses"]) + 1,
        total_questions=min(5, len([q for q in questions if q["course_id"] == quiz["course_id"]]))
    )


@main.route("/student/quiz/result/<int:quiz_id>")
@login_required(role="student")
def quiz_result(quiz_id):
    quiz = next(
        (q for q in quiz_sessions if q["id"] == quiz_id and q["student_id"] == session["user"]["id"]),
        None
    )

    if not quiz:
        flash("Quiz result not found.", "error")
        return redirect(url_for("main.student_dashboard"))

    total_questions = len(quiz["responses"])
    correct_answers = sum(1 for response in quiz["responses"] if response["is_correct"])
    wrong_answers = total_questions - correct_answers
    percentage = round((correct_answers / total_questions) * 100, 2) if total_questions > 0 else 0

    course = next((c for c in courses if c["id"] == quiz["course_id"]), None)
    quiz["score"] = percentage

    return render_template(
        "student/quiz_result.html",
        user=session.get("user"),
        quiz=quiz,
        course=course,
        total_questions=total_questions,
        correct_answers=correct_answers,
        wrong_answers=wrong_answers,
        percentage=percentage
    )


@main.route("/lecturer/dashboard")
@login_required(role="lecturer")
def lecturer_dashboard():
    lecturer = session.get("user")
    lecturer_courses = [course for course in courses if course["lecturer_id"] == lecturer["id"]]
    lecturer_course_ids = [course["id"] for course in lecturer_courses]

    lecturer_quiz_sessions = [
        quiz for quiz in quiz_sessions
        if quiz["course_id"] in lecturer_course_ids and quiz["status"] == "completed"
    ]

    total_courses = len(lecturer_courses)
    total_attempts = len(lecturer_quiz_sessions)

    average_score = 0
    if total_attempts > 0:
        average_score = round(
            sum(quiz["score"] for quiz in lecturer_quiz_sessions) / total_attempts,
            2
        )

    total_students = len(set(quiz["student_id"] for quiz in lecturer_quiz_sessions))

    return render_template(
        "lecturer/dashboard.html",
        user=lecturer,
        courses=lecturer_courses,
        total_courses=total_courses,
        total_attempts=total_attempts,
        average_score=average_score,
        total_students=total_students
    )


@main.route("/lecturer/analytics")
@login_required(role="lecturer")
def lecturer_analytics():
    lecturer = session.get("user")
    lecturer_courses = [course for course in courses if course["lecturer_id"] == lecturer["id"]]
    lecturer_course_ids = [course["id"] for course in lecturer_courses]

    lecturer_quiz_sessions = [
        quiz for quiz in quiz_sessions
        if quiz["course_id"] in lecturer_course_ids and quiz["status"] == "completed"
    ]

    course_stats = []
    topic_gap_counter = {}
    student_stats = {}

    for course in lecturer_courses:
        course_attempts = [quiz for quiz in lecturer_quiz_sessions if quiz["course_id"] == course["id"]]
        attempt_count = len(course_attempts)
        participant_count = len(set(quiz["student_id"] for quiz in course_attempts))

        avg_score = 0
        if attempt_count > 0:
            avg_score = round(sum(quiz["score"] for quiz in course_attempts) / attempt_count, 2)

        course_stats.append({
            "course_code": course["course_code"],
            "course_title": course["course_title"],
            "attempt_count": attempt_count,
            "participant_count": participant_count,
            "average_score": avg_score
        })

    for quiz in lecturer_quiz_sessions:
        student_id = quiz["student_id"]

        if student_id not in student_stats:
            student_stats[student_id] = {
                "student_name": quiz.get("student_name", f"Student {student_id}"),
                "attempts": 0,
                "scores": []
            }

        student_stats[student_id]["attempts"] += 1
        student_stats[student_id]["scores"].append(quiz["score"])

        for response in quiz["responses"]:
            if not response["is_correct"]:
                topic = response.get("topic", "Unknown Topic")
                topic_gap_counter[topic] = topic_gap_counter.get(topic, 0) + 1

    student_performance = []
    for _, data in student_stats.items():
        avg = round(sum(data["scores"]) / len(data["scores"]), 2) if data["scores"] else 0
        student_performance.append({
            "student_name": data["student_name"],
            "attempts": data["attempts"],
            "average_score": avg
        })

    student_performance.sort(key=lambda x: x["average_score"], reverse=True)

    topic_gaps = [
        {"topic": topic, "wrong_count": count}
        for topic, count in topic_gap_counter.items()
    ]
    topic_gaps.sort(key=lambda x: x["wrong_count"], reverse=True)

    total_attempts = len(lecturer_quiz_sessions)
    overall_average = round(
        sum(quiz["score"] for quiz in lecturer_quiz_sessions) / total_attempts,
        2
    ) if total_attempts > 0 else 0

    total_participants = len(set(quiz["student_id"] for quiz in lecturer_quiz_sessions))

    return render_template(
        "lecturer/analytics.html",
        user=lecturer,
        course_stats=course_stats,
        student_performance=student_performance,
        topic_gaps=topic_gaps,
        total_attempts=total_attempts,
        overall_average=overall_average,
        total_participants=total_participants
    )


@main.route("/admin/dashboard")
@login_required(role="admin")
def admin_dashboard():
    total_users = len(users)
    total_students = len([u for u in users if u["role"] == "student"])
    total_lecturers = len([u for u in users if u["role"] == "lecturer"])
    total_admins = len([u for u in users if u["role"] == "admin"])

    total_courses = len(courses)
    total_questions = len(questions)
    total_quiz_attempts = len([q for q in quiz_sessions if q["status"] == "completed"])

    overall_average = 0
    completed_sessions = [q for q in quiz_sessions if q["status"] == "completed"]
    if completed_sessions:
        overall_average = round(sum(q["score"] for q in completed_sessions) / len(completed_sessions), 2)

    return render_template(
        "admin/dashboard.html",
        user=session.get("user"),
        total_users=total_users,
        total_students=total_students,
        total_lecturers=total_lecturers,
        total_admins=total_admins,
        total_courses=total_courses,
        total_questions=total_questions,
        total_quiz_attempts=total_quiz_attempts,
        overall_average=overall_average
    )


@main.route("/admin/users")
@login_required(role="admin")
def admin_users():
    return render_template(
        "admin/users.html",
        user=session.get("user"),
        users=users
    )


@main.route("/admin/users/<int:user_id>/role", methods=["POST"])
@login_required(role="admin")
def update_user_role(user_id):
    new_role = request.form.get("role", "").strip().lower()
    valid_roles = ["student", "lecturer", "admin"]

    if new_role not in valid_roles:
        flash("Invalid role selected.", "error")
        return redirect(url_for("main.admin_users"))

    target_user = next((u for u in users if u["id"] == user_id), None)
    if not target_user:
        flash("User not found.", "error")
        return redirect(url_for("main.admin_users"))

    target_user["role"] = new_role

    if "user" in session and session["user"]["id"] == user_id:
        session["user"]["role"] = new_role

    flash("User role updated successfully.", "success")
    return redirect(url_for("main.admin_users"))


@main.route("/admin/courses")
@login_required(role="admin")
def admin_courses():
    lecturer_map = {u["id"]: u for u in users if u["role"] in ["lecturer", "admin"]}

    enriched_courses = []
    for course in courses:
        course_questions = [q for q in questions if q["course_id"] == course["id"]]
        course_attempts = [q for q in quiz_sessions if q["course_id"] == course["id"] and q["status"] == "completed"]

        enriched_courses.append({
            "id": course["id"],
            "course_code": course["course_code"],
            "course_title": course["course_title"],
            "lecturer_name": lecturer_map.get(course["lecturer_id"], {}).get("full_name", "Unassigned"),
            "question_count": len(course_questions),
            "attempt_count": len(course_attempts)
        })

    return render_template(
        "admin/courses.html",
        user=session.get("user"),
        courses=enriched_courses
    )


@main.route("/admin/reports")
@login_required(role="admin")
def admin_reports():
    completed_sessions = [q for q in quiz_sessions if q["status"] == "completed"]

    course_reports = []
    for course in courses:
        course_sessions = [q for q in completed_sessions if q["course_id"] == course["id"]]
        participants = len(set(q["student_id"] for q in course_sessions))
        avg_score = round(sum(q["score"] for q in course_sessions) / len(course_sessions), 2) if course_sessions else 0

        course_reports.append({
            "course_code": course["course_code"],
            "course_title": course["course_title"],
            "participants": participants,
            "attempts": len(course_sessions),
            "average_score": avg_score
        })

    top_students_map = {}
    for q in completed_sessions:
        sid = q["student_id"]
        if sid not in top_students_map:
            top_students_map[sid] = {
                "student_name": q.get("student_name", f"Student {sid}"),
                "scores": []
            }
        top_students_map[sid]["scores"].append(q["score"])

    top_students = []
    for _, data in top_students_map.items():
        avg_score = round(sum(data["scores"]) / len(data["scores"]), 2)
        top_students.append({
            "student_name": data["student_name"],
            "average_score": avg_score
        })

    top_students.sort(key=lambda x: x["average_score"], reverse=True)

    return render_template(
        "admin/reports.html",
        user=session.get("user"),
        course_reports=course_reports,
        top_students=top_students[:10]
    )


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

        valid_course = next((course for course in lecturer_courses if str(course["id"]) == course_id), None)

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