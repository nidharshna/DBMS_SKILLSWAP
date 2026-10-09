
-- 06_triggers.sql
-- SkillSwap: Review validation trigger
-- Only completed sessions can receive reviews.

CREATE OR REPLACE TRIGGER TRG_REVIEW_COMPLETED_SESSION
BEFORE INSERT OR UPDATE OF SESSION_ID ON REVIEWS
FOR EACH ROW
DECLARE
    v_session_status SESSIONS.STATUS%TYPE;
BEGIN
    SELECT STATUS
    INTO v_session_status
    FROM SESSIONS
    WHERE SESSION_ID = :NEW.SESSION_ID;

    IF v_session_status <> 'COMPLETED' THEN
        RAISE_APPLICATION_ERROR(
            -20001,
            'Reviews can only be submitted for completed sessions.'
        );
    END IF;

EXCEPTION
    WHEN NO_DATA_FOUND THEN
        RAISE_APPLICATION_ERROR(
            -20002,
            'The specified session does not exist.'
        );
END;
/