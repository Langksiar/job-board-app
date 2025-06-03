# 🧑‍💼 Part-Time Job Board

A simple Flask-based web application that allows students to apply for part-time jobs, and employers to post and manage job listings.

## 🚀 Features

- Student registration, login, and dashboard
- Employers can post, edit, and delete job listings
- Students can view and apply for jobs
- Admin can manage users and jobs
- Flash message alerts and session handling
- Simple SQLite database integration

## 📁 Project Structure

job-board/
├── static/
│ └── style.css
├── templates/
│ ├── index.html
│ ├── login.html
│ ├── student_dashboard.html
│ ├── employer_dashboard.html
│ └── apply_job.html
├── app.py
├── database.db
├── README.md
└── .gitignore


## 🛠️ Technologies Used

- Python 3.x
- Flask
- HTML/CSS
- SQLite

## 🧪 How to Run

```bash
# Step 1: Clone this repository
git clone https://github.com/your-username/job-board-app.git

# Step 2: Change directory
cd job-board-app

# Step 3: Run the Flask app
python app.py