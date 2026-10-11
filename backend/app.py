
from flask import Flask, jsonify, request
from database import get_connection

app = Flask(__name__)


# --------------------------------------------------
# DATABASE HELPERS
# --------------------------------------------------

def fetch_all(sql, params=None):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(sql, params or {})
        columns = [col[0].lower() for col in cursor.description]

        return [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]

    finally:
        cursor.close()
        connection.close()


def execute(sql, params=None):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(sql, params or {})
        connection.commit()
        return cursor.rowcount

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


def error_response(message, status=400):
    return jsonify({"error": message}), status


def required(data, *fields):
    return [
        field for field in fields
        if field not in data or data[field] is None or data[field] == ""
    ]


# --------------------------------------------------
# 1. HOME
# --------------------------------------------------

@app.route("/")
def home():
    return jsonify({
        "message": "Welcome to SkillSwap API",
        "status": "running"
    })


# --------------------------------------------------
# 2. USERS
# --------------------------------------------------

@app.route("/users", methods=["GET"])
def get_users():
    try:
        users = fetch_all("""
            SELECT user_id, name, email, location, bio,
                   profile_picture, created_at
            FROM users
            ORDER BY user_id
        """)
        return jsonify(users)

    except Exception as e:
        return error_response(str(e), 500)


@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    try:
        users = fetch_all("""
            SELECT user_id, name, email, location, bio,
                   profile_picture, created_at
            FROM users
            WHERE user_id = :user_id
        """, {"user_id": user_id})

        if not users:
            return error_response("User not found.", 404)

        return jsonify(users[0])

    except Exception as e:
        return error_response(str(e), 500)


@app.route("/users", methods=["POST"])
def create_user():
    data = request.get_json(silent=True) or {}

    missing = required(data, "name", "email", "password")
    if missing:
        return error_response(
            "Required fields: " + ", ".join(missing)
        )

    try:
        execute("""
            INSERT INTO users (name, email, password_hash, location, bio)
            VALUES (
                :name, :email, :password, :location, :bio
            )
        """, {
            "name": data["name"],
            "email": data["email"],
            "password": data["password"],
            "location": data.get("location"),
            "bio": data.get("bio")
        })

        return jsonify({
            "message": "User registered successfully."
        }), 201

    except Exception as e:
        return error_response(str(e), 400)


# --------------------------------------------------
# 3. CATEGORIES AND SKILLS
# --------------------------------------------------

@app.route("/categories", methods=["GET"])
def get_categories():
    try:
        return jsonify(fetch_all("""
            SELECT category_id, category_name, description
            FROM categories
            ORDER BY category_name
        """))

    except Exception as e:
        return error_response(str(e), 500)


@app.route("/skills", methods=["GET"])
def get_skills():
    try:
        return jsonify(fetch_all("""
            SELECT s.skill_id, s.skill_name, s.description,
                   c.category_id, c.category_name
            FROM skills s
            JOIN categories c
              ON c.category_id = s.category_id
            ORDER BY s.skill_id
        """))

    except Exception as e:
        return error_response(str(e), 500)


# --------------------------------------------------
# 4. SKILL OFFERINGS: WHAT USERS CAN TEACH
# --------------------------------------------------

@app.route("/offerings", methods=["GET"])
def get_offerings():
    try:
        return jsonify(fetch_all("""
            SELECT so.offering_id, so.user_id, u.name,
                   so.skill_id, s.skill_name,
                   so.proficiency_level
            FROM skillofferings so
            JOIN users u ON u.user_id = so.user_id
            JOIN skills s ON s.skill_id = so.skill_id
            ORDER BY so.offering_id
        """))

    except Exception as e:
        return error_response(str(e), 500)


@app.route("/users/<int:user_id>/offerings", methods=["GET"])
def get_user_offerings(user_id):
    try:
        return jsonify(fetch_all("""
            SELECT so.offering_id, so.user_id, so.skill_id,
                   s.skill_name, so.proficiency_level
            FROM skillofferings so
            JOIN skills s ON s.skill_id = so.skill_id
            WHERE so.user_id = :user_id
            ORDER BY s.skill_name
        """, {"user_id": user_id}))

    except Exception as e:
        return error_response(str(e), 500)


@app.route("/offerings", methods=["POST"])
def create_offering():
    data = request.get_json(silent=True) or {}

    missing = required(
        data, "user_id", "skill_id", "proficiency_level"
    )
    if missing:
        return error_response(
            "Required fields: " + ", ".join(missing)
        )

    level = str(data["proficiency_level"]).upper()
    allowed = {"BEGINNER", "INTERMEDIATE", "ADVANCED", "EXPERT"}

    if level not in allowed:
        return error_response(
            "Proficiency must be BEGINNER, INTERMEDIATE, ADVANCED or EXPERT."
        )

    try:
        execute("""
            INSERT INTO skillofferings
                (user_id, skill_id, proficiency_level)
            VALUES
                (:user_id, :skill_id, :level)
        """, {
            "user_id": data["user_id"],
            "skill_id": data["skill_id"],
            "level": level
        })

        return jsonify({
            "message": "Skill offering added successfully."
        }), 201

    except Exception as e:
        return error_response(str(e), 400)


@app.route("/offerings/<int:offering_id>", methods=["DELETE"])
def delete_offering(offering_id):
    try:
        count = execute("""
            DELETE FROM skillofferings
            WHERE offering_id = :offering_id
        """, {"offering_id": offering_id})

        if count == 0:
            return error_response("Offering not found.", 404)

        return jsonify({"message": "Offering deleted."})

    except Exception as e:
        return error_response(str(e), 400)


# --------------------------------------------------
# 5. SKILL REQUESTS: WHAT USERS WANT TO LEARN
# --------------------------------------------------

@app.route("/requests", methods=["GET"])
def get_requests():
    try:
        return jsonify(fetch_all("""
            SELECT sr.request_id, sr.user_id, u.name,
                   sr.skill_id, s.skill_name,
                   sr.expected_teacher_proficiency
            FROM skillrequests sr
            JOIN users u ON u.user_id = sr.user_id
            JOIN skills s ON s.skill_id = sr.skill_id
            ORDER BY sr.request_id
        """))

    except Exception as e:
        return error_response(str(e), 500)


@app.route("/users/<int:user_id>/requests", methods=["GET"])
def get_user_requests(user_id):
    try:
        return jsonify(fetch_all("""
            SELECT sr.request_id, sr.user_id, sr.skill_id,
                   s.skill_name, sr.expected_teacher_proficiency
            FROM skillrequests sr
            JOIN skills s ON s.skill_id = sr.skill_id
            WHERE sr.user_id = :user_id
            ORDER BY s.skill_name
        """, {"user_id": user_id}))

    except Exception as e:
        return error_response(str(e), 500)


@app.route("/requests", methods=["POST"])
def create_request():
    data = request.get_json(silent=True) or {}

    missing = required(
        data, "user_id", "skill_id", "expected_teacher_proficiency"
    )
    if missing:
        return error_response(
            "Required fields: " + ", ".join(missing)
        )

    level = str(data["expected_teacher_proficiency"]).upper()
    allowed = {"BEGINNER", "INTERMEDIATE", "ADVANCED", "EXPERT"}

    if level not in allowed:
        return error_response(
            "Teacher proficiency must be BEGINNER, INTERMEDIATE, "
            "ADVANCED or EXPERT."
        )

    try:
        execute("""
            INSERT INTO skillrequests
                (user_id, skill_id, expected_teacher_proficiency)
            VALUES
                (:user_id, :skill_id, :level)
        """, {
            "user_id": data["user_id"],
            "skill_id": data["skill_id"],
            "level": level
        })

        return jsonify({
            "message": "Skill request added successfully."
        }), 201

    except Exception as e:
        return error_response(str(e), 400)


@app.route("/requests/<int:request_id>", methods=["DELETE"])
def delete_request(request_id):
    try:
        count = execute("""
            DELETE FROM skillrequests
            WHERE request_id = :request_id
        """, {"request_id": request_id})

        if count == 0:
            return error_response("Skill request not found.", 404)

        return jsonify({"message": "Skill request deleted."})

    except Exception as e:
        return error_response(str(e), 400)


# --------------------------------------------------
# 6. USER PREFERENCES
# --------------------------------------------------

@app.route("/users/<int:user_id>/preferences", methods=["GET"])
def get_preferences(user_id):
    try:
        preferences = fetch_all("""
            SELECT preference_id, user_id, preferred_mode,
                   preferred_location, minimum_teacher_rating,
                   preferred_session_duration,
                   preferred_session_frequency
            FROM userpreferences
            WHERE user_id = :user_id
        """, {"user_id": user_id})

        if not preferences:
            return error_response("Preferences not found.", 404)

        return jsonify(preferences[0])

    except Exception as e:
        return error_response(str(e), 500)


@app.route("/users/<int:user_id>/preferences", methods=["PUT"])
def save_preferences(user_id):
    data = request.get_json(silent=True) or {}

    mode = str(data.get("preferred_mode", "EITHER")).upper()
    if mode not in {"ONLINE", "OFFLINE", "EITHER"}:
        return error_response(
            "preferred_mode must be ONLINE, OFFLINE or EITHER."
        )

    try:
        execute("""
            MERGE INTO userpreferences p
            USING (SELECT :user_id AS user_id FROM dual) src
            ON (p.user_id = src.user_id)
            WHEN MATCHED THEN UPDATE SET
                p.preferred_mode = :mode,
                p.preferred_location = :location,
                p.minimum_teacher_rating = :rating,
                p.preferred_session_duration = :duration,
                p.preferred_session_frequency = :frequency
            WHEN NOT MATCHED THEN INSERT (
                user_id, preferred_mode, preferred_location,
                minimum_teacher_rating, preferred_session_duration,
                preferred_session_frequency
            ) VALUES (
                :user_id, :mode, :location, :rating, :duration,
                :frequency
            )
        """, {
            "user_id": user_id,
            "mode": mode,
            "location": data.get("preferred_location"),
            "rating": data.get("minimum_teacher_rating", 0),
            "duration": data.get("preferred_session_duration", 60),
            "frequency": data.get("preferred_session_frequency")
        })

        return jsonify({"message": "Preferences saved."})

    except Exception as e:
        return error_response(str(e), 400)


# --------------------------------------------------
# 7. AVAILABILITY
# --------------------------------------------------

@app.route("/availability", methods=["GET"])
def get_availability():
    try:
        return jsonify(fetch_all("""
            SELECT a.availability_id, a.user_id, u.name,
                   a.day_of_week, a.start_time, a.end_time
            FROM availability a
            JOIN users u ON u.user_id = a.user_id
            ORDER BY a.user_id, a.day_of_week, a.start_time
        """))

    except Exception as e:
        return error_response(str(e), 500)


@app.route("/users/<int:user_id>/availability", methods=["GET"])
def get_user_availability(user_id):
    try:
        return jsonify(fetch_all("""
            SELECT availability_id, user_id, day_of_week,
                   start_time, end_time
            FROM availability
            WHERE user_id = :user_id
            ORDER BY day_of_week, start_time
        """, {"user_id": user_id}))

    except Exception as e:
        return error_response(str(e), 500)


@app.route("/availability", methods=["POST"])
def create_availability():
    data = request.get_json(silent=True) or {}

    missing = required(
        data, "user_id", "day_of_week", "start_time", "end_time"
    )
    if missing:
        return error_response(
            "Required fields: " + ", ".join(missing)
        )

    day = str(data["day_of_week"]).upper()
    days = {
        "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY",
        "FRIDAY", "SATURDAY", "SUNDAY"
    }

    if day not in days:
        return error_response("Invalid day_of_week.")

    start = str(data["start_time"])
    end = str(data["end_time"])

    # Validate 24-hour HH:MM format and ensure start precedes end.
    import re
    pattern = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"

    if not re.fullmatch(pattern, start) or not re.fullmatch(pattern, end):
        return error_response("Times must use 24-hour HH:MM format.")

    if start >= end:
        return error_response("start_time must be earlier than end_time.")

    try:
        execute("""
            INSERT INTO availability
                (user_id, day_of_week, start_time, end_time)
            VALUES
                (:user_id, :day, :start_time, :end_time)
        """, {
            "user_id": data["user_id"],
            "day": day,
            "start_time": start,
            "end_time": end
        })

        return jsonify({"message": "Availability added."}), 201

    except Exception as e:
        return error_response(str(e), 400)


@app.route("/availability/<int:availability_id>", methods=["DELETE"])
def delete_availability(availability_id):
    try:
        count = execute("""
            DELETE FROM availability
            WHERE availability_id = :availability_id
        """, {"availability_id": availability_id})

        if count == 0:
            return error_response("Availability record not found.", 404)

        return jsonify({"message": "Availability deleted."})

    except Exception as e:
        return error_response(str(e), 400)


# --------------------------------------------------
# 8. MATCHES
# --------------------------------------------------

@app.route("/matches", methods=["GET"])
def get_matches():
    try:
        return jsonify(fetch_all("""
            SELECT m.match_id, m.user_a_id, ua.name AS user_a,
                   m.user_b_id, ub.name AS user_b,
                   m.skill_a_teaches, sa.skill_name AS user_a_teaches,
                   m.skill_b_teaches, sb.skill_name AS user_b_teaches,
                   m.status, m.created_at
            FROM matches m
            JOIN users ua ON ua.user_id = m.user_a_id
            JOIN users ub ON ub.user_id = m.user_b_id
            JOIN skills sa ON sa.skill_id = m.skill_a_teaches
            JOIN skills sb ON sb.skill_id = m.skill_b_teaches
            ORDER BY m.match_id
        """))

    except Exception as e:
        return error_response(str(e), 500)


@app.route("/users/<int:user_id>/matches", methods=["GET"])
def get_user_matches(user_id):
    try:
        return jsonify(fetch_all("""
            SELECT m.match_id, m.user_a_id, ua.name AS user_a,
                   m.user_b_id, ub.name AS user_b,
                   sa.skill_name AS user_a_teaches,
                   sb.skill_name AS user_b_teaches,
                   m.status, m.created_at
            FROM matches m
            JOIN users ua ON ua.user_id = m.user_a_id
            JOIN users ub ON ub.user_id = m.user_b_id
            JOIN skills sa ON sa.skill_id = m.skill_a_teaches
            JOIN skills sb ON sb.skill_id = m.skill_b_teaches
            WHERE m.user_a_id = :user_id
               OR m.user_b_id = :user_id
            ORDER BY m.match_id
        """, {"user_id": user_id}))

    except Exception as e:
        return error_response(str(e), 500)


@app.route("/match-suggestions/<int:user_id>", methods=["GET"])
def match_suggestions(user_id):
    try:
        suggestions = fetch_all("""
            SELECT
                teacher.user_id AS teacher_id,
                teacher.name AS teacher_name,
                skill.skill_id,
                skill.skill_name,
                offering.proficiency_level
            FROM skillrequests request
            JOIN skillofferings offering
              ON offering.skill_id = request.skill_id
             AND offering.user_id <> request.user_id
            JOIN users teacher
              ON teacher.user_id = offering.user_id
            JOIN skills skill
              ON skill.skill_id = request.skill_id
            WHERE request.user_id = :user_id
            ORDER BY skill.skill_name, teacher.name
        """, {"user_id": user_id})

        return jsonify(suggestions)

    except Exception as e:
        return error_response(str(e), 500)


@app.route("/matches", methods=["POST"])
def create_match():
    data = request.get_json(silent=True) or {}

    missing = required(
        data, "user_a_id", "user_b_id",
        "skill_a_teaches", "skill_b_teaches"
    )
    if missing:
        return error_response(
            "Required fields: " + ", ".join(missing)
        )

    a = data["user_a_id"]
    b = data["user_b_id"]
    skill_a = data["skill_a_teaches"]
    skill_b = data["skill_b_teaches"]

    if a == b:
        return error_response("A user cannot match with themselves.")

    try:
        # User A must offer skill A and request skill B.
        a_valid = fetch_all("""
            SELECT COUNT(*) AS total
            FROM skillofferings o
            JOIN skillrequests r ON r.user_id = o.user_id
            WHERE o.user_id = :user_a
              AND o.skill_id = :skill_a
              AND r.skill_id = :skill_b
        """, {
            "user_a": a,
            "skill_a": skill_a,
            "skill_b": skill_b
        })[0]["total"]

        # User B must offer skill B and request skill A.
        b_valid = fetch_all("""
            SELECT COUNT(*) AS total
            FROM skillofferings o
            JOIN skillrequests r ON r.user_id = o.user_id
            WHERE o.user_id = :user_b
              AND o.skill_id = :skill_b
              AND r.skill_id = :skill_a
        """, {
            "user_b": b,
            "skill_b": skill_b,
            "skill_a": skill_a
        })[0]["total"]

        if not a_valid or not b_valid:
            return error_response(
                "A match requires reciprocal skill offerings and requests."
            )

        execute("""
            INSERT INTO matches (
                user_a_id, user_b_id, skill_a_teaches,
                skill_b_teaches, status
            )
            VALUES (
                :user_a, :user_b, :skill_a, :skill_b, 'PENDING'
            )
        """, {
            "user_a": a,
            "user_b": b,
            "skill_a": skill_a,
            "skill_b": skill_b
        })

        return jsonify({
            "message": "Match request created.",
            "status": "PENDING"
        }), 201

    except Exception as e:
        return error_response(str(e), 400)


@app.route("/matches/<int:match_id>/status", methods=["PUT"])
def update_match_status(match_id):
    data = request.get_json(silent=True) or {}
    status = str(data.get("status", "")).upper()

    allowed = {"ACCEPTED", "REJECTED", "CANCELLED"}

    if status not in allowed:
        return error_response(
            "Status must be ACCEPTED, REJECTED or CANCELLED."
        )

    try:
        count = execute("""
            UPDATE matches
            SET status = :status
            WHERE match_id = :match_id
              AND status = 'PENDING'
        """, {"status": status, "match_id": match_id})

        if count == 0:
            return error_response(
                "Pending match not found; its status may already have changed.",
                404
            )

        return jsonify({
            "message": "Match status updated.",
            "status": status
        })

    except Exception as e:
        return error_response(str(e), 400)


# --------------------------------------------------
# 9. SESSIONS
# --------------------------------------------------

@app.route("/sessions", methods=["GET"])
def get_sessions():
    try:
        return jsonify(fetch_all("""
            SELECT se.session_id, se.match_id,
                   ua.user_id AS user_a_id, ua.name AS user_a,
                   ub.user_id AS user_b_id, ub.name AS user_b,
                   TO_CHAR(se.scheduled_date, 'YYYY-MM-DD')
                       AS scheduled_date,
                   se.start_time, se.duration_minutes,
                   se.session_mode, se.location, se.status
            FROM sessions se
            JOIN matches m ON m.match_id = se.match_id
            JOIN users ua ON ua.user_id = m.user_a_id
            JOIN users ub ON ub.user_id = m.user_b_id
            ORDER BY se.scheduled_date, se.start_time
        """))

    except Exception as e:
        return error_response(str(e), 500)


@app.route("/users/<int:user_id>/sessions", methods=["GET"])
def get_user_sessions(user_id):
    try:
        return jsonify(fetch_all("""
            SELECT se.session_id, se.match_id,
                   TO_CHAR(se.scheduled_date, 'YYYY-MM-DD')
                       AS scheduled_date,
                   se.start_time, se.duration_minutes,
                   se.session_mode, se.location, se.status
            FROM sessions se
            JOIN matches m ON m.match_id = se.match_id
            WHERE m.user_a_id = :user_id
               OR m.user_b_id = :user_id
            ORDER BY se.scheduled_date, se.start_time
        """, {"user_id": user_id}))

    except Exception as e:
        return error_response(str(e), 500)


@app.route("/sessions", methods=["POST"])
def create_session():
    data = request.get_json(silent=True) or {}

    missing = required(
        data, "match_id", "scheduled_date", "start_time",
        "duration_minutes", "session_mode"
    )
    if missing:
        return error_response(
            "Required fields: " + ", ".join(missing)
        )

    mode = str(data["session_mode"]).upper()
    if mode not in {"ONLINE", "OFFLINE"}:
        return error_response("session_mode must be ONLINE or OFFLINE.")

    start = str(data["start_time"])
    import re
    if not re.fullmatch(r"^([01][0-9]|2[0-3]):[0-5][0-9]$", start):
        return error_response("start_time must use 24-hour HH:MM format.")

    try:
        # Only accepted matches can have sessions scheduled.
        accepted = fetch_all("""
            SELECT match_id
            FROM matches
            WHERE match_id = :match_id
              AND status = 'ACCEPTED'
        """, {"match_id": data["match_id"]})

        if not accepted:
            return error_response(
                "A session can only be scheduled for an accepted match."
            )

        execute("""
            INSERT INTO sessions (
                match_id, scheduled_date, start_time,
                duration_minutes, session_mode, location
            )
            VALUES (
                :match_id,
                TO_DATE(:scheduled_date, 'YYYY-MM-DD'),
                :start_time, :duration, :session_mode_value, :location
            )
        """, {
            "match_id": data["match_id"],
            "scheduled_date": data["scheduled_date"],
            "start_time": start,
            "duration": data["duration_minutes"],
            "session_mode_value": mode,
            "location": data.get("location")
        })

        return jsonify({"message": "Session scheduled."}), 201

    except Exception as e:
        return error_response(str(e), 400)


@app.route("/sessions/<int:session_id>/status", methods=["PUT"])
def update_session_status(session_id):
    data = request.get_json(silent=True) or {}
    status = str(data.get("status", "")).upper()

    if status not in {"SCHEDULED", "COMPLETED", "CANCELLED"}:
        return error_response(
            "Status must be SCHEDULED, COMPLETED or CANCELLED."
        )

    try:
        count = execute("""
            UPDATE sessions
            SET status = :status
            WHERE session_id = :session_id
        """, {"status": status, "session_id": session_id})

        if count == 0:
            return error_response("Session not found.", 404)

        return jsonify({
            "message": "Session status updated.",
            "status": status
        })

    except Exception as e:
        return error_response(str(e), 400)


# --------------------------------------------------
# 10. REVIEWS
# --------------------------------------------------

@app.route("/reviews", methods=["GET"])
def get_reviews():
    try:
        return jsonify(fetch_all("""
            SELECT r.review_id, r.session_id,
                   r.reviewer_id, reviewer.name AS reviewer_name,
                   r.reviewee_id, reviewee.name AS reviewee_name,
                   r.rating, r.feedback, r.created_at
            FROM reviews r
            JOIN users reviewer
              ON reviewer.user_id = r.reviewer_id
            JOIN users reviewee
              ON reviewee.user_id = r.reviewee_id
            ORDER BY r.review_id
        """))

    except Exception as e:
        return error_response(str(e), 500)


@app.route("/users/<int:user_id>/reviews", methods=["GET"])
def get_user_reviews(user_id):
    try:
        return jsonify(fetch_all("""
            SELECT r.review_id, r.session_id,
                   r.reviewer_id, reviewer.name AS reviewer_name,
                   r.reviewee_id, r.rating, r.feedback, r.created_at
            FROM reviews r
            JOIN users reviewer
              ON reviewer.user_id = r.reviewer_id
            WHERE r.reviewee_id = :user_id
            ORDER BY r.created_at DESC
        """, {"user_id": user_id}))

    except Exception as e:
        return error_response(str(e), 500)


@app.route("/reviews", methods=["POST"])
def create_review():
    data = request.get_json(silent=True) or {}

    missing = required(
        data, "session_id", "reviewer_id",
        "reviewee_id", "rating"
    )
    if missing:
        return error_response(
            "Required fields: " + ", ".join(missing)
        )

    if data["reviewer_id"] == data["reviewee_id"]:
        return error_response("Users cannot review themselves.")

    try:
        # Verify the session exists, is completed, and includes both users.
        valid = fetch_all("""
            SELECT se.session_id
            FROM sessions se
            JOIN matches m ON m.match_id = se.match_id
            WHERE se.session_id = :session_id
              AND se.status = 'COMPLETED'
              AND (
                  (m.user_a_id = :reviewer AND m.user_b_id = :reviewee)
                  OR
                  (m.user_b_id = :reviewer AND m.user_a_id = :reviewee)
              )
        """, {
            "session_id": data["session_id"],
            "reviewer": data["reviewer_id"],
            "reviewee": data["reviewee_id"]
        })

        if not valid:
            return error_response(
                "The session must be completed and both users "
                "must be its participants."
            )

        rating = int(data["rating"])
        if rating < 1 or rating > 5:
            return error_response("Rating must be between 1 and 5.")

        execute("""
            INSERT INTO reviews (
                session_id, reviewer_id, reviewee_id, rating, feedback
            )
            VALUES (
                :session_id, :reviewer_id, :reviewee_id,
                :rating, :feedback
            )
        """, {
            "session_id": data["session_id"],
            "reviewer_id": data["reviewer_id"],
            "reviewee_id": data["reviewee_id"],
            "rating": rating,
            "feedback": data.get("feedback")
        })

        return jsonify({"message": "Review submitted successfully."}), 201

    except Exception as e:
        return error_response(str(e), 400)


# --------------------------------------------------
# 11. USER RATING SUMMARY
# --------------------------------------------------

@app.route("/users/<int:user_id>/rating", methods=["GET"])
def get_user_rating(user_id):
    try:
        result = fetch_all("""
            SELECT u.user_id, u.name,
                   ROUND(AVG(r.rating), 2) AS average_rating,
                   COUNT(r.review_id) AS total_reviews
            FROM users u
            LEFT JOIN reviews r ON r.reviewee_id = u.user_id
            WHERE u.user_id = :user_id
            GROUP BY u.user_id, u.name
        """, {"user_id": user_id})

        if not result:
            return error_response("User not found.", 404)

        return jsonify(result[0])

    except Exception as e:
        return error_response(str(e), 500)


# --------------------------------------------------
# 12. DASHBOARD SUMMARY
# --------------------------------------------------

@app.route("/users/<int:user_id>/dashboard", methods=["GET"])
def get_dashboard(user_id):
    try:
        user = fetch_all("""
            SELECT user_id, name, email, location, bio
            FROM users
            WHERE user_id = :user_id
        """, {"user_id": user_id})

        if not user:
            return error_response("User not found.", 404)

        counts = fetch_all("""
            SELECT
                (SELECT COUNT(*) FROM skillofferings
                 WHERE user_id = :uid1) AS skills_offered,
                (SELECT COUNT(*) FROM skillrequests
                 WHERE user_id = :uid2) AS skills_requested,
                (SELECT COUNT(*) FROM matches
                 WHERE (user_a_id = :uid3 OR user_b_id = :uid4)
                   AND status = 'ACCEPTED') AS accepted_matches,
                (SELECT COUNT(*) FROM sessions se
                 JOIN matches m ON m.match_id = se.match_id
                 WHERE (m.user_a_id = :uid5 OR m.user_b_id = :uid6)
                   AND se.status = 'SCHEDULED') AS upcoming_sessions
            FROM dual
        """, {
            "uid1": user_id,
            "uid2": user_id,
            "uid3": user_id,
            "uid4": user_id,
            "uid5": user_id,
            "uid6": user_id
        })[0]

        rating = fetch_all("""
            SELECT ROUND(AVG(rating), 2) AS average_rating,
                   COUNT(*) AS total_reviews
            FROM reviews
            WHERE reviewee_id = :user_id
        """, {"user_id": user_id})[0]

        return jsonify({
            "user": user[0],
            "summary": counts,
            "rating": rating
        })

    except Exception as e:
        return error_response(str(e), 500)


# --------------------------------------------------
# START SERVER
# Keep this block at the very bottom.
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
