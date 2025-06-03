from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3
import os
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a secure random key in production
app.config['UPLOAD_FOLDER'] = 'uploads/'  # Directory to store CVs
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'doc', 'docx'}  # Allowed file types

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database connection helper with row factory
def get_db_connection():
    conn = sqlite3.connect('job_board.db')
    conn.row_factory = sqlite3.Row  # Set row factory to return dictionary-like rows
    return conn

# Database initialization
def init_db():
    with get_db_connection() as conn:
        c = conn.cursor()
        # Create users table if it doesn't exist
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
        ''')
        # Create jobs table if it doesn't exist
        c.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                poster_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT NOT NULL,
                FOREIGN KEY (poster_id) REFERENCES users (id)
            )
        ''')
        # Create applications table if it doesn't exist
        c.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                message TEXT,
                date_applied TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cv_path TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs (id),
                FOREIGN KEY (student_id) REFERENCES users (id)
            )
        ''')
        conn.commit()

# Initialize the database
init_db()

# Check if file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Routes
@app.route('/', methods=['GET'])
def home():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']  # 'student' or 'employer'
        
        try:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)", 
                         (name, email, password, role))
                conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already exists. Please use a different email.', 'error')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
            user = c.fetchone()
            
            if user:
                session['user_id'] = user['id']
                session['name'] = user['name']
                session['email'] = user['email']
                session['role'] = user['role']
                
                if user['role'] == 'employer':
                    return redirect(url_for('employer_dashboard'))
                else:
                    return redirect(url_for('student_dashboard'))
            else:
                flash('Invalid credentials. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/employer/dashboard')
def employer_dashboard():
    if 'user_id' not in session or session['role'] != 'employer':
        flash('Please login as an employer to access this page.', 'error')
        return redirect(url_for('login'))
    
    with get_db_connection() as conn:
        c = conn.cursor()
        # Get jobs posted by this employer
        c.execute("""
            SELECT j.id, j.title, j.location, j.description, 
                   COUNT(a.id) as application_count 
            FROM jobs j 
            LEFT JOIN applications a ON j.id = a.job_id 
            WHERE j.poster_id = ? 
            GROUP BY j.id
        """, (session['user_id'],))
        jobs = c.fetchall()
    
    return render_template('employer_dashboard.html', jobs=jobs)

@app.route('/student/dashboard')
def student_dashboard():
    if 'user_id' not in session or session['role'] != 'student':
        flash('Please login as a student to access this page.', 'error')
        return redirect(url_for('login'))
    
    with get_db_connection() as conn:
        c = conn.cursor()
        # Get all available jobs
        c.execute("""
            SELECT j.id, j.title, j.location, j.description, u.name as company_name,
                   (SELECT COUNT(*) FROM applications a WHERE a.job_id = j.id AND a.student_id = ?) as applied
            FROM jobs j
            JOIN users u ON j.poster_id = u.id
        """, (session['user_id'],))
        jobs = c.fetchall()
        
        # Get student's applications
        c.execute("""
            SELECT a.id, j.title, u.name as company_name, a.status, a.date_applied
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            JOIN users u ON j.poster_id = u.id
            WHERE a.student_id = ?
        """, (session['user_id'],))
        applications = c.fetchall()
    
    return render_template('student_dashboard.html', jobs=jobs, applications=applications)

@app.route('/post_job', methods=['POST'])
def post_job():
    if 'user_id' not in session or session['role'] != 'employer':
        flash('Please login as an employer to post jobs.', 'error')
        return redirect(url_for('login'))
    
    title = request.form['title']
    location = request.form['location']
    description = request.form['description']
    
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO jobs (poster_id, title, location, description) VALUES (?, ?, ?, ?)", 
                 (session['user_id'], title, location, description))
        conn.commit()
    
    flash('Job posted successfully!', 'success')
    return redirect(url_for('employer_dashboard'))

@app.route('/apply_job/<int:job_id>', methods=['GET', 'POST'])
def apply_job(job_id):
    if 'user_id' not in session or session['role'] != 'student':
        flash('Please login as a student to apply for jobs.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        message = request.form['message']
        cv_file = request.files.get('cv')
        
        # Validate inputs
        if not message:
            flash('Application message is required.', 'error')
            return redirect(url_for('apply_job', job_id=job_id))
        
        if not cv_file or not allowed_file(cv_file.filename):
            flash('Please upload a valid CV (PDF, DOC, or DOCX).', 'error')
            return redirect(url_for('apply_job', job_id=job_id))
        
        # Securely save the CV file with absolute path
        filename = secure_filename(cv_file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"  # Avoid filename conflicts
        cv_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        cv_path_absolute = os.path.abspath(cv_path)  # Convert to absolute path
        cv_file.save(cv_path_absolute)
        
        with get_db_connection() as conn:
            c = conn.cursor()
            # Check if already applied
            c.execute("SELECT * FROM applications WHERE job_id = ? AND student_id = ?", 
                     (job_id, session['user_id']))
            if c.fetchone():
                flash('You have already applied for this job.', 'error')
                return redirect(url_for('student_dashboard'))
                
            c.execute("INSERT INTO applications (job_id, student_id, message, cv_path) VALUES (?, ?, ?, ?)", 
                     (job_id, session['user_id'], message, cv_path_absolute))
            conn.commit()
        
        flash('Application submitted successfully!', 'success')
        return redirect(url_for('student_dashboard'))
    
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT j.id, j.title, j.location, j.description, u.name as company_name
            FROM jobs j
            JOIN users u ON j.poster_id = u.id
            WHERE j.id = ?
        """, (job_id,))
        job = c.fetchone()
    
    if not job:
        flash('Job not found.', 'error')
        return redirect(url_for('student_dashboard'))
    
    return render_template('apply_job.html', job=job)

@app.route('/view_applications/<int:job_id>')
def view_applications(job_id):
    if 'user_id' not in session or session['role'] != 'employer':
        flash('Unauthorized access.', 'error')
        return redirect(url_for('login'))
    
    with get_db_connection() as conn:
        c = conn.cursor()
        # Verify the job belongs to this employer
        c.execute("SELECT * FROM jobs WHERE id = ? AND poster_id = ?", (job_id, session['user_id']))
        job = c.fetchone()
        
        if not job:
            flash('Job not found or you do not have permission to view its applications.', 'error')
            return redirect(url_for('employer_dashboard'))
        
        # Get applications for this job
        c.execute("""
            SELECT a.id, u.name as student_name, u.email as student_email, 
                   a.message, a.status, a.date_applied, a.cv_path
            FROM applications a
            JOIN users u ON a.student_id = u.id
            WHERE a.job_id = ?
            ORDER BY a.date_applied DESC
        """, (job_id,))
        applications = c.fetchall()
        print("Applications:", [dict(app) for app in applications])  # Debug print
    
    return render_template('view_applications.html', job=job, applications=applications)

@app.route('/download_cv/<int:app_id>')
def download_cv(app_id):
    if 'user_id' not in session or session['role'] != 'employer':
        flash('Please login as an employer to view CVs.', 'error')
        return redirect(url_for('login'))
    
    with get_db_connection() as conn:
        c = conn.cursor()
        # Verify the application belongs to a job by this employer
        c.execute("""
            SELECT a.cv_path, a.job_id
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE a.id = ? AND j.poster_id = ?
        """, (app_id, session['user_id']))
        application = c.fetchone()
        
        if not application:
            flash('Application not found or you do not have permission to view this CV.', 'error')
            return redirect(url_for('employer_dashboard'))
        
        try:
            print("Attempting to download CV from:", application['cv_path'])  # Now works with dictionary-like access
            return send_file(application['cv_path'], as_attachment=True)
        except FileNotFoundError as e:
            print("File not found error:", e)
            flash('CV file not found.', 'error')
            return redirect(url_for('employer_dashboard'))
        except Exception as e:
            print("Unexpected error:", e)
            flash('An error occurred while downloading the CV.', 'error')
            return redirect(url_for('employer_dashboard'))

@app.route('/update_application_status/<int:app_id>/<status>')
def update_application_status(app_id, status):
    if 'user_id' not in session or session['role'] != 'employer':
        flash('Unauthorized access.', 'error')
        return redirect(url_for('login'))
    
    if status not in ['approved', 'rejected', 'pending']:
        flash('Invalid status.', 'error')
        return redirect(url_for('employer_dashboard'))
    
    with get_db_connection() as conn:
        c = conn.cursor()
        # Verify the application belongs to a job by this employer
        c.execute("""
            SELECT a.id, j.id as job_id
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE a.id = ? AND j.poster_id = ?
        """, (app_id, session['user_id']))
        application = c.fetchone()
        
        if not application:
            flash('Application not found or you do not have permission to update it.', 'error')
            return redirect(url_for('employer_dashboard'))
        
        c.execute("UPDATE applications SET status = ? WHERE id = ?", (status, app_id))
        conn.commit()
    
    flash(f'Application status updated to {status}.', 'success')
    return redirect(url_for('view_applications', job_id=application['job_id']))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)