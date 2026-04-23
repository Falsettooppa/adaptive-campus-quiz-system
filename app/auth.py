from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from app.db import get_db

auth = Blueprint("auth", __name__)


def login_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if "user" not in session:
                flash("Please log in first.", "error")
                return redirect(url_for("auth.login"))

            if role and session["user"]["role"] != role:
                flash("You do not have permission to access this page.", "error")
                return redirect(url_for("main.home"))

            return view(*args, **kwargs)
        return wrapped_view
    return decorator


@auth.route("/seed-users")
def seed_users():
    db = get_db()

    admin_exists = db.users.find_one({"email": "admin@example.com"})
    lecturer_exists = db.users.find_one({"email": "lecturer@example.com"})

    if not admin_exists:
        result = db.users.insert_one({
            "full_name": "System Administrator",
            "matric_number": None,
            "email": "admin@example.com",
            "password_hash": generate_password_hash("admin123"),
            "role": "admin"
        })

        db.notifications.insert_one({
            "user_id": str(result.inserted_id),
            "title": "Welcome",
            "message": "Your admin account has been created successfully.",
            "is_read": False
        })

    if not lecturer_exists:
        result = db.users.insert_one({
            "full_name": "Dr. John Lecturer",
            "matric_number": None,
            "email": "lecturer@example.com",
            "password_hash": generate_password_hash("lecturer123"),
            "role": "lecturer"
        })

        db.notifications.insert_one({
            "user_id": str(result.inserted_id),
            "title": "Welcome",
            "message": "Your lecturer account has been created successfully.",
            "is_read": False
        })

    flash("Default users seeded successfully.", "success")
    return redirect(url_for("auth.login"))


@auth.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        db = get_db()

        full_name = request.form.get("full_name", "").strip()
        matric_number = request.form.get("matric_number", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not full_name or not matric_number or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("auth.register"))

        existing_user = db.users.find_one({"email": email})
        if existing_user:
            flash("Email already exists.", "error")
            return redirect(url_for("auth.register"))

        new_user = {
            "full_name": full_name,
            "matric_number": matric_number,
            "email": email,
            "password_hash": generate_password_hash(password),
            "role": "student"
        }

        result = db.users.insert_one(new_user)

        db.notifications.insert_one({
            "user_id": str(result.inserted_id),
            "title": "Welcome",
            "message": "Your student account has been created successfully.",
            "is_read": False
        })

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        db = get_db()

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        user = db.users.find_one({"email": email})

        if user and check_password_hash(user["password_hash"], password):
            session["user"] = {
                "id": str(user["_id"]),
                "full_name": user["full_name"],
                "email": user["email"],
                "role": user["role"]
            }

            flash("Login successful.", "success")

            if user["role"] == "student":
                return redirect(url_for("main.student_dashboard"))
            elif user["role"] == "lecturer":
                return redirect(url_for("main.lecturer_dashboard"))
            elif user["role"] == "admin":
                return redirect(url_for("main.admin_dashboard"))

            return redirect(url_for("main.home"))

        flash("Invalid email or password.", "error")
        return redirect(url_for("auth.login"))

    return render_template("auth/login.html")


@auth.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("active_quiz_id", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))