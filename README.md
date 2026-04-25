# Adaptive Campus Quiz System

A smart web-based platform for adaptive quizzes, automated grading, and academic performance tracking.

## Overview

The Adaptive Campus Quiz System is designed to improve academic assessment by adjusting quiz difficulty based on each student’s performance. The system supports students, lecturers, and administrators with role-based dashboards and tools for quiz participation, question management, analytics, and institutional reporting.

## Key Features

- Student registration and login
- Role-based access for students, lecturers, and administrators
- Adaptive quiz question selection
- Automated grading
- Immediate quiz result and feedback
- Student performance tracking
- Lecturer course and question management
- Lecturer analytics dashboard
- Admin user management
- Institutional reporting
- In-app notifications
- MongoDB database persistence
- Mobile-responsive interface using Tailwind CSS

## Tech Stack

- Python
- Flask
- MongoDB Atlas
- PyMongo
- Tailwind CSS
- HTML/Jinja Templates
- Gunicorn
- Render

## User Roles

### Student
Students can register, log in, view available courses, take adaptive quizzes, receive instant feedback, and track quiz history.

### Lecturer
Lecturers can create courses, add questions, manage question banks, and view analytics on student performance and knowledge gaps.

### Administrator
Administrators can manage users, assign roles, view courses, and access institutional performance reports.

## Project Structure

```text
adaptive-campus-quiz-system/
│
├── app/
│   ├── static/
│   │   ├── css/
│   │   └── src/
│   ├── templates/
│   │   ├── admin/
│   │   ├── auth/
│   │   ├── lecturer/
│   │   ├── notifications/
│   │   ├── partials/
│   │   └── student/
│   ├── __init__.py
│   ├── auth.py
│   ├── db.py
│   └── routes.py
│
├── run.py
├── config.py
├── requirements.txt
├── package.json
├── .python-version
└── README.md
Installation
Clone the repository:
git clone https://github.com/Falsettooppa/adaptive-campus-quiz-system.gitcd adaptive-campus-quiz-system
Create and activate a virtual environment:
python -m venv venvvenv\Scripts\activate
Install Python dependencies:
pip install -r requirements.txt
Install frontend dependencies:
npm install
Build Tailwind CSS:
npm run build-css
Environment Variables
Create a .env file in the project root:
SECRET_KEY=your_secret_keyMONGO_URI=your_mongodb_atlas_connection_stringDATABASE_NAME=adaptive_quiz_db
Running Locally
python run.py
Open in your browser:
http://127.0.0.1:5000
Default Test Users
After running the app, visit:
/seed-users
This creates default users:
Admin:admin@example.comadmin123Lecturer:lecturer@example.comlecturer123
Deployment
The project is deployed using Render.
Render build command:
pip install -r requirements.txt && npm install && npm run build-css
Render start command:
gunicorn run:app
Required Render environment variables:
SECRET_KEY=your_secret_keyMONGO_URI=your_mongodb_atlas_connection_stringDATABASE_NAME=adaptive_quiz_db
Important Notes


Do not commit .env to GitHub.


Ensure MongoDB Atlas Network Access allows your deployment server.


Remove or protect /seed-users before final public release.


Make sure app/static/css/output.css is generated during deployment.


Status
This project is actively developed as a final year academic project.
