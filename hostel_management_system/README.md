# HOSTEL MANAGEMENT SYSTEM — Hostel Management System

A full-stack B.Tech college project using **Python 3, Flask, Flask-SQLAlchemy, Flask-Login, Werkzeug, MySQL, HTML5, CSS3, JavaScript and Bootstrap 5**. No React, Node.js, Django or MongoDB is used.

## Features

- Public home, about, contact, login and student registration pages
- Secure password hashing with Werkzeug and session authentication with Flask-Login
- Student dashboard, profile editing, room details, fee status, complaint submission/status, and notices
- Admin dashboard with student/room/fee/complaint statistics
- Student CRUD and search by ID, name, email, course or branch
- Room CRUD, search, block and availability filters, occupancy and available-bed counts
- Room allocation and vacating; prevents a student having two active allocations and prevents over-capacity allocation
- Fee records: create, edit, delete, due dates, payment date/method, transaction/receipt ID, and status
- Complaint review and status/warden response updates
- Notice create, edit, delete and student visibility
- Responsive Bootstrap UI with Bootstrap Icons

## Requirements

- Python 3.10+
- MySQL Server 8+ (or compatible MySQL/MariaDB version)
- A browser and internet connection for Bootstrap CDN assets

## Setup (Windows)

1. **Create the MySQL database** in MySQL Workbench or the MySQL command line:

   ```sql
   CREATE DATABASE hostel_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

2. Open a terminal in this project directory and create a virtual environment:

   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Install Python packages:

   ```powershell
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and update `DATABASE_URL` with your actual MySQL username and password. Example:

   ```text
   DATABASE_URL=mysql+pymysql://root:MyStrongPassword@localhost/hostel_management?charset=utf8mb4
   SECRET_KEY=use-a-long-random-secret-value
   ADMIN_USERNAME=admin
   ADMIN_EMAIL=admin@hostel.local
   ADMIN_PASSWORD=ChangeThisAdminPassword123!
   ```

   If your MySQL password contains URL-special characters (for example `@`, `#`, `/`, or `:`), URL-encode the password in `DATABASE_URL`.

5. Create the tables and initial admin account:

   ```powershell
   flask --app app init-db
   ```

   The default admin credentials are taken from `.env`. If not changed, the development defaults are `admin` / `Admin@12345`. **Change these before using the application beyond a local demo.** The command only creates an admin if no admin user exists yet.

6. Run the app:

   ```powershell
   flask --app app run --debug
   ```

7. Open `http://127.0.0.1:5000`.

## First-use demo flow

1. Log in with the configured admin account.
2. Add rooms from **Administration → Rooms**.
3. Register students from the public registration page, or create accounts in **Manage students**. Admin-created student accounts use the entered password or `ChangeMe123!` if the password field is left blank; students should change it after first login.
4. Allocate a student to a room under **Room allocation**.
5. Add a fee record, publish a notice, and try submitting a complaint from the student account.

## Database tables

The application creates these tables through SQLAlchemy: `users`, `students`, `rooms`, `room_allocations`, `fees`, `complaints`, and `notices`. Primary keys, unique constraints, and foreign keys are defined in `app.py`. Room occupancy is derived from active allocation records so it stays consistent with allocation/vacating operations.

## Security and demo notes

- Passwords are stored as Werkzeug password hashes, never as plain text.
- Student and admin routes are protected by Flask-Login and role checks.
- The app is configured for local development. Before deployment, set a strong `SECRET_KEY`, disable debug mode, configure HTTPS, add CSRF protection (for example Flask-WTF), and review backups/permissions.
- The contact form is a UI/demo workflow and does not send email. Fee status is recorded by the administrator; no payment gateway is integrated.
- The default admin password is for local development only.
