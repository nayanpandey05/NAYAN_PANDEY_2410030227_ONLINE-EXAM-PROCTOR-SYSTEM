from flask import Flask, render_template, request, jsonify, redirect, session, flash, url_for
from flask_session import Session
from database.mongo import users, violations, exam_sessions, exam_results
from database.demo_user import create_demo_users
from suspicious_score import get_session_score, get_violation_breakdown
import bcrypt
import datetime
from functools import wraps
from bson import ObjectId
import os

app = Flask(__name__)
app.config.from_object('config.Config')

# Initialize Flask-Session
Session(app)

# Sample exam questions
EXAM_QUESTIONS = [
    {
        "id": 1,
        "question": "What is the time complexity of binary search?",
        "options": ["O(n)", "O(log n)", "O(n²)", "O(1)"],
        "correct": 1
    },
    {
        "id": 2,
        "question": "Which data structure uses LIFO principle?",
        "options": ["Queue", "Stack", "Tree", "Graph"],
        "correct": 1
    },
    {
        "id": 3,
        "question": "What does HTML stand for?",
        "options": ["Hyper Text Markup Language", "High Tech Modern Language", 
                   "Home Tool Markup Language", "Hyperlinks and Text Markup Language"],
        "correct": 0
    },
    {
        "id": 4,
        "question": "Which of the following is not a programming language?",
        "options": ["Python", "Java", "HTML", "C++"],
        "correct": 2
    },
    {
        "id": 5,
        "question": "What is the result of 2 ** 3 in Python?",
        "options": ["6", "8", "9", "5"],
        "correct": 1
    }
]

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        user = users.find_one({"_id": ObjectId(session['user_id'])})
        if not user or user.get('role') != 'admin':
            flash('Admin access required', 'error')
            return redirect(url_for('exam'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
def root():
    if 'user_id' in session:
        return redirect(url_for('exam'))
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            name = request.form.get("name", "").strip()
            
            # Validation
            if not email or not password or not name:
                flash("All fields are required", "error")
                return redirect(url_for('register'))
            
            if len(password) < 6:
                flash("Password must be at least 6 characters", "error")
                return redirect(url_for('register'))
            
            # Check if user already exists
            if users.find_one({"email": email}):
                flash("Email already registered", "error")
                return redirect(url_for('register'))
            
            # Hash password
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            
            # Insert user
            users.insert_one({
                "email": email,
                "password": hashed,
                "name": name,
                "role": "student",
                "created_at": datetime.datetime.now()
            })
            
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('login'))
            
        except Exception as e:
            flash(f"Registration failed: {str(e)}", "error")
            return redirect(url_for('register'))
    
    return render_template("register.html")

@app.route("/login", methods=["POST","GET"])
def login():
    if request.method == "POST":
        try:
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            
            if not email or not password:
                flash("Email and password are required", "error")
                return redirect(url_for('login'))
            
            user = users.find_one({"email": email})
            
            if user and bcrypt.checkpw(password.encode(), user["password"]):
                session['user_id'] = str(user['_id'])
                session['user_email'] = user['email']
                session['user_name'] = user.get('name', 'Student')
                session['user_role'] = user.get('role', 'student')
                
                # Redirect based on role
                if user.get('role') == 'admin':
                    return redirect(url_for('dashboard'))
                return redirect(url_for('exam'))
            
            flash("Invalid email or password", "error")
            return redirect(url_for('login'))
            
        except Exception as e:
            flash(f"Login failed: {str(e)}", "error")
            return redirect(url_for('login'))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for('login'))

@app.route("/exam")
@login_required
def exam():
    # Create new exam session
    session_data = {
        "user_id": session['user_id'],
        "user_email": session['user_email'],
        "start_time": datetime.datetime.now(),
        "status": "in_progress"
    }
    result = exam_sessions.insert_one(session_data)
    session['exam_session_id'] = str(result.inserted_id)
    
    return render_template("exam.html", 
                          questions=EXAM_QUESTIONS,
                          user_name=session.get('user_name'))

@app.route("/violation", methods=["POST"])
@login_required
def violation():
    try:
        data = request.json
        violation_data = {
            "type": data["type"],
            "user_id": session['user_id'],
            "user_email": session['user_email'],
            "session_id": session.get('exam_session_id'),
            "time": datetime.datetime.now()
        }
        violations.insert_one(violation_data)
        
        # Get current score for this session
        score = get_session_score(session.get('exam_session_id'))
        
        return jsonify({
            "status": "logged",
            "current_score": score
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/submit_exam", methods=["POST"])
@login_required
def submit_exam():
    try:
        data = request.json
        answers = data.get("answers", {})
        
        # Calculate score
        correct_count = 0
        for question in EXAM_QUESTIONS:
            qid = str(question["id"])
            if qid in answers and int(answers[qid]) == question["correct"]:
                correct_count += 1
        
        exam_score = (correct_count / len(EXAM_QUESTIONS)) * 100
        
        # Get suspicious score
        session_id = session.get('exam_session_id')
        suspicious_score = get_session_score(session_id)
        violation_breakdown = get_violation_breakdown(session_id=session_id)
        
        # Save results
        result_data = {
            "user_id": session['user_id'],
            "user_email": session['user_email'],
            "session_id": session_id,
            "exam_score": exam_score,
            "correct_answers": correct_count,
            "total_questions": len(EXAM_QUESTIONS),
            "suspicious_score": suspicious_score,
            "violations": violation_breakdown,
            "submitted_at": datetime.datetime.now()
        }
        exam_results.insert_one(result_data)
        
        # Update session status
        exam_sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {
                "status": "completed",
                "end_time": datetime.datetime.now()
            }}
        )
        
        return jsonify({
            "status": "success",
            "exam_score": exam_score,
            "suspicious_score": suspicious_score,
            "violations": violation_breakdown
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/dashboard")
@admin_required
def dashboard():
    # Get all violations with user info
    all_violations = list(violations.find().sort("time", -1).limit(100))
    
    # Get statistics
    total_violations = violations.count_documents({})
    
    # Violations by type
    violation_types = {}
    for v in violations.find():
        vtype = v.get("type", "Unknown")
        violation_types[vtype] = violation_types.get(vtype, 0) + 1
    
    # Recent exam results
    recent_results = list(exam_results.find().sort("submitted_at", -1).limit(10))
    
    stats = {
        "total_violations": total_violations,
        "violation_types": violation_types,
        "total_exams": exam_results.count_documents({}),
        "total_users": users.count_documents({})
    }
    
    return render_template("dashboard.html", 
                          violations=all_violations,
                          stats=stats,
                          recent_results=recent_results)

@app.route("/api/get_questions")
@login_required
def get_questions():
    return jsonify({"questions": EXAM_QUESTIONS})

if __name__ == "__main__":
    # Ensure upload folder exists
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    
    print("\n" + "="*50)
    print("*** Online Exam Proctor System ***")
    print("="*50)
    print(f"Server running at: http://localhost:5000")
    print(f"Demo Login: student@demo.com / password123")
    print(f"Admin Login: admin@demo.com / admin123")
    print("="*50 + "\n")
    # create_demo_users()
    
    app.run(debug=True, port=5000)
