import os
import re
from functools import wraps
from datetime import date

from flask import Flask, jsonify, request, session, send_from_directory
from database import get_connection

app = Flask(__name__, static_folder="frontend", static_url_path="")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "skillswap-local-development-key-change-later")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

LEVELS = {"BEGINNER", "INTERMEDIATE", "ADVANCED", "EXPERT"}
MODES = {"ONLINE", "OFFLINE", "EITHER"}
SESSION_MODES = {"ONLINE", "OFFLINE"}
DAYS = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"}
TIME_RE = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


def query_all(sql, params=None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql, params or {})
        if cur.description is None:
            return []
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def query_one(sql, params=None):
    rows = query_all(sql, params)
    return rows[0] if rows else None


def run_sql(sql, params=None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql, params or {})
        conn.commit()
        return cur.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def fail(message, status=400):
    return jsonify({"error": message}), status


def body():
    return request.get_json(silent=True) or {}


def missing_fields(data, *fields):
    return [f for f in fields if data.get(f) is None or data.get(f) == ""]


def current_user_id():
    return session.get("user_id")


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not current_user_id():
            return fail("Please log in to continue.", 401)
        return fn(*args, **kwargs)
    return wrapped


def db_error(message="Could not complete the request."):
    # Keep Oracle details out of browser responses.
    app.logger.exception("SkillSwap database operation failed")
    return fail(message, 400)


@app.get("/")
def home():
    if os.path.isfile(os.path.join(app.static_folder, "index.html")):
        return send_from_directory(app.static_folder, "index.html")
    return jsonify({"message": "SkillSwap API is running. Frontend files will be served from /frontend."})


@app.get("/api/health")
def health():
    try:
        query_one("SELECT 1 AS ok FROM dual")
        return jsonify({"status": "ok", "database": "connected"})
    except Exception:
        app.logger.exception("Health check failed")
        return fail("API is running, but the database connection failed.", 503)


# Authentication: passwords intentionally remain plain text for this development/demo version.
@app.post("/api/auth/register")
def register():
    data = body()
    missing = missing_fields(data, "name", "email", "password")
    if missing:
        return fail("Required fields: " + ", ".join(missing))
    name, email, password = str(data["name"]).strip(), str(data["email"]).strip().lower(), str(data["password"])
    if not name or not email or not password:
        return fail("Name, email and password cannot be blank.")
    try:
        run_sql("""INSERT INTO users (name, email, password_hash, location, bio)
                   VALUES (:name, :email, :password, :location, :bio)""",
                {"name": name, "email": email, "password": password,
                 "location": data.get("location"), "bio": data.get("bio")})
        user = query_one("SELECT user_id, name, email, location, bio FROM users WHERE email = :email", {"email": email})
        session.clear()
        session["user_id"] = int(user["user_id"])
        return jsonify({"message": "Account created.", "user": user}), 201
    except Exception:
        return db_error("Could not create account. This email may already be registered.")


@app.post("/api/auth/login")
def login():
    data = body()
    if missing_fields(data, "email", "password"):
        return fail("Email and password are required.")
    try:
        user = query_one("""SELECT user_id, name, email, location, bio, profile_picture
                             FROM users WHERE LOWER(email) = :email AND password_hash = :password""",
                         {"email": str(data["email"]).strip().lower(), "password": str(data["password"])})
        if not user:
            return fail("Incorrect email or password.", 401)
        session.clear()
        session["user_id"] = int(user["user_id"])
        return jsonify({"message": "Logged in successfully.", "user": user})
    except Exception:
        return db_error("Could not log in right now.")


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out."})


@app.get("/api/auth/me")
@login_required
def me():
    try:
        user = query_one("""SELECT user_id, name, email, location, bio, profile_picture, created_at
                             FROM users WHERE user_id = :user_id""", {"user_id": current_user_id()})
        if not user:
            session.clear()
            return fail("Account not found. Please log in again.", 401)
        return jsonify({"user": user})
    except Exception:
        return db_error("Could not load your account.")


# Public reference data and skill discovery.
@app.get("/api/categories")
def categories():
    try:
        return jsonify(query_all("SELECT category_id, category_name, description FROM categories ORDER BY category_name"))
    except Exception:
        return db_error("Could not load categories.")


@app.get("/api/skills")
def skills():
    try:
        return jsonify(query_all("""SELECT s.skill_id, s.skill_name, s.description,
                                  c.category_id, c.category_name
                                  FROM skills s JOIN categories c ON c.category_id=s.category_id
                                  ORDER BY s.skill_name"""))
    except Exception:
        return db_error("Could not load skills.")


@app.get("/api/offerings")
def offerings_discover():
    try:
        return jsonify(query_all("""SELECT o.offering_id, o.user_id, u.name, u.location,
                                  o.skill_id, s.skill_name, o.proficiency_level
                                  FROM skillofferings o JOIN users u ON u.user_id=o.user_id
                                  JOIN skills s ON s.skill_id=o.skill_id
                                  ORDER BY s.skill_name, u.name"""))
    except Exception:
        return db_error("Could not load skill offerings.")


@app.get("/api/requests")
def requests_discover():
    try:
        return jsonify(query_all("""SELECT r.request_id, r.user_id, u.name, u.location,
                                  r.skill_id, s.skill_name, r.expected_teacher_proficiency
                                  FROM skillrequests r JOIN users u ON u.user_id=r.user_id
                                  JOIN skills s ON s.skill_id=r.skill_id
                                  ORDER BY s.skill_name, u.name"""))
    except Exception:
        return db_error("Could not load skill requests.")


@app.get("/api/dashboard")
@login_required
def dashboard():
    user_id = current_user_id()
    uid = current_user_id()
    try:
        user = query_one("SELECT user_id, name, email, location, bio, profile_picture FROM users WHERE user_id=:user_id", {"user_id": uid})
        summary = query_one("""SELECT
            (SELECT COUNT(*) FROM skillofferings WHERE user_id=:u1) AS skills_offered,
            (SELECT COUNT(*) FROM skillrequests WHERE user_id=:u2) AS skills_requested,
            (SELECT COUNT(*) FROM matches WHERE (user_a_id=:u3 OR user_b_id=:u4) AND status='ACCEPTED') AS accepted_matches,
            (SELECT COUNT(*) FROM sessions se JOIN matches m ON m.match_id=se.match_id
             WHERE (m.user_a_id=:u5 OR m.user_b_id=:u6) AND se.status='SCHEDULED') AS upcoming_sessions
            FROM dual""", {"u1":user_id,"u2":user_id,"u3":user_id,"u4":user_id,"u5":user_id,"u6":user_id})
        rating = query_one("SELECT ROUND(AVG(rating), 2) AS average_rating, COUNT(*) AS total_reviews FROM reviews WHERE reviewee_id=:user_id", {"user_id": uid})
        return jsonify({"user": user, "summary": summary, "rating": rating})
    except Exception:
        return db_error("Could not load your dashboard.")


# User's own offerings and learning requests.
@app.get("/api/my/offerings")
@login_required
def my_offerings():
    try:
        return jsonify(query_all("""SELECT o.offering_id, o.skill_id, s.skill_name, o.proficiency_level
                                  FROM skillofferings o JOIN skills s ON s.skill_id=o.skill_id
                                  WHERE o.user_id=:user_id ORDER BY s.skill_name""", {"user_id": current_user_id()}))
    except Exception:
        return db_error("Could not load your offerings.")


@app.post("/api/my/offerings")
@login_required
def add_offering():
    data = body(); missing = missing_fields(data, "skill_id", "proficiency_level")
    if missing: return fail("Required fields: " + ", ".join(missing))
    level = str(data["proficiency_level"]).upper()
    if level not in LEVELS: return fail("Choose a valid proficiency level.")
    try:
        run_sql("INSERT INTO skillofferings (user_id, skill_id, proficiency_level) VALUES (:user_id, :sid, :p_level)",
                {"user_id": current_user_id(), "sid": data["skill_id"], "p_level": level})
        return jsonify({"message": "Skill offering added."}), 201
    except Exception:
        return db_error("Could not add this offering. You may already offer this skill.")


@app.delete("/api/my/offerings/<int:offering_id>")
@login_required
def remove_offering(offering_id):
    try:
        count = run_sql("DELETE FROM skillofferings WHERE offering_id=:oid AND user_id=:user_id", {"oid": offering_id, "user_id": current_user_id()})
        return (jsonify({"message": "Offering removed."}), 200) if count else fail("Offering not found.", 404)
    except Exception:
        return db_error("Could not remove this offering.")


@app.get("/api/my/requests")
@login_required
def my_requests():
    try:
        return jsonify(query_all("""SELECT r.request_id, r.skill_id, s.skill_name, r.expected_teacher_proficiency
                                  FROM skillrequests r JOIN skills s ON s.skill_id=r.skill_id
                                  WHERE r.user_id=:user_id ORDER BY s.skill_name""", {"user_id": current_user_id()}))
    except Exception:
        return db_error("Could not load your requests.")


@app.post("/api/my/requests")
@login_required
def add_request():
    data = body(); missing = missing_fields(data, "skill_id", "expected_teacher_proficiency")
    if missing: return fail("Required fields: " + ", ".join(missing))
    level = str(data["expected_teacher_proficiency"]).upper()
    if level not in LEVELS: return fail("Choose a valid teacher proficiency level.")
    try:
        run_sql("INSERT INTO skillrequests (user_id, skill_id, expected_teacher_proficiency) VALUES (:user_id, :sid, :p_level)",
                {"user_id": current_user_id(), "sid": data["skill_id"], "p_level": level})
        return jsonify({"message": "Learning request added."}), 201
    except Exception:
        return db_error("Could not add this request. You may already have requested this skill.")


@app.delete("/api/my/requests/<int:request_id>")
@login_required
def remove_request(request_id):
    try:
        count = run_sql("DELETE FROM skillrequests WHERE request_id=:rid AND user_id=:user_id", {"rid": request_id, "user_id": current_user_id()})
        return (jsonify({"message": "Request removed."}), 200) if count else fail("Request not found.", 404)
    except Exception:
        return db_error("Could not remove this request.")


# Matches: suggestions are reciprocal skill exchanges; users can only act on their own matches.
@app.get("/api/my/matches")
@login_required
def my_matches():
    try:
        return jsonify(query_all("""SELECT m.match_id, m.user_a_id, ua.name AS user_a,
            m.user_b_id, ub.name AS user_b, m.skill_a_teaches, sa.skill_name AS user_a_teaches,
            m.skill_b_teaches, sb.skill_name AS user_b_teaches, m.status, m.created_at
            FROM matches m JOIN users ua ON ua.user_id=m.user_a_id JOIN users ub ON ub.user_id=m.user_b_id
            JOIN skills sa ON sa.skill_id=m.skill_a_teaches JOIN skills sb ON sb.skill_id=m.skill_b_teaches
            WHERE m.user_a_id=:user_id OR m.user_b_id=:user_id ORDER BY m.created_at DESC""", {"user_id": current_user_id()}))
    except Exception:
        return db_error("Could not load your matches.")


@app.get("/api/match-suggestions")
@login_required
def match_suggestions():
    uid = current_user_id()
    try:
        return jsonify(query_all("""SELECT DISTINCT
            teacher.user_id AS teacher_id, teacher.name AS teacher_name, teacher.location,
            offered.skill_id AS their_skill_id, their_skill.skill_name AS their_skill_name,
            offered.proficiency_level, my_offer.skill_id AS my_skill_id,
            my_skill.skill_name AS my_skill_name
            FROM skillrequests my_request
            JOIN skillofferings offered
              ON offered.skill_id = my_request.skill_id
             AND offered.user_id <> my_request.user_id
            JOIN skillrequests teacher_request
              ON teacher_request.user_id = offered.user_id
            JOIN skillofferings my_offer
              ON my_offer.user_id = my_request.user_id
             AND my_offer.skill_id = teacher_request.skill_id
            JOIN users teacher ON teacher.user_id = offered.user_id
            JOIN skills their_skill ON their_skill.skill_id = offered.skill_id
            JOIN skills my_skill ON my_skill.skill_id = my_offer.skill_id
            WHERE my_request.user_id = :user_id
            ORDER BY their_skill.skill_name, teacher.name""", {"user_id": uid}))
    except Exception:
        return db_error("Could not load match suggestions.")


@app.post("/api/matches")
@login_required
def create_match():
    user_id = current_user_id()
    data = body(); missing = missing_fields(data, "other_user_id", "my_skill_id", "their_skill_id")
    if missing: return fail("Required fields: " + ", ".join(missing))
    uid, other = int(current_user_id()), int(data["other_user_id"])
    if uid == other: return fail("You cannot create a match with yourself.")
    # Current user offers my_skill and requests their_skill; other user must offer their_skill and request my_skill.
    try:
        valid = query_one("""SELECT COUNT(*) AS total FROM skillofferings a JOIN skillrequests ar ON ar.user_id=a.user_id
            JOIN skillofferings b ON b.user_id=:other AND b.skill_id=:their_skill
            JOIN skillrequests br ON br.user_id=:other AND br.skill_id=:my_skill
            WHERE a.user_id=:user_id AND a.skill_id=:my_skill AND ar.skill_id=:their_skill""",
            {"user_id":user_id,"other":other,"my_skill":data["my_skill_id"],"their_skill":data["their_skill_id"]})
        if not valid or not valid["total"]: return fail("A match requires both users to offer and request complementary skills.")
        run_sql("""INSERT INTO matches (user_a_id,user_b_id,skill_a_teaches,skill_b_teaches,status)
                    VALUES (:user_id,:other,:my_skill,:their_skill,'PENDING')""",
                {"user_id":user_id,"other":other,"my_skill":data["my_skill_id"],"their_skill":data["their_skill_id"]})
        return jsonify({"message":"Match request sent.","status":"PENDING"}), 201
    except Exception:
        return db_error("Could not create this match.")


@app.put("/api/matches/<int:match_id>/status")
@login_required
def match_status(match_id):
    data = body(); status = str(data.get("status", "")).upper()
    if status not in {"ACCEPTED", "REJECTED", "CANCELLED"}: return fail("Choose ACCEPTED, REJECTED or CANCELLED.")
    uid = current_user_id()
    try:
        # Recipient can accept/reject; either participant can cancel their pending match.
        match = query_one("SELECT user_a_id,user_b_id,status FROM matches WHERE match_id=:mid", {"mid":match_id})
        if not match or uid not in (match["user_a_id"], match["user_b_id"]): return fail("Match not found.", 404)
        if match["status"] != "PENDING": return fail("This match is no longer pending.", 409)
        if status in {"ACCEPTED", "REJECTED"} and uid == match["user_a_id"]:
            return fail("Only the recipient can accept or reject this match.", 403)
        run_sql("UPDATE matches SET status=:status WHERE match_id=:mid AND status='PENDING'", {"status":status,"mid":match_id})
        return jsonify({"message":"Match status updated.","status":status})
    except Exception:
        return db_error("Could not update match status.")


# Sessions.
@app.get("/api/my/sessions")
@login_required
def my_sessions():
    try:
        return jsonify(query_all("""SELECT se.session_id,se.match_id,ua.user_id AS user_a_id,ua.name AS user_a,
            ub.user_id AS user_b_id,ub.name AS user_b,TO_CHAR(se.scheduled_date,'YYYY-MM-DD') AS scheduled_date,
            se.start_time,se.duration_minutes,se.session_mode,se.location,se.status
            FROM sessions se JOIN matches m ON m.match_id=se.match_id JOIN users ua ON ua.user_id=m.user_a_id
            JOIN users ub ON ub.user_id=m.user_b_id WHERE m.user_a_id=:user_id OR m.user_b_id=:user_id
            ORDER BY se.scheduled_date,se.start_time""", {"user_id": current_user_id()}))
    except Exception:
        return db_error("Could not load your sessions.")


@app.post("/api/my/sessions")
@login_required
def create_session():
    data = body(); missing = missing_fields(data,"match_id","scheduled_date","start_time","duration_minutes","session_mode")
    if missing: return fail("Required fields: " + ", ".join(missing))
    mode = str(data["session_mode"]).upper(); start = str(data["start_time"])
    if mode not in SESSION_MODES: return fail("Session mode must be ONLINE or OFFLINE.")
    if not TIME_RE.fullmatch(start): return fail("Start time must use HH:MM 24-hour format.")
    try:
        duration = int(data["duration_minutes"])
        if duration <= 0: return fail("Duration must be greater than zero.")
        match = query_one("SELECT user_a_id,user_b_id,status FROM matches WHERE match_id=:mid", {"mid":data["match_id"]})
        uid = current_user_id()
        if not match or uid not in (match["user_a_id"], match["user_b_id"]): return fail("Match not found.",404)
        if match["status"] != "ACCEPTED": return fail("Only accepted matches can schedule sessions.")
        run_sql("""INSERT INTO sessions (match_id,scheduled_date,start_time,duration_minutes,session_mode,location)
                    VALUES (:p_match_id,TO_DATE(:p_scheduled_date,'YYYY-MM-DD'),:p_start_time,:p_duration_minutes,:p_session_mode,:p_location)""",
                {"p_match_id":data["match_id"],"p_scheduled_date":data["scheduled_date"],"p_start_time":start,"p_duration_minutes":duration,"p_session_mode":mode,"p_location":data.get("location")})
        return jsonify({"message":"Session scheduled."}),201
    except ValueError:
        return fail("Duration must be a whole number.")
    except Exception:
        return db_error("Could not schedule this session. Use a date in YYYY-MM-DD format.")


@app.put("/api/my/sessions/<int:session_id>/status")
@login_required
def session_status(session_id):
    status = str(body().get("status", "")).upper()
    if status not in {"SCHEDULED","COMPLETED","CANCELLED"}: return fail("Invalid session status.")
    try:
        count = run_sql("""UPDATE sessions se SET status=:status WHERE se.session_id=:sid AND EXISTS
            (SELECT 1 FROM matches m WHERE m.match_id=se.match_id AND (m.user_a_id=:user_id OR m.user_b_id=:user_id))""",
            {"status":status,"sid":session_id,"user_id":current_user_id()})
        return (jsonify({"message":"Session status updated.","status":status}),200) if count else fail("Session not found.",404)
    except Exception:
        return db_error("Could not update session status.")


# Reviews: users can review their partner only after a completed session.
@app.get("/api/my/reviews")
@login_required
def my_reviews():
    try:
        return jsonify(query_all("""SELECT r.review_id,r.session_id,r.reviewer_id,rv.name AS reviewer_name,
            r.reviewee_id,re.name AS reviewee_name,r.rating,r.feedback,r.created_at
            FROM reviews r JOIN users rv ON rv.user_id=r.reviewer_id JOIN users re ON re.user_id=r.reviewee_id
            WHERE r.reviewer_id=:user_id OR r.reviewee_id=:user_id ORDER BY r.created_at DESC""", {"user_id":current_user_id()}))
    except Exception:
        return db_error("Could not load reviews.")


@app.post("/api/my/reviews")
@login_required
def create_review():
    user_id = current_user_id()
    data = body(); missing = missing_fields(data,"session_id","reviewee_id","rating")
    if missing: return fail("Required fields: " + ", ".join(missing))
    uid = current_user_id()
    try:
        rating = int(data["rating"])
        if rating < 1 or rating > 5: return fail("Rating must be from 1 to 5.")
        if int(data["reviewee_id"]) == int(uid): return fail("You cannot review yourself.")
        valid = query_one("""SELECT se.session_id FROM sessions se JOIN matches m ON m.match_id=se.match_id
            WHERE se.session_id=:sid AND se.status='COMPLETED' AND
            ((m.user_a_id=:user_id AND m.user_b_id=:reviewee) OR (m.user_b_id=:user_id AND m.user_a_id=:reviewee))""",
            {"sid":data["session_id"],"user_id":user_id,"reviewee":data["reviewee_id"]})
        if not valid: return fail("Review requires a completed session with this user.")
        run_sql("INSERT INTO reviews (session_id,reviewer_id,reviewee_id,rating,feedback) VALUES (:sid,:user_id,:reviewee,:rating,:feedback)",
                {"sid":data["session_id"],"user_id":user_id,"reviewee":data["reviewee_id"],"rating":rating,"feedback":data.get("feedback")})
        return jsonify({"message":"Review submitted."}),201
    except ValueError:
        return fail("Rating must be a number from 1 to 5.")
    except Exception:
        return db_error("Could not submit this review. You may have already reviewed this session.")


# Profile and preferences.
@app.get("/api/my/profile")
@login_required
def my_profile():
    try:
        user = query_one("SELECT user_id,name,email,location,bio,profile_picture,created_at FROM users WHERE user_id=:user_id", {"user_id":current_user_id()})
        prefs = query_one("""SELECT preferred_mode,preferred_location,minimum_teacher_rating,
            preferred_session_duration,preferred_session_frequency FROM userpreferences WHERE user_id=:user_id""", {"user_id":current_user_id()})
        return jsonify({"user":user,"preferences":prefs})
    except Exception:
        return db_error("Could not load your profile.")


@app.patch("/api/my/profile")
@login_required
def update_profile():
    data = body(); allowed = {"name","location","bio","profile_picture"}
    if not any(k in data for k in allowed): return fail("Provide at least one profile field to update.")
    columns = {"name": "name", "location": "location", "bio": "bio", "profile_picture": "profile_picture"}
    changes = {key: data[key] for key in allowed if key in data}
    assignments = ", ".join(f"{columns[key]} = :{key}" for key in changes)
    changes["uid"] = current_user_id()
    try:
        run_sql(f"UPDATE users SET {assignments} WHERE user_id = :user_id", changes)
        return jsonify({"message": "Profile updated."})
    except Exception:
        return db_error("Could not update your profile.")


@app.put("/api/my/preferences")
@login_required
def update_preferences():
    data = body(); mode = str(data.get("preferred_mode","EITHER")).upper()
    if mode not in MODES: return fail("Preferred mode must be ONLINE, OFFLINE or EITHER.")
    try:
        rating = float(data.get("minimum_teacher_rating",0)); duration = int(data.get("preferred_session_duration",60))
        frequency = data.get("preferred_session_frequency")
        if not 0 <= rating <= 5 or duration <= 0 or (frequency not in (None, "") and int(frequency) <= 0):
            return fail("Check the rating, duration and frequency values.")
        run_sql("""MERGE INTO userpreferences p USING (SELECT :p_user_id user_id FROM dual) src ON (p.user_id=src.user_id)
            WHEN MATCHED THEN UPDATE SET p.preferred_mode=:p_mode,p.preferred_location=:p_location,
              p.minimum_teacher_rating=:p_rating,p.preferred_session_duration=:p_duration,p.preferred_session_frequency=:p_frequency
            WHEN NOT MATCHED THEN INSERT (user_id,preferred_mode,preferred_location,minimum_teacher_rating,preferred_session_duration,preferred_session_frequency)
              VALUES (:p_user_id,:p_mode,:p_location,:p_rating,:p_duration,:p_frequency)""",
            {"p_user_id":current_user_id(),"p_mode":mode,"p_location":data.get("preferred_location"),"p_rating":rating,"p_duration":duration,"p_frequency":int(frequency) if frequency not in (None,"") else None})
        return jsonify({"message":"Preferences saved."})
    except (ValueError, TypeError):
        return fail("Check the rating, duration and frequency values.")
    except Exception:
        return db_error("Could not save preferences.")


@app.get("/api/my/availability")
@login_required
def my_availability():
    try:
        return jsonify(query_all("SELECT availability_id,day_of_week,start_time,end_time FROM availability WHERE user_id=:user_id ORDER BY day_of_week,start_time", {"user_id":current_user_id()}))
    except Exception:
        return db_error("Could not load availability.")


@app.post("/api/my/availability")
@login_required
def add_availability():
    data=body(); missing=missing_fields(data,"day_of_week","start_time","end_time")
    if missing: return fail("Required fields: " + ", ".join(missing))
    day=str(data["day_of_week"]).upper(); start=str(data["start_time"]); end=str(data["end_time"])
    if day not in DAYS: return fail("Choose a valid day.")
    if not TIME_RE.fullmatch(start) or not TIME_RE.fullmatch(end) or start >= end: return fail("Use valid HH:MM times with start before end.")
    try:
        run_sql(
        "INSERT INTO availability (user_id,day_of_week,start_time,end_time) "
        "VALUES (:p_user_id,:p_day,:p_start_time,:p_end_time)",
        {
            "p_user_id": current_user_id(),
            "p_day": day,
            "p_start_time": start,
            "p_end_time": end
        }
    )
        return jsonify({"message":"Availability added."}),201
    except Exception:
        return db_error("Could not add availability.")


@app.delete("/api/my/availability/<int:availability_id>")
@login_required
def remove_availability(availability_id):
    try:
        count=run_sql("DELETE FROM availability WHERE availability_id=:aid AND user_id=:user_id", {"aid":availability_id,"user_id":current_user_id()})
        return (jsonify({"message":"Availability removed."}),200) if count else fail("Availability not found.",404)
    except Exception:
        return db_error("Could not remove availability.")


@app.get("/api/users/<int:user_id>/rating")
def user_rating(user_id):
    try:
        result=query_one("""SELECT u.user_id,u.name,ROUND(AVG(r.rating),2) AS average_rating,COUNT(r.review_id) AS total_reviews
            FROM users u LEFT JOIN reviews r ON r.reviewee_id=u.user_id WHERE u.user_id=:user_id GROUP BY u.user_id,u.name""", {"user_id":user_id})
        return (jsonify(result),200) if result else fail("User not found.",404)
    except Exception:
        return db_error("Could not load rating.")


@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith("/api/"):
        return fail("API endpoint not found. Check the frontend/backend route paths.", 404)
    return fail("Page not found.", 404)


@app.errorhandler(405)
def method_not_allowed(_error):
    if request.path.startswith("/api/"):
        allowed = request.url_rule.methods if request.url_rule else set()
        return jsonify({
            "error": "HTTP method not allowed for this API endpoint.",
            "path": request.path,
            "method": request.method,
            "allowed_methods": sorted(allowed),
        }), 405
    return fail("This HTTP method is not allowed for this page.", 405)


@app.errorhandler(500)
def internal_error(_error):
    if request.path.startswith("/api/"):
        app.logger.exception("Unhandled API error")
        return fail("Unexpected server error. Check the Flask terminal for details.", 500)
    return fail("Unexpected server error.", 500)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", "5000")))
