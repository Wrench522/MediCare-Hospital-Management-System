# MediCare Hospital Management System

A Flask + SQLite hospital management application for a student project.

## Features
- Admin/receptionist sign-in
- Dashboard with live statistics and payment chart
- Patient and doctor records (create, view, edit, search)
- Appointment booking and status updates
- Doctor appointment conflict prevention
- Invoices and partial/full payment recording in KES
- Responsive interface

## Run on Fedora

```bash
cd medicare_hospital_system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

First-run account:
- Username: `admin`
- Password: `Admin@12345`

Change the starter password before using real data. This is a learning/demo application, not a production hospital system. Do not enter real patient medical information. For production, add CSRF protection, stronger secret management, audit logs, backups, access controls, HTTPS, and privacy/security review.

## Database
SQLite database is automatically created at `database/hospital.db`.

To reset demo data, stop the server and delete `database/hospital.db`; it will be recreated on next launch.
