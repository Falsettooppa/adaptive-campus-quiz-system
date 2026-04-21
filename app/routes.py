from flask import Blueprint, render_template, session
from app.auth import login_required

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
    return render_template("lecturer/dashboard.html", user=session.get("user"))


@main.route("/admin/dashboard")
@login_required(role="admin")
def admin_dashboard():
    return render_template("admin/dashboard.html", user=session.get("user"))