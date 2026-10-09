
-- 05_procedures.sql
-- SkillSwap: Stored Procedures

-- PROCEDURE 1: Display skills a user can teach

CREATE OR REPLACE PROCEDURE GET_USER_SKILLS (
    p_user_id IN NUMBER
)
AS
    v_user_name USERS.NAME%TYPE;
    v_count NUMBER := 0;
BEGIN
    SELECT NAME
    INTO v_user_name
    FROM USERS
    WHERE USER_ID = p_user_id;

    DBMS_OUTPUT.PUT_LINE('Skills taught by: ' || v_user_name);

    FOR rec IN (
        SELECT S.SKILL_NAME, SO.PROFICIENCY_LEVEL
        FROM SKILLOFFERINGS SO
        JOIN SKILLS S ON SO.SKILL_ID = S.SKILL_ID
        WHERE SO.USER_ID = p_user_id
    )
    LOOP
        DBMS_OUTPUT.PUT_LINE(
            rec.SKILL_NAME || ' - ' || rec.PROFICIENCY_LEVEL
        );
        v_count := v_count + 1;
    END LOOP;

    IF v_count = 0 THEN
        DBMS_OUTPUT.PUT_LINE('No teaching skills found.');
    END IF;

EXCEPTION
    WHEN NO_DATA_FOUND THEN
        DBMS_OUTPUT.PUT_LINE('User ID not found.');
END;
/

-- PROCEDURE 2: Display skills a user wants to learn

CREATE OR REPLACE PROCEDURE GET_USER_REQUESTS (
    p_user_id IN NUMBER
)
AS
    v_user_name USERS.NAME%TYPE;
    v_count NUMBER := 0;
BEGIN
    SELECT NAME
    INTO v_user_name
    FROM USERS
    WHERE USER_ID = p_user_id;

    DBMS_OUTPUT.PUT_LINE('Skills requested by: ' || v_user_name);

    FOR rec IN (
        SELECT S.SKILL_NAME, SR.EXPECTED_TEACHER_PROFICIENCY
        FROM SKILLREQUESTS SR
        JOIN SKILLS S ON SR.SKILL_ID = S.SKILL_ID
        WHERE SR.USER_ID = p_user_id
    )
    LOOP
        DBMS_OUTPUT.PUT_LINE(
            rec.SKILL_NAME || ' - Expected teacher level: ' ||
            rec.EXPECTED_TEACHER_PROFICIENCY
        );
        v_count := v_count + 1;
    END LOOP;

    IF v_count = 0 THEN
        DBMS_OUTPUT.PUT_LINE('No learning requests found.');
    END IF;

EXCEPTION
    WHEN NO_DATA_FOUND THEN
        DBMS_OUTPUT.PUT_LINE('User ID not found.');
END;
/

-- Enable output and test both procedures

SET SERVEROUTPUT ON;

EXEC GET_USER_SKILLS(1);

EXEC GET_USER_REQUESTS(1);