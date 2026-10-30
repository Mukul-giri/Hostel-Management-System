import os
from datetime import datetime, date
from functools import wraps

import click
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, or_
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'change-this-secret-key-before-deployment')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 'mysql+pymysql://root:your_mysql_password@localhost/hostel_management?charset=utf8mb4'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    student = db.relationship('Student', back_populates='user', uselist=False, cascade='all, delete-orphan')

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password, raw_password)


class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    student_id = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(25))
    gender = db.Column(db.String(20))
    course = db.Column(db.String(80))
    branch = db.Column(db.String(80))
    year = db.Column(db.Integer)
    address = db.Column(db.Text)
    guardian_name = db.Column(db.String(120))
    guardian_phone = db.Column(db.String(25))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', back_populates='student')
    allocations = db.relationship('RoomAllocation', back_populates='student', cascade='all, delete-orphan')
    fees = db.relationship('Fee', back_populates='student', cascade='all, delete-orphan')
    complaints = db.relationship('Complaint', back_populates='student', cascade='all, delete-orphan')

    @property
    def active_allocation(self):
        return RoomAllocation.query.filter_by(student_id=self.id, status='Active').first()


class Room(db.Model):
    __tablename__ = 'rooms'
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(20), unique=True, nullable=False)
    block = db.Column(db.String(60), nullable=False)
    floor = db.Column(db.Integer, default=0)
    room_type = db.Column(db.String(40), default='Double')
    capacity = db.Column(db.Integer, nullable=False, default=2)
    status = db.Column(db.String(20), nullable=False, default='Available')
    allocations = db.relationship('RoomAllocation', back_populates='room')

    @property
    def active_allocations(self):
        return RoomAllocation.query.filter_by(room_id=self.id, status='Active').count()

    @property
    def occupied(self):
        return self.active_allocations

    @property
    def available_beds(self):
        return max(0, self.capacity - self.occupied)

    @property
    def live_status(self):
        if self.available_beds == 0:
            return 'Full'
        return 'Available'


class RoomAllocation(db.Model):
    __tablename__ = 'room_allocations'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id', ondelete='RESTRICT'), nullable=False)
    allocation_date = db.Column(db.Date, default=date.today, nullable=False)
    vacate_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='Active', nullable=False)
    student = db.relationship('Student', back_populates='allocations')
    room = db.relationship('Room', back_populates='allocations')


class Fee(db.Model):
    __tablename__ = 'fees'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(db.Date)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='Pending', nullable=False)
    payment_method = db.Column(db.String(40))
    transaction_id = db.Column(db.String(100))
    student = db.relationship('Student', back_populates='fees')


class Complaint(db.Model):
    __tablename__ = 'complaints'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    subject = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default='Pending', nullable=False)
    admin_response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    student = db.relationship('Student', back_populates='complaints')


class Notice(db.Model):
    __tablename__ = 'notices'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    creator = db.relationship('User')


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                flash('You do not have permission to view that page.', 'danger')
                return redirect(url_for('dashboard'))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def student_profile_or_404():
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        abort(404, description='Student profile not found for this account.')
    return student


def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, '%Y-%m-%d').date()


@app.context_processor
def inject_globals():
    return {'today': date.today()}


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        flash('Thank you for contacting the hostel office. This demo does not send email automatically.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        name = request.form.get('name', '').strip()
        student_id = request.form.get('student_id', '').strip()
        if not all([username, email, password, name, student_id]):
            flash('Please fill all required fields.', 'danger')
        elif len(password) < 8:
            flash('Password must contain at least 8 characters.', 'danger')
        elif User.query.filter(or_(User.username == username, User.email == email)).first():
            flash('Username or email is already registered.', 'danger')
        elif Student.query.filter_by(student_id=student_id).first():
            flash('That student ID is already registered.', 'danger')
        else:
            user = User(username=username, email=email, role='student')
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            student = Student(user_id=user.id, student_id=student_id, name=name, email=email,
                              phone=request.form.get('phone', '').strip(), course=request.form.get('course', '').strip(),
                              branch=request.form.get('branch', '').strip(), year=int(request.form['year']) if request.form.get('year', '').isdigit() else None)
            db.session.add(student)
            db.session.commit()
            flash('Registration successful. You can now log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter(or_(User.username == identifier, User.email == identifier.lower())).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Welcome back!', 'success')
            next_url = request.args.get('next')
            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect(url_for('dashboard'))
        flash('Invalid username/email or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))


@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    student = student_profile_or_404()
    allocation = student.active_allocation
    fees = Fee.query.filter_by(student_id=student.id).order_by(Fee.due_date.desc()).all()
    complaints = Complaint.query.filter_by(student_id=student.id).order_by(Complaint.created_at.desc()).limit(5).all()
    notices = Notice.query.order_by(Notice.created_at.desc()).limit(5).all()
    pending_fees = sum(1 for fee in fees if fee.status != 'Paid')
    pending_complaints = Complaint.query.filter_by(student_id=student.id, status='Pending').count()
    return render_template('student_dashboard.html', student=student, allocation=allocation, fees=fees,
                           complaints=complaints, notices=notices, pending_fees=pending_fees,
                           pending_complaints=pending_complaints)


@app.route('/profile', methods=['GET', 'POST'])
@role_required('student')
def profile():
    student = student_profile_or_404()
    if request.method == 'POST':
        student.name = request.form.get('name', '').strip()
        student.phone = request.form.get('phone', '').strip()
        student.gender = request.form.get('gender', '').strip()
        student.course = request.form.get('course', '').strip()
        student.branch = request.form.get('branch', '').strip()
        student.year = int(request.form['year']) if request.form.get('year', '').isdigit() else None
        student.address = request.form.get('address', '').strip()
        student.guardian_name = request.form.get('guardian_name', '').strip()
        student.guardian_phone = request.form.get('guardian_phone', '').strip()
        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', student=student)


@app.route('/my-room')
@role_required('student')
def my_room():
    student = student_profile_or_404()
    allocation = student.active_allocation
    return render_template('my_room.html', student=student, allocation=allocation)


@app.route('/my-fees')
@role_required('student')
def my_fees():
    student = student_profile_or_404()
    fees = Fee.query.filter_by(student_id=student.id).order_by(Fee.due_date.desc()).all()
    return render_template('my_fees.html', fees=fees)


@app.route('/complaints', methods=['GET', 'POST'])
@role_required('student')
def student_complaints():
    student = student_profile_or_404()
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        description = request.form.get('description', '').strip()
        if subject and description:
            db.session.add(Complaint(student_id=student.id, subject=subject, description=description))
            db.session.commit()
            flash('Complaint submitted successfully.', 'success')
            return redirect(url_for('student_complaints'))
        flash('Subject and description are required.', 'danger')
    complaints = Complaint.query.filter_by(student_id=student.id).order_by(Complaint.created_at.desc()).all()
    return render_template('student_complaints.html', complaints=complaints)


@app.route('/notices')
@login_required
def student_notices():
    notices = Notice.query.order_by(Notice.created_at.desc()).all()
    return render_template('notices.html', notices=notices)


@app.route('/admin')
@role_required('admin')
def admin_dashboard():
    total_students = Student.query.count()
    total_rooms = Room.query.count()
    all_rooms = Room.query.all()
    occupied_rooms = sum(1 for room in all_rooms if room.occupied > 0)
    available_rooms = sum(1 for room in all_rooms if room.available_beds > 0)
    pending_fees = db.session.query(func.coalesce(func.sum(Fee.amount), 0)).filter(Fee.status != 'Paid').scalar()
    pending_complaints = Complaint.query.filter_by(status='Pending').count()
    recent_complaints = Complaint.query.order_by(Complaint.created_at.desc()).limit(5).all()
    return render_template('admin_dashboard.html', total_students=total_students, total_rooms=total_rooms,
                           occupied_rooms=occupied_rooms, available_rooms=available_rooms,
                           pending_fees=pending_fees, pending_complaints=pending_complaints,
                           recent_complaints=recent_complaints)


# ---------- Admin: student management ----------
@app.route('/admin/students')
@role_required('admin')
def manage_students():
    q = request.args.get('q', '').strip()
    query = Student.query.join(User)
    if q:
        pattern = f'%{q}%'
        query = query.filter(or_(Student.student_id.ilike(pattern), Student.name.ilike(pattern),
                                 Student.email.ilike(pattern), Student.course.ilike(pattern), Student.branch.ilike(pattern)))
    students = query.order_by(Student.name).all()
    return render_template('admin_students.html', students=students, q=q)


@app.route('/admin/students/add', methods=['GET', 'POST'])
@app.route('/admin/students/<int:student_id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def student_form(student_id=None):
    student = db.session.get(Student, student_id) if student_id else None
    if student_id and not student:
        abort(404)
    if request.method == 'POST':
        student_id_value = request.form.get('student_id', '').strip()
        email = request.form.get('email', '').strip().lower()
        username = request.form.get('username', '').strip()
        if not all([student_id_value, email, request.form.get('name', '').strip()]):
            flash('Student ID, name, and email are required.', 'danger')
        elif Student.query.filter(Student.student_id == student_id_value, Student.id != (student.id if student else 0)).first():
            flash('Student ID already exists.', 'danger')
        else:
            if not student:
                if not username:
                    username = student_id_value
                if User.query.filter(or_(User.username == username, User.email == email)).first():
                    flash('Username or email already exists.', 'danger')
                    return render_template('student_form.html', student=student)
                user = User(username=username, email=email, role='student')
                user.set_password(request.form.get('password') or 'ChangeMe123!')
                db.session.add(user)
                db.session.flush()
                student = Student(user_id=user.id, student_id=student_id_value, name=request.form.get('name').strip(), email=email)
                db.session.add(student)
            else:
                student.student_id = student_id_value
                student.email = email
                student.user.email = email
                student.user.username = username or student.user.username
                if request.form.get('password'):
                    student.user.set_password(request.form['password'])
                student.name = request.form.get('name', '').strip()
            student.phone = request.form.get('phone', '').strip()
            student.gender = request.form.get('gender', '').strip()
            student.course = request.form.get('course', '').strip()
            student.branch = request.form.get('branch', '').strip()
            student.year = int(request.form['year']) if request.form.get('year', '').isdigit() else None
            student.address = request.form.get('address', '').strip()
            student.guardian_name = request.form.get('guardian_name', '').strip()
            student.guardian_phone = request.form.get('guardian_phone', '').strip()
            db.session.commit()
            flash('Student saved successfully.', 'success')
            return redirect(url_for('manage_students'))
    return render_template('student_form.html', student=student)


@app.route('/admin/students/<int:student_id>/delete', methods=['POST'])
@role_required('admin')
def delete_student(student_id):
    student = db.session.get(Student, student_id) or abort(404)
    for allocation in student.allocations:
        if allocation.status == 'Active':
            allocation.status = 'Vacated'
            allocation.vacate_date = date.today()
    db.session.delete(student.user)
    db.session.commit()
    flash('Student and login account deleted.', 'success')
    return redirect(url_for('manage_students'))


# ---------- Admin: room management ----------
@app.route('/admin/rooms')
@role_required('admin')
def manage_rooms():
    q = request.args.get('q', '').strip()
    block = request.args.get('block', '').strip()
    availability = request.args.get('availability', '').strip()
    query = Room.query
    if q:
        query = query.filter(or_(Room.room_number.ilike(f'%{q}%'), Room.block.ilike(f'%{q}%')))
    if block:
        query = query.filter_by(block=block)
    rooms = query.order_by(Room.block, Room.room_number).all()
    if availability == 'available':
        rooms = [r for r in rooms if r.available_beds > 0]
    elif availability == 'full':
        rooms = [r for r in rooms if r.available_beds == 0]
    blocks = [r[0] for r in db.session.query(Room.block).distinct().order_by(Room.block).all()]
    return render_template('admin_rooms.html', rooms=rooms, q=q, block=block, availability=availability, blocks=blocks)


@app.route('/admin/rooms/add', methods=['GET', 'POST'])
@app.route('/admin/rooms/<int:room_id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def room_form(room_id=None):
    room = db.session.get(Room, room_id) if room_id else None
    if room_id and not room:
        abort(404)
    if request.method == 'POST':
        number = request.form.get('room_number', '').strip()
        capacity = int(request.form.get('capacity', 0) or 0)
        existing = Room.query.filter(Room.room_number == number, Room.id != (room.id if room else 0)).first()
        if not number or not request.form.get('block', '').strip() or capacity < 1:
            flash('Room number, block, and a positive capacity are required.', 'danger')
        elif existing:
            flash('Room number already exists.', 'danger')
        elif room and capacity < room.occupied:
            flash('Capacity cannot be lower than current occupancy.', 'danger')
        else:
            if not room:
                room = Room(room_number=number, block=request.form.get('block').strip(), capacity=capacity)
                db.session.add(room)
            room.room_number = number
            room.block = request.form.get('block').strip()
            room.floor = int(request.form.get('floor', 0) or 0)
            room.room_type = request.form.get('room_type', 'Double')
            room.capacity = capacity
            db.session.commit()
            flash('Room saved successfully.', 'success')
            return redirect(url_for('manage_rooms'))
    return render_template('room_form.html', room=room)


@app.route('/admin/rooms/<int:room_id>/delete', methods=['POST'])
@role_required('admin')
def delete_room(room_id):
    room = db.session.get(Room, room_id) or abort(404)
    if room.occupied:
        flash('Vacate all students before deleting this room.', 'danger')
    else:
        db.session.delete(room)
        db.session.commit()
        flash('Room deleted.', 'success')
    return redirect(url_for('manage_rooms'))


# ---------- Admin: room allocation ----------
@app.route('/admin/allocations', methods=['GET', 'POST'])
@role_required('admin')
def manage_allocations():
    if request.method == 'POST':
        student = db.session.get(Student, int(request.form.get('student_id', 0)))
        room = db.session.get(Room, int(request.form.get('room_id', 0)))
        if not student or not room:
            flash('Choose a valid student and room.', 'danger')
        elif student.active_allocation:
            flash('This student already has an active room allocation.', 'danger')
        elif room.available_beds < 1:
            flash('This room is full. Allocation was not created.', 'danger')
        else:
            allocation = RoomAllocation(student_id=student.id, room_id=room.id,
                                        allocation_date=parse_date(request.form.get('allocation_date')) or date.today(), status='Active')
            db.session.add(allocation)
            db.session.commit()
            flash('Room allocated successfully.', 'success')
            return redirect(url_for('manage_allocations'))
    allocations = RoomAllocation.query.order_by(RoomAllocation.allocation_date.desc(), RoomAllocation.id.desc()).all()
    students = Student.query.order_by(Student.name).all()
    rooms = Room.query.order_by(Room.block, Room.room_number).all()
    return render_template('admin_allocations.html', allocations=allocations, students=students, rooms=rooms)


@app.route('/admin/allocations/<int:allocation_id>/vacate', methods=['POST'])
@role_required('admin')
def vacate_room(allocation_id):
    allocation = db.session.get(RoomAllocation, allocation_id) or abort(404)
    if allocation.status == 'Active':
        allocation.status = 'Vacated'
        allocation.vacate_date = parse_date(request.form.get('vacate_date')) or date.today()
        db.session.commit()
        flash('Room vacated successfully.', 'success')
    else:
        flash('This allocation is already inactive.', 'info')
    return redirect(url_for('manage_allocations'))


# ---------- Admin: fee management ----------
@app.route('/admin/fees', methods=['GET', 'POST'])
@role_required('admin')
def manage_fees():
    if request.method == 'POST':
        student = db.session.get(Student, int(request.form.get('student_id', 0)))
        amount = request.form.get('amount', '').strip()
        due_date = parse_date(request.form.get('due_date'))
        try:
            amount_value = float(amount)
        except ValueError:
            amount_value = 0
        if not student or amount_value <= 0 or not due_date:
            flash('Select a student and enter a positive amount and due date.', 'danger')
        else:
            status = request.form.get('status', 'Pending')
            fee = Fee(student_id=student.id, amount=amount_value, due_date=due_date, status=status,
                      payment_date=parse_date(request.form.get('payment_date')),
                      payment_method=request.form.get('payment_method', '').strip(),
                      transaction_id=request.form.get('transaction_id', '').strip())
            if status == 'Paid' and not fee.payment_date:
                fee.payment_date = date.today()
            db.session.add(fee)
            db.session.commit()
            flash('Fee record added.', 'success')
            return redirect(url_for('manage_fees'))
    fees = Fee.query.order_by(Fee.due_date.desc()).all()
    students = Student.query.order_by(Student.name).all()
    return render_template('admin_fees.html', fees=fees, students=students)


@app.route('/admin/fees/<int:fee_id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def edit_fee(fee_id):
    fee = db.session.get(Fee, fee_id) or abort(404)
    if request.method == 'POST':
        fee.amount = float(request.form.get('amount', fee.amount))
        fee.due_date = parse_date(request.form.get('due_date')) or fee.due_date
        fee.status = request.form.get('status', fee.status)
        fee.payment_date = parse_date(request.form.get('payment_date'))
        fee.payment_method = request.form.get('payment_method', '').strip()
        fee.transaction_id = request.form.get('transaction_id', '').strip()
        if fee.status == 'Paid' and not fee.payment_date:
            fee.payment_date = date.today()
        if fee.status != 'Paid':
            fee.payment_date = None
        db.session.commit()
        flash('Fee record updated.', 'success')
        return redirect(url_for('manage_fees'))
    return render_template('fee_form.html', fee=fee)


@app.route('/admin/fees/<int:fee_id>/delete', methods=['POST'])
@role_required('admin')
def delete_fee(fee_id):
    fee = db.session.get(Fee, fee_id) or abort(404)
    db.session.delete(fee)
    db.session.commit()
    flash('Fee record deleted.', 'success')
    return redirect(url_for('manage_fees'))


# ---------- Admin: complaint management ----------
@app.route('/admin/complaints')
@role_required('admin')
def manage_complaints():
    status = request.args.get('status', '')
    query = Complaint.query
    if status:
        query = query.filter_by(status=status)
    complaints = query.order_by(Complaint.created_at.desc()).all()
    return render_template('admin_complaints.html', complaints=complaints, status=status)


@app.route('/admin/complaints/<int:complaint_id>', methods=['GET', 'POST'])
@role_required('admin')
def edit_complaint(complaint_id):
    complaint = db.session.get(Complaint, complaint_id) or abort(404)
    if request.method == 'POST':
        complaint.status = request.form.get('status', 'Pending')
        complaint.admin_response = request.form.get('admin_response', '').strip()
        complaint.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Complaint updated.', 'success')
        return redirect(url_for('manage_complaints'))
    return render_template('complaint_form.html', complaint=complaint)


# ---------- Admin: notice management ----------
@app.route('/admin/notices', methods=['GET', 'POST'])
@role_required('admin')
def manage_notices():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        if title and description:
            db.session.add(Notice(title=title, description=description, created_by=current_user.id))
            db.session.commit()
            flash('Notice published.', 'success')
            return redirect(url_for('manage_notices'))
        flash('Title and description are required.', 'danger')
    notices = Notice.query.order_by(Notice.created_at.desc()).all()
    return render_template('admin_notices.html', notices=notices)


@app.route('/admin/notices/<int:notice_id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def edit_notice(notice_id):
    notice = db.session.get(Notice, notice_id) or abort(404)
    if request.method == 'POST':
        notice.title = request.form.get('title', '').strip()
        notice.description = request.form.get('description', '').strip()
        if notice.title and notice.description:
            db.session.commit()
            flash('Notice updated.', 'success')
            return redirect(url_for('manage_notices'))
        flash('Title and description are required.', 'danger')
    return render_template('notice_form.html', notice=notice)


@app.route('/admin/notices/<int:notice_id>/delete', methods=['POST'])
@role_required('admin')
def delete_notice(notice_id):
    notice = db.session.get(Notice, notice_id) or abort(404)
    db.session.delete(notice)
    db.session.commit()
    flash('Notice deleted.', 'success')
    return redirect(url_for('manage_notices'))


@app.cli.command('init-db')
def init_db_command():
    """Create all tables and optionally create an admin account from environment variables."""
    db.create_all()
    admin_email = os.getenv('ADMIN_EMAIL', 'admin@hostel.local')
    admin_username = os.getenv('ADMIN_USERNAME', 'admin')
    admin_password = os.getenv('ADMIN_PASSWORD', 'Admin@12345')
    if not User.query.filter_by(role='admin').first():
        admin = User(username=admin_username, email=admin_email, role='admin')
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f'Created admin user: {admin_username} / {admin_password}')
    click.echo('Database tables are ready.')


@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', code=404, message=getattr(error, 'description', 'Page not found.')), 404


@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    return render_template('error.html', code=500, message='Something went wrong. Check the terminal for the development error details.'), 500


if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', '1') == '1')
