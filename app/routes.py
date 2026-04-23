from flask import Blueprint, render_template, session, request, redirect, url_for, flash
from bson import ObjectId
from app.auth import login_required
from app.db import get_db

main = Blueprint("main", __name__)


def safe_object_id(value):
    try:
        return ObjectId(value)
    except Exception:
        return None


def serialize_doc(doc):
    if doc and "_id" in doc:
        doc["id"] = str(doc["_id"])
    return doc


def get_next_question(db, course_id, answered_question_ids, current_difficulty):
    excluded_ids = []
    for qid in answered_question_ids:
        oid = safe_object_id(qid)
        if oid:
            excluded_ids.append(oid)

    query = {"course_id": str(course_id)}
    if excluded_ids:
        query["_id"] = {"$nin": excluded_ids}

    available_questions = list(db.questions.find(query))

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
    db = get_db()
    student = session.get("user")

    available_courses = list(db.courses.find())
    student_attempts = list(db.quiz_sessions.find({
        "student_id": student["id"],
        "status": "completed"
    }))

    total_attempts = len(student_attempts)
    average_score = 0

    if total_attempts > 0:
        average_score = sum(quiz.get("score", 0) for quiz in student_attempts) / total_attempts

    latest_ability = student_attempts[-1]["ability_estimate"] if student_attempts else "Beginner"

    for course in available_courses:
        serialize_doc(course)

    for attempt in student_attempts:
        serialize_doc(attempt)

    return render_template(
        "student/dashboard.html",
        user=student,
        courses=available_courses,
        attempts=student_attempts,
        total_attempts=total_attempts,
        average_score=round(average_score, 2),
        latest_ability=latest_ability
    )


@main.route("/student/quiz/start/<course_id>")
@login_required(role="student")
def start_quiz(course_id):
    db = get_db()

    course_oid = safe_object_id(course_id)
    if not course_oid:
        flash("Invalid course ID.", "error")
        return redirect(url_for("main.student_dashboard"))

    course = db.courses.find_one({"_id": course_oid})
    if not course:
        flash("Course not found.", "error")
        return redirect(url_for("main.student_dashboard"))

    course_questions = list(db.questions.find({"course_id": course_id}))
    if not course_questions:
        flash("No questions available for this course yet.", "error")
        return redirect(url_for("main.student_dashboard"))

    first_question = get_next_question(db, course_id, [], "medium")
    if not first_question:
        flash("Unable to start quiz.", "error")
        return redirect(url_for("main.student_dashboard"))

    quiz_session = {
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

    result = db.quiz_sessions.insert_one(quiz_session)
    session["active_quiz_id"] = str(result.inserted_id)

    return redirect(url_for("main.take_quiz"))


@main.route("/student/quiz", methods=["GET", "POST"])
@login_required(role="student")
def take_quiz():
    db = get_db()

    active_quiz_id = session.get("active_quiz_id")
    if not active_quiz_id:
        flash("No active quiz session found.", "error")
        return redirect(url_for("main.student_dashboard"))

    quiz_oid = safe_object_id(active_quiz_id)
    if not quiz_oid:
        flash("Invalid quiz session.", "error")
        return redirect(url_for("main.student_dashboard"))

    quiz = db.quiz_sessions.find_one({"_id": quiz_oid})
    if not quiz or quiz["status"] != "in_progress":
        flash("Quiz session is no longer active.", "error")
        return redirect(url_for("main.student_dashboard"))

    if request.method == "POST":
        question_id = request.form.get("question_id", "").strip()
        selected_option = request.form.get("selected_option", "").strip().upper()

        question_oid = safe_object_id(question_id)
        if not question_oid:
            flash("Invalid question ID.", "error")
            return redirect(url_for("main.take_quiz"))

        question = db.questions.find_one({"_id": question_oid})
        if not question:
            flash("Question not found.", "error")
            return redirect(url_for("main.take_quiz"))

        is_correct = selected_option == question["correct_option"]

        answered_questions = quiz.get("answered_questions", [])
        responses = quiz.get("responses", [])

        answered_questions.append(question_id)
        responses.append({
            "question_id": question_id,
            "question_text": question["question_text"],
            "selected_option": selected_option,
            "correct_option": question["correct_option"],
            "is_correct": is_correct,
            "explanation": question.get("explanation", ""),
            "difficulty_level": question["difficulty_level"],
            "topic": question.get("topic", "Unknown Topic")
        })

        score = quiz.get("score", 0)
        if is_correct:
            score += 1

        total_answered = len(responses)
        correct_count = sum(1 for response in responses if response["is_correct"])

        ability_estimate = estimate_ability(correct_count, total_answered)
        current_difficulty = update_difficulty(quiz["current_difficulty"], is_correct)

        course_questions = list(db.questions.find({"course_id": quiz["course_id"]}))
        max_questions = min(5, len(course_questions))

        new_status = "in_progress"
        if len(answered_questions) >= max_questions:
            new_status = "completed"

        db.quiz_sessions.update_one(
            {"_id": quiz_oid},
            {
                "$set": {
                    "answered_questions": answered_questions,
                    "responses": responses,
                    "score": score,
                    "ability_estimate": ability_estimate,
                    "current_difficulty": current_difficulty,
                    "status": new_status
                }
            }
        )

        if new_status == "completed":
            session.pop("active_quiz_id", None)
            flash("Quiz completed successfully.", "success")
            return redirect(url_for("main.quiz_result", quiz_id=active_quiz_id))

        quiz = db.quiz_sessions.find_one({"_id": quiz_oid})

    next_question = get_next_question(
        db,
        quiz["course_id"],
        quiz.get("answered_questions", []),
        quiz["current_difficulty"]
    )

    if not next_question:
        db.quiz_sessions.update_one(
            {"_id": quiz_oid},
            {"$set": {"status": "completed"}}
        )
        session.pop("active_quiz_id", None)
        return redirect(url_for("main.quiz_result", quiz_id=active_quiz_id))

    course = db.courses.find_one({"_id": safe_object_id(quiz["course_id"])})
    serialize_doc(next_question)
    if course:
        serialize_doc(course)

    total_questions = min(5, db.questions.count_documents({"course_id": quiz["course_id"]}))

    return render_template(
        "student/take_quiz.html",
        user=session.get("user"),
        quiz=quiz,
        question=next_question,
        course=course,
        question_number=len(quiz.get("responses", [])) + 1,
        total_questions=total_questions
    )


@main.route("/student/quiz/result/<quiz_id>")
@login_required(role="student")
def quiz_result(quiz_id):
    db = get_db()

    quiz_oid = safe_object_id(quiz_id)
    if not quiz_oid:
        flash("Invalid quiz result ID.", "error")
        return redirect(url_for("main.student_dashboard"))

    quiz = db.quiz_sessions.find_one({
        "_id": quiz_oid,
        "student_id": session["user"]["id"]
    })

    if not quiz:
        flash("Quiz result not found.", "error")
        return redirect(url_for("main.student_dashboard"))

    total_questions = len(quiz.get("responses", []))
    correct_answers = sum(1 for response in quiz.get("responses", []) if response["is_correct"])
    wrong_answers = total_questions - correct_answers
    percentage = round((correct_answers / total_questions) * 100, 2) if total_questions > 0 else 0

    course = db.courses.find_one({"_id": safe_object_id(quiz["course_id"])})
    if course:
        serialize_doc(course)

    db.quiz_sessions.update_one(
        {"_id": quiz_oid},
        {"$set": {"score": percentage, "status": "completed"}}
    )

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
    db = get_db()
    lecturer = session.get("user")

    lecturer_courses = list(db.courses.find({"lecturer_id": lecturer["id"]}))
    lecturer_course_ids = [str(course["_id"]) for course in lecturer_courses]

    lecturer_quiz_sessions = list(db.quiz_sessions.find({
        "course_id": {"$in": lecturer_course_ids},
        "status": "completed"
    }))

    total_courses = len(lecturer_courses)
    total_attempts = len(lecturer_quiz_sessions)

    average_score = 0
    if total_attempts > 0:
        average_score = round(
            sum(quiz.get("score", 0) for quiz in lecturer_quiz_sessions) / total_attempts,
            2
        )

    total_students = len(set(quiz["student_id"] for quiz in lecturer_quiz_sessions))

    for course in lecturer_courses:
        serialize_doc(course)

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
    db = get_db()
    lecturer = session.get("user")

    lecturer_courses = list(db.courses.find({"lecturer_id": lecturer["id"]}))
    lecturer_course_ids = [str(course["_id"]) for course in lecturer_courses]

    lecturer_quiz_sessions = list(db.quiz_sessions.find({
        "course_id": {"$in": lecturer_course_ids},
        "status": "completed"
    }))

    course_stats = []
    topic_gap_counter = {}
    student_stats = {}

    for course in lecturer_courses:
        course_id = str(course["_id"])
        course_attempts = [quiz for quiz in lecturer_quiz_sessions if quiz["course_id"] == course_id]
        attempt_count = len(course_attempts)
        participant_count = len(set(quiz["student_id"] for quiz in course_attempts))

        avg_score = 0
        if attempt_count > 0:
            avg_score = round(sum(quiz.get("score", 0) for quiz in course_attempts) / attempt_count, 2)

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
        student_stats[student_id]["scores"].append(quiz.get("score", 0))

        for response in quiz.get("responses", []):
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

    topic_gaps = [{"topic": topic, "wrong_count": count} for topic, count in topic_gap_counter.items()]
    topic_gaps.sort(key=lambda x: x["wrong_count"], reverse=True)

    total_attempts = len(lecturer_quiz_sessions)
    overall_average = round(
        sum(quiz.get("score", 0) for quiz in lecturer_quiz_sessions) / total_attempts,
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
    db = get_db()

    total_users = db.users.count_documents({})
    total_students = db.users.count_documents({"role": "student"})
    total_lecturers = db.users.count_documents({"role": "lecturer"})
    total_admins = db.users.count_documents({"role": "admin"})

    total_courses = db.courses.count_documents({})
    total_questions = db.questions.count_documents({})
    total_quiz_attempts = db.quiz_sessions.count_documents({"status": "completed"})

    completed_sessions = list(db.quiz_sessions.find({"status": "completed"}))
    overall_average = 0
    if completed_sessions:
        overall_average = round(
            sum(q.get("score", 0) for q in completed_sessions) / len(completed_sessions),
            2
        )

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
    db = get_db()
    users = list(db.users.find({}))

    for member in users:
        serialize_doc(member)

    return render_template(
        "admin/users.html",
        user=session.get("user"),
        users=users
    )


@main.route("/admin/users/<user_id>/role", methods=["POST"])
@login_required(role="admin")
def update_user_role(user_id):
    db = get_db()
    new_role = request.form.get("role", "").strip().lower()
    valid_roles = ["student", "lecturer", "admin"]

    if new_role not in valid_roles:
        flash("Invalid role selected.", "error")
        return redirect(url_for("main.admin_users"))

    user_oid = safe_object_id(user_id)
    if not user_oid:
        flash("Invalid user ID.", "error")
        return redirect(url_for("main.admin_users"))

    target_user = db.users.find_one({"_id": user_oid})
    if not target_user:
        flash("User not found.", "error")
        return redirect(url_for("main.admin_users"))

    db.users.update_one(
        {"_id": user_oid},
        {"$set": {"role": new_role}}
    )

    if "user" in session and session["user"]["id"] == user_id:
        session["user"]["role"] = new_role

    flash("User role updated successfully.", "success")
    return redirect(url_for("main.admin_users"))


@main.route("/admin/courses")
@login_required(role="admin")
def admin_courses():
    db = get_db()

    users = list(db.users.find({}))
    courses = list(db.courses.find({}))
    questions = list(db.questions.find({}))
    quiz_sessions = list(db.quiz_sessions.find({"status": "completed"}))

    lecturer_map = {str(u["_id"]): u for u in users if u["role"] in ["lecturer", "admin"]}

    enriched_courses = []
    for course in courses:
        cid = str(course["_id"])

        course_questions = [q for q in questions if q["course_id"] == cid]
        course_attempts = [q for q in quiz_sessions if q["course_id"] == cid]

        enriched_courses.append({
            "id": cid,
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
    db = get_db()

    completed_sessions = list(db.quiz_sessions.find({"status": "completed"}))
    courses = list(db.courses.find({}))

    course_reports = []
    for course in courses:
        course_id = str(course["_id"])
        course_sessions = [q for q in completed_sessions if q["course_id"] == course_id]
        participants = len(set(q["student_id"] for q in course_sessions))
        avg_score = round(sum(q.get("score", 0) for q in course_sessions) / len(course_sessions), 2) if course_sessions else 0

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
        top_students_map[sid]["scores"].append(q.get("score", 0))

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
    db = get_db()

    if request.method == "POST":
        course_code = request.form.get("course_code", "").strip().upper()
        course_title = request.form.get("course_title", "").strip()

        if not course_code or not course_title:
            flash("Course code and title are required.", "error")
            return redirect(url_for("main.create_course"))

        existing_course = db.courses.find_one({"course_code": course_code})
        if existing_course:
            flash("Course code already exists.", "error")
            return redirect(url_for("main.create_course"))

        db.courses.insert_one({
            "course_code": course_code,
            "course_title": course_title,
            "lecturer_id": session["user"]["id"]
        })

        flash("Course created successfully.", "success")
        return redirect(url_for("main.lecturer_dashboard"))

    return render_template("lecturer/create_course.html", user=session.get("user"))


@main.route("/lecturer/questions/create", methods=["GET", "POST"])
@login_required(role="lecturer")
def create_question():
    db = get_db()
    lecturer = session.get("user")

    lecturer_courses = list(db.courses.find({"lecturer_id": lecturer["id"]}))
    for course in lecturer_courses:
        serialize_doc(course)

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

        valid_course = db.courses.find_one({
            "_id": safe_object_id(course_id),
            "lecturer_id": lecturer["id"]
        })

        if not valid_course:
            flash("Invalid course selected.", "error")
            return redirect(url_for("main.create_question"))

        db.questions.insert_one({
            "course_id": course_id,
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
        })

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
    db = get_db()
    lecturer = session.get("user")

    lecturer_courses = list(db.courses.find({"lecturer_id": lecturer["id"]}))
    lecturer_course_ids = [str(course["_id"]) for course in lecturer_courses]

    lecturer_questions = list(db.questions.find({
        "course_id": {"$in": lecturer_course_ids}
    }))

    course_map = {}
    for course in lecturer_courses:
        cid = str(course["_id"])
        serialize_doc(course)
        course_map[cid] = course

    for question in lecturer_questions:
        serialize_doc(question)

    return render_template(
        "lecturer/view_questions.html",
        user=lecturer,
        questions=lecturer_questions,
        course_map=course_map
    )