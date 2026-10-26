import oracledb


def get_connection():
    """Create and return a connection to the SkillSwap Oracle database."""
    return oracledb.connect(
        user="SKILLSWAP",
        password="SkillSwap123",
        dsn="localhost:1521/FREEPDB1"
    )