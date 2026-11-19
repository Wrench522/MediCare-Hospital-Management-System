
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-development-secret")


# Database configuration
database_url = os.environ.get("DATABASE_URL")

if database_url:
    # Support PostgreSQL connection URLs from hosting providers
    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://", "postgresql://", 1
        )

    if database_url.startswith("postgresql+psycopg://"):
        database_url = database_url.replace(
            "postgresql+psycopg://",
            "postgresql+psycopg2://",
            1
        )
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://",
            "postgresql+psycopg2://",
            1
        )

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url

elif os.environ.get("VERCEL"):
    # Do not silently use temporary SQLite storage on Vercel
    raise RuntimeError(
        "DATABASE_URL is missing. Configure a persistent PostgreSQL database."
    )

else:
    # Use SQLite for local development on Fedora
    database_dir = os.path.join(BASE_DIR, "database")
    os.makedirs(database_dir, exist_ok=True)

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///" + os.path.join(database_dir, "hospital.db")
    )

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="Receptionist")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120))
    address = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    appointments = db.relationship("Appointment", backref="patient", lazy=True)
    bills = db.relationship("Bill", backref="patient", lazy=True)


class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120))
    availability = db.Column(db.String(120), default="Mon–Fri")
    appointments = db.relationship("Appointment", backref="doctor", lazy=True)


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctor.id"), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.String(10), nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(30), default="Pending", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    amount_paid = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    payment_status = db.Column(db.String(20), default="Pending", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def balance(self):
        return self.amount - self.amount_paid


@app.context_processor
def inject_template_globals():
    return {"now_year": date.today().year, "today_iso": date.today().isoformat()}


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "Admin":
            flash("Only an administrator can perform that action.", "danger")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def index():
    return redirect(url_for("dashboard" if current_user.is_authenticated else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    today = date.today()
    stats = {
        "patients": Patient.query.count(),
        "doctors": Doctor.query.count(),
        "appointments": Appointment.query.filter_by(appointment_date=today).count(),
        "revenue": db.session.query(db.func.coalesce(db.func.sum(Bill.amount_paid), 0)).scalar()
    }
    recent = Appointment.query.order_by(Appointment.appointment_date.desc(), Appointment.id.desc()).limit(6).all()
    monthly = []
    for month in range(1, 13):
        total = db.session.query(db.func.coalesce(db.func.sum(Bill.amount_paid), 0)).filter(
            db.extract("month", Bill.created_at) == month,
            db.extract("year", Bill.created_at) == today.year
        ).scalar()
        monthly.append(float(total or 0))
    return render_template("dashboard.html", stats=stats, recent=recent, monthly=monthly, today=today)


@app.route("/patients")
@login_required
def patients():
    q = request.args.get("q", "").strip()
    query = Patient.query
    if q:
        query = query.filter(or_(Patient.full_name.ilike(f"%{q}%"), Patient.phone.ilike(f"%{q}%"), Patient.email.ilike(f"%{q}%")))
    return render_template("patients.html", patients=query.order_by(Patient.full_name).all(), q=q)


@app.route("/patients/add", methods=["GET", "POST"])
@login_required
def add_patient():
    if request.method == "POST":
        try:
            dob = date.fromisoformat(request.form["date_of_birth"])
            if dob > date.today():
                raise ValueError
            patient = Patient(
                full_name=request.form["full_name"].strip(),
                gender=request.form["gender"],
                date_of_birth=dob,
                phone=request.form["phone"].strip(),
                email=request.form.get("email", "").strip() or None,
                address=request.form.get("address", "").strip() or None
            )
            if not patient.full_name or not patient.phone:
                raise ValueError
            db.session.add(patient)
            db.session.commit()
            flash("Patient registered successfully.", "success")
            return redirect(url_for("patients"))
        except (ValueError, KeyError):
            flash("Please enter valid patient details. Date of birth cannot be in the future.", "danger")
    return render_template("patient_form.html", patient=None)


@app.route("/patients/<int:patient_id>/edit", methods=["GET", "POST"])
@login_required
def edit_patient(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    if request.method == "POST":
        try:
            dob = date.fromisoformat(request.form["date_of_birth"])
            if dob > date.today():
                raise ValueError
            patient.full_name = request.form["full_name"].strip()
            patient.gender = request.form["gender"]
            patient.date_of_birth = dob
            patient.phone = request.form["phone"].strip()
            patient.email = request.form.get("email", "").strip() or None
            patient.address = request.form.get("address", "").strip() or None
            if not patient.full_name or not patient.phone:
                raise ValueError
            db.session.commit()
            flash("Patient details updated.", "success")
            return redirect(url_for("patients"))
        except (ValueError, KeyError):
            flash("Please check the submitted details.", "danger")
    return render_template("patient_form.html", patient=patient)


@app.route("/patients/<int:patient_id>/delete", methods=["POST"])
@admin_required
def delete_patient(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    if patient.appointments or patient.bills:
        flash("This patient has appointment or billing records and cannot be deleted.", "warning")
    else:
        db.session.delete(patient)
        db.session.commit()
        flash("Patient deleted.", "success")
    return redirect(url_for("patients"))


@app.route("/doctors")
@login_required
def doctors():
    q = request.args.get("q", "").strip()
    query = Doctor.query
    if q:
        query = query.filter(or_(Doctor.full_name.ilike(f"%{q}%"), Doctor.specialization.ilike(f"%{q}%")))
    return render_template("doctors.html", doctors=query.order_by(Doctor.full_name).all(), q=q)


@app.route("/doctors/add", methods=["GET", "POST"])
@login_required
def add_doctor():
    if request.method == "POST":
        doctor = Doctor(full_name=request.form["full_name"].strip(),
                        specialization=request.form["specialization"].strip(),
                        phone=request.form["phone"].strip(),
                        email=request.form.get("email", "").strip() or None,
                        availability=request.form.get("availability", "Mon–Fri").strip())
        if not doctor.full_name or not doctor.specialization or not doctor.phone:
            flash("Name, specialty and phone are required.", "danger")
        else:
            db.session.add(doctor)
            db.session.commit()
            flash("Doctor added successfully.", "success")
            return redirect(url_for("doctors"))
    return render_template("doctor_form.html", doctor=None)


@app.route("/doctors/<int:doctor_id>/edit", methods=["GET", "POST"])
@login_required
def edit_doctor(doctor_id):
    doctor = db.get_or_404(Doctor, doctor_id)
    if request.method == "POST":
        doctor.full_name = request.form["full_name"].strip()
        doctor.specialization = request.form["specialization"].strip()
        doctor.phone = request.form["phone"].strip()
        doctor.email = request.form.get("email", "").strip() or None
        doctor.availability = request.form.get("availability", "").strip()
        if not doctor.full_name or not doctor.specialization or not doctor.phone:
            flash("Name, specialty and phone are required.", "danger")
        else:
            db.session.commit()
            flash("Doctor details updated.", "success")
            return redirect(url_for("doctors"))
    return render_template("doctor_form.html", doctor=doctor)


@app.route("/doctors/<int:doctor_id>/delete", methods=["POST"])
@admin_required
def delete_doctor(doctor_id):
    doctor = db.get_or_404(Doctor, doctor_id)
    if doctor.appointments:
        flash("This doctor has appointment records and cannot be deleted.", "warning")
    else:
        db.session.delete(doctor)
        db.session.commit()
        flash("Doctor deleted.", "success")
    return redirect(url_for("doctors"))


@app.route("/appointments")
@login_required
def appointments():
    q = request.args.get("q", "").strip()
    query = Appointment.query.join(Patient).join(Doctor)
    if q:
        query = query.filter(or_(Patient.full_name.ilike(f"%{q}%"), Doctor.full_name.ilike(f"%{q}%"), Appointment.status.ilike(f"%{q}%")))
    rows = query.order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).all()
    return render_template("appointments.html", appointments=rows, q=q)


@app.route("/appointments/add", methods=["GET", "POST"])
@login_required
def add_appointment():
    patients_list = Patient.query.order_by(Patient.full_name).all()
    doctors_list = Doctor.query.order_by(Doctor.full_name).all()
    if request.method == "POST":
        try:
            appt_date = date.fromisoformat(request.form["appointment_date"])
            appt_time = request.form["appointment_time"]
            doctor_id = int(request.form["doctor_id"])
            patient_id = int(request.form["patient_id"])
            if appt_date < date.today():
                raise ValueError
            conflict = Appointment.query.filter_by(doctor_id=doctor_id, appointment_date=appt_date,
                                                   appointment_time=appt_time).filter(Appointment.status != "Cancelled").first()
            if conflict:
                flash("That doctor already has an appointment at this date and time.", "danger")
            else:
                appt = Appointment(patient_id=patient_id, doctor_id=doctor_id, appointment_date=appt_date,
                                   appointment_time=appt_time, reason=request.form["reason"].strip(), status="Pending")
                db.session.add(appt)
                db.session.commit()
                flash("Appointment booked.", "success")
                return redirect(url_for("appointments"))
        except (ValueError, KeyError):
            flash("Please provide valid appointment details. Past dates are not allowed.", "danger")
    return render_template("appointment_form.html", patients=patients_list, doctors=doctors_list)


@app.route("/appointments/<int:appointment_id>/status", methods=["POST"])
@login_required
def update_appointment_status(appointment_id):
    appt = db.get_or_404(Appointment, appointment_id)
    status = request.form.get("status")
    if status not in ["Pending", "Confirmed", "Completed", "Cancelled"]:
        abort(400)
    appt.status = status
    db.session.commit()
    flash("Appointment status updated.", "success")
    return redirect(url_for("appointments"))


@app.route("/billing")
@login_required
def billing():
    bills = Bill.query.order_by(Bill.created_at.desc()).all()
    return render_template("billing.html", bills=bills)


@app.route("/billing/add", methods=["GET", "POST"])
@login_required
def add_bill():
    patients_list = Patient.query.order_by(Patient.full_name).all()
    if request.method == "POST":
        try:
            amount = Decimal(request.form["amount"])
            if amount <= 0:
                raise InvalidOperation
            bill = Bill(patient_id=int(request.form["patient_id"]),
                        description=request.form["description"].strip(),
                        amount=amount, amount_paid=Decimal("0.00"), payment_status="Pending")
            if not bill.description:
                raise ValueError
            db.session.add(bill)
            db.session.commit()
            flash("Invoice created.", "success")
            return redirect(url_for("billing"))
        except (InvalidOperation, ValueError, KeyError):
            flash("Enter a valid positive amount and description.", "danger")
    return render_template("bill_form.html", patients=patients_list)


@app.route("/billing/<int:bill_id>/payment", methods=["POST"])
@login_required
def record_payment(bill_id):
    bill = db.get_or_404(Bill, bill_id)
    try:
        payment = Decimal(request.form["payment"])
        if payment <= 0 or payment > bill.balance:
            raise InvalidOperation
        bill.amount_paid += payment
        bill.payment_status = "Paid" if bill.balance == 0 else "Partial"
        db.session.commit()
        flash("Payment recorded successfully.", "success")
    except (InvalidOperation, ValueError, KeyError):
        flash("Payment must be greater than zero and cannot exceed the outstanding balance.", "danger")
    return redirect(url_for("billing"))


@app.route("/setup")
def setup():
    """Initialize the database using a private one-time setup token."""
    setup_token = os.environ.get("SETUP_TOKEN")
    provided_token = request.args.get("token", "")

    if not setup_token or not provided_token or provided_token != setup_token:
        abort(404)

    db.create_all()

    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", role="Admin")
        admin.set_password(os.environ["ADMIN_PASSWORD"])
        db.session.add(admin)
        db.session.commit()

    return "Database initialized successfully."
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", role="Admin")
            admin.set_password(os.environ.get("ADMIN_PASSWORD", "Admin@12345"))
            db.session.add(admin)
            db.session.commit()

    app.run(debug=True)
