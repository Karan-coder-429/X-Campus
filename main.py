from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
import sqlite3
from datetime import datetime
import qrcode
from passlib.context import CryptContext

# Initialize FastAPI app
app = FastAPI(title="X Campus API", version="1.0.0")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development - restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Database path - UPDATE THIS TO YOUR PATH
db_path = "C:\\Users\\Dell\\Desktop\\X Pay DataBase\\X Campus.db"

# Create directories for file uploads
directories = ["uploads", "student_photos", "staff_photos", "idcards", "qrcodes"]
for directory in directories:
    os.makedirs(directory, exist_ok=True)

# Mount static file directories
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/student_photos", StaticFiles(directory="student_photos"), name="student_photos")
app.mount("/staff_photos", StaticFiles(directory="staff_photos"), name="staff_photos")
app.mount("/idcards", StaticFiles(directory="idcards"), name="idcards")
app.mount("/qrcodes", StaticFiles(directory="qrcodes"), name="qrcodes")

# Serve frontend files (optional - if you want to serve HTML from FastAPI)
# app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

# ========================================
# LOST & FOUND ENDPOINTS
# ========================================

@app.post("/item/lost_item/")
async def submit_lost_item(
    item_name: str = Form(...),
    item_description: str = Form(...),
    founder_name: str = Form(...),
    founder_number: str = Form(...),
    founder_class: str = Form(...),
    founder_branch: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        # Save uploaded file
        file_path = os.path.join("uploads", file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Insert into database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO lost_item (item_name, item_description, founder_name, founder_number, founder_class, founder_branch, file_path, time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item_name,
            item_description,
            founder_name,
            founder_number,
            founder_class,
            founder_branch,
            file_path,
            datetime.now().strftime("%d %b %Y %H:%M:%S")
        ))
        conn.commit()
        conn.close()

        return {"message": "Lost item submitted successfully!"}
    except Exception as e:
        print(f"Error in submit_lost_item: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/item/lost_items/")
def get_lost_items():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT item_name, item_description, file_path FROM lost_item ORDER BY time DESC")
        items = cursor.fetchall()
        conn.close()
        
        # Convert file paths to accessible URLs
        result = []
        for item in items:
            filename = os.path.basename(item[2]) if item[2] else "default.jpg"
            result.append({
                "name": item[0],
                "desc": item[1],
                "img": f"http://127.0.0.1:8000/uploads/{filename}"
            })
        
        return result
    except Exception as e:
        print(f"Error in get_lost_items: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch items")

# ========================================
# ID CARD ENDPOINTS
# ========================================

from hashlib import sha256

@app.post("/idcard/upload/")
async def upload_id_card(
    name: str = Form(...),
    roll_number: str = Form(...),
    branch: str = Form(...),
    year: str = Form(...),
    college_name: str = Form(...),
    college_contact: str = Form(...),
    password: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        # Save ID card image
        id_filename = f"{roll_number}_{file.filename}"
        file_path = os.path.join("idcards", id_filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Generate QR code
        qr_data = f"http://127.0.0.1:8000/idcard/view_secure/{roll_number}"
        qr_filename = f"{roll_number}_qr.png"
        qr_path = os.path.join("qrcodes", qr_filename)
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(qr_path)

        # Hash password using SHA-256
        password = sha256(password.encode()).hexdigest()

        # Save to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO student_id (name, roll_number, branch, year, college_name, college_contact, id_image_path, qr_path, password, time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, roll_number, branch, year, college_name,college_contact,
            file_path, qr_path, password, datetime.now().strftime("%d %b %Y %H:%M:%S")
        ))
        conn.commit()
        conn.close()

        return {
            "message": "ID card uploaded successfully!",
            "qr_link": qr_data,
            "qr_image": f"http://127.0.0.1:8000/qrcodes/{qr_filename}"
        }
    except Exception as e:
        print(f"Error in upload_id_card: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
import hashlib

@app.post("/idcard/view_secure/")
def view_id_card_secure(roll_number: str = Form(...), password: str = Form(...)):
    try:
        password_2 = hashlib.sha256(password.strip().encode()).hexdigest()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM student_id WHERE roll_number = ? AND password = ?", (roll_number, password_2))
        student = cursor.fetchone()
        conn.close()
    except Exception as e:
        print(f"DB error: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not student:
        raise HTTPException(status_code=401, detail="Invalid roll number or password")

    return {
        "name": student[1],
        "roll_number": student[2],
        "branch": student[3],
        "year": student[4],
        "college_name": student[5],
        "college_contact": student[6]
    }


# ========================================
# CAREER GUIDANCE ENDPOINTS
# ========================================

@app.post("/career/suggest/")
def suggest_career(skill: str = Form(...)):
    skill_mapping = {
        "coding": "Software Development / Backend Engineering",
        "design": "UI/UX Design / Product Design", 
        "communication": "Marketing / Public Relations / HR",
        "data analysis": "Data Science / Business Analytics",
        "machine learning": "AI Research / ML Engineering",
        "video editing": "Content Creation / Media Production",
        "finance": "Investment Banking / Financial Analysis"
    }
    
    recommended_field = skill_mapping.get(skill.lower(), "General Technology Field")
    return {"recommended_field": recommended_field}

# ========================================
# COLLEGE RECOMMENDATION ENDPOINTS
# ========================================

@app.post("/college/recommend/")
def recommend_college(
    percentage: int = Form(...),
    skill: str = Form(...),
    city: str = Form(...)
):
    # Define cutoffs
    govt_cutoff = 85
    private_cutoff = 50
    
    if percentage < private_cutoff:
        return {"message": "Sorry, percentage too low for recommendations."}
    
    college_type = "govt" if percentage >= govt_cutoff else "private"
    
    # College mapping
    colleges = {
        "coding": {
            "govt": {
                "Vadodara": "MSU Technology Campus",
                "Ahmedabad": "LD Engineering College",
                "Surat": "Government Engineering College",
                "Rajkot": "Government Engineering College Rajkot",
                "Pune": "College of Engineering Pune",
                "Mumbai": "VJTI Mumbai",
                "Delhi": "NSUT Delhi",
                "Bangalore": "University Visvesvaraya College of Engineering",
                "Hyderabad": "Osmania University College of Engineering",
                "Chennai": "College of Engineering Guindy"
            },
            "private": {
                "Vadodara": "Parul University",
                "Ahmedabad": "Nirma University",
                "Surat": "Sardar Vallabhbhai National Institute of Technology",
                "Rajkot": "Marwadi University",
                "Pune": "MIT World Peace University",
                "Mumbai": "NMIMS University",
                "Delhi": "Amity University Delhi",
                "Bangalore": "PES University",
                "Hyderabad": "Vardhaman College of Engineering",
                "Chennai": "SRM Institute of Science and Technology"
            }
        },
        "design": {
            "govt": {
                "Vadodara": "MSU Faculty of Fine Arts",
                "Ahmedabad": "CEPT University",
                "Surat": "Veer Narmad South Gujarat University",
                "Rajkot": "Saurashtra University",
                "Pune": "College of Engineering Pune - Design",
                "Mumbai": "Sir JJ School of Art",
                "Delhi": "NIFT Delhi",
                "Bangalore": "National Institute of Design",
                "Hyderabad": "JNAFAU",
                "Chennai": "Government College of Fine Arts"
            },
            "private": {
                "Vadodara": "Parul Institute of Design",
                "Ahmedabad": "Anant National University",
                "Surat": "AURO University",
                "Rajkot": "RK University",
                "Pune": "Symbiosis Institute of Design",
                "Mumbai": "Indian School of Design and Innovation",
                "Delhi": "Pearl Academy",
                "Bangalore": "Srishti Institute of Art, Design and Technology",
                "Hyderabad": "ICAT Design and Media College",
                "Chennai": "LISAA School of Design"
            }
        },
        "finance": {
            "govt": {
                "Vadodara": "MSU Faculty of Commerce",
                "Ahmedabad": "Gujarat University",
                "Surat": "Veer Narmad South Gujarat University",
                "Rajkot": "Saurashtra University",
                "Pune": "Brihan Maharashtra College of Commerce",
                "Mumbai": "Sydenham College of Commerce and Economics",
                "Delhi": "Shri Ram College of Commerce",
                "Bangalore": "Bangalore University",
                "Hyderabad": "Osmania University",
                "Chennai": "University of Madras"
            },
            "private": {
                "Vadodara": "Navrachana University",
                "Ahmedabad": "GLS University",
                "Surat": "AURO University",
                "Rajkot": "Atmiya University",
                "Pune": "MIT World Peace University",
                "Mumbai": "NMIMS School of Business Management",
                "Delhi": "Amity Business School",
                "Bangalore": "Christ University",
                "Hyderabad": "ICFAI Business School",
                "Chennai": "VIT Business School"
            }
        }
    }
    
    try:
        recommended_college = colleges[skill.lower()][college_type][city]
        return {
            "college_type": "Government" if college_type == "govt" else "Private",
            "recommended_college": recommended_college
        }
    except KeyError:
        return {"message": "No matching college found for this combination."}

# ========================================
# STUDENT REGISTRATION ENDPOINTS
# ========================================

@app.post("/student/register/")
async def register_student(
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    branch: str = Form(...),
    year: str = Form(...),
    password: str = Form(...),
    photo: UploadFile = File(...)
):
    try:
        # Save student photo
        photo_filename = f"student_{email}_{photo.filename}"
        photo_path = os.path.join("student_photos", photo_filename)
        with open(photo_path, "wb") as f:
            f.write(await photo.read())

        # Hash password
        hashed_password = pwd_context.hash(password)

        # Save to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO student_register (name, email, phone, branch, year, password_hash, photo_path, time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, email, phone, branch, year, hashed_password, photo_path,
            datetime.now().strftime("%d %b %Y %H:%M:%S")
        ))
        conn.commit()
        conn.close()

        return {"message": "Student registered successfully!"}
    except Exception as e:
        print(f"Error in register_student: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.post("/student/login/")
def login_student(email: str = Form(...), password: str = Form(...)):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name, password_hash FROM student_register WHERE email = ?", (email,))
        student = cursor.fetchone()
        conn.close()
        
        if not student or not pwd_context.verify(password, student[1]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        return {"message": f"Welcome back, {student[0]}!"}
    except Exception as e:
        print(f"Error in login_student: {e}")
        raise HTTPException(status_code=500, detail="Login failed")

# ========================================
# STAFF REGISTRATION ENDPOINTS
# ========================================

@app.post("/staff/register/")
async def register_staff(
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    department: str = Form(...),
    designation: str = Form(...),
    password: str = Form(...),
    photo: UploadFile = File(...)
):
    try:
        # Save staff photo
        photo_filename = f"staff_{email}_{photo.filename}"
        photo_path = os.path.join("staff_photos", photo_filename)
        with open(photo_path, "wb") as f:
            f.write(await photo.read())

        # Hash password
        hashed_password = pwd_context.hash(password)

        # Save to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO staff_register (name, email, phone, department, designation, password_hash, photo_path, time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, email, phone, department, designation, hashed_password, photo_path,
            datetime.now().strftime("%d %b %Y %H:%M:%S")
        ))
        conn.commit()
        conn.close()

        return {"message": "Staff registered successfully!"}
    except Exception as e:
        print(f"Error in register_staff: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.post("/staff/login/")
def login_staff(email: str = Form(...), password: str = Form(...)):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name, password_hash FROM staff_register WHERE email = ?", (email,))
        staff = cursor.fetchone()
        conn.close()
        
        if not staff or not pwd_context.verify(password, staff[1]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        return {"message": f"Welcome back, {staff[0]}!"}
    except Exception as e:
        print(f"Error in login_staff: {e}")
        raise HTTPException(status_code=500, detail="Login failed")

# ========================================
# SENIOR-JUNIOR CONNECT ENDPOINTS
# ========================================

@app.post("/connect/register_senior/")
def register_senior(
    name: str = Form(...),
    branch: str = Form(...),
    year: str = Form(...),
    skills: str = Form(...),
    availability: str = Form(...),
    contact: str = Form(...)
):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO senior_connect (name, branch, year, skills, availability, contact)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, branch, year, skills, availability, contact))
        conn.commit()
        conn.close()
        return {"message": "Senior registered successfully!"}
    except Exception as e:
        print(f"Error in register_senior: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.post("/connect/request_junior/")
def request_junior(
    name: str = Form(...),
    branch: str = Form(...),
    year: str = Form(...),
    query: str = Form(...),
    skill_needed: str = Form(...)
):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO junior_request (name, branch, year, query, skill_needed)
            VALUES (?, ?, ?, ?, ?)
        """, (name, branch, year, query, skill_needed))
        conn.commit()
        conn.close()
        return {"message": "Junior request submitted successfully!"}
    except Exception as e:
        print(f"Error in request_junior: {e}")
        raise HTTPException(status_code=500, detail="Request failed")

@app.get("/connect/match/")
def match_junior_to_senior(skill: str):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, contact, availability FROM senior_connect
            WHERE skills LIKE ?
        """, (f'%{skill}%',))
        matches = cursor.fetchall()
        conn.close()
        
        return [{"name": match[0], "contact": match[1], "availability": match[2]} for match in matches]
    except Exception as e:
        print(f"Error in match_junior_to_senior: {e}")
        raise HTTPException(status_code=500, detail="Matching failed")

# ========================================
# CHATBOT ENDPOINTS
# ========================================

@app.post("/chatbot/query")
def chatbot_response(query: str = Form(...)):
    query_lower = query.lower()
    
    responses = {
        "rule": "College rules: 75% attendance required, ID card mandatory, ragging strictly prohibited.",
        "regulation": "College rules: 75% attendance required, ID card mandatory, ragging strictly prohibited.",
        "canteen": "Canteen opens at 9 AM and closes at 5 PM. Menu updates daily.",
        "food": "Canteen opens at 9 AM and closes at 5 PM. Menu updates daily.",
        "notes": "Study materials are available under the Notes section in X Campus.",
        "study material": "Study materials are available under the Notes section in X Campus.",
        "internship": "Internship listings are updated every Monday. Check the Internships tab.",
        "job": "Internship listings are updated every Monday. Check the Internships tab.",
        "new student": "Welcome! Begin with Dashboard, explore your schedule, and check out the canteen and notes.",
        "how to start": "Welcome! Begin with Dashboard, explore your schedule, and check out the canteen and notes.",
        "library": "Library is open from 8 AM to 8 PM. Carry your ID card to enter.",
        "exam": "Mid-sem exams are in October, finals in March. Check Dashboard for exact dates.",
        "test": "Mid-sem exams are in October, finals in March. Check Dashboard for exact dates.",
        "attendance": "Minimum 75% attendance is mandatory to appear for exams.",
        "id card": "Your college ID card must be carried at all times. It's needed for library, exams, and events.",
        "ragging": "Ragging is strictly prohibited. Report any incident immediately to the authorities.",
        "hostel": "Hostel curfew is 10 PM. Visitors allowed till 7 PM with prior permission.",
        "sports": "Sports facilities include basketball, cricket, and gym. Timings: 4 PM to 7 PM.",
        "events": "Upcoming events are listed in the Campus News section. Don't miss the annual fest!",
        "fest": "Upcoming events are listed in the Campus News section. Don't miss the annual fest!",
        "wifi": "Campus Wi-Fi is available in all blocks. Use your student credentials to login.",
        "internet": "Campus Wi-Fi is available in all blocks. Use your student credentials to login.",
        "contact": "For help, visit the Admin Office or use the Help section in X Campus.",
        "help": "For help, visit the Admin Office or use the Help section in X Campus."
    }
    
    for keyword, response in responses.items():
        if keyword in query_lower:
            return {"response": response}
    
    return {"response": "Sorry, I didn't understand that. Try asking about rules, canteen, notes, exams, or hostel."}

# ========================================
# ROOT ENDPOINT
# ========================================

@app.get("/")
def read_root():
    return {"message": "X Campus API is running!", "docs": "/docs", "version": "1.0.0"}

# ========================================
# HEALTH CHECK
# ========================================

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().strftime("%d %b %Y %H:%M:%S")}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)