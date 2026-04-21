from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

auth = Blueprint("auth", __name__)

# Temporary in-memory users store
users = [
    {
        "id": 1,
        "full_name": "System Administrator",
        "matric_number": None,
        "email": "admin@example.com",
        "password_hash": generate_password_hash("admin123"),
        "role": "admin"
    },
    {
        "id": 2,
        "full_name": "Dr. John Lecturer",
        "matric_number": None,
        "email": "lecturer@example.com",
        "password_hash": generate_password_hash("lecturer123"),
        "role": "lecturer"
    }
]


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


@auth.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        matric_number = request.form.get("matric_number", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not full_name or not matric_number or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("auth.register"))

        existing_user = next((user for user in users if user["email"] == email), None)
        if existing_user:
            flash("Email already exists.", "error")
            return redirect(url_for("auth.register"))

        hashed_password = generate_password_hash(password)

        new_user = {
            "id": len(users) + 1,
            "full_name": full_name,
            "matric_number": matric_number,
            "email": email,
            "password_hash": hashed_password,
            "role": "student"
        }

        users.append(new_user)

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        user = next((user for user in users if user["email"] == email), None)

        if user and check_password_hash(user["password_hash"], password):
            session["user"] = {
                "id": user["id"],
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
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))