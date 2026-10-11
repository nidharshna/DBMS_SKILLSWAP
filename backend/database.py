
import oracledb


def get_connection():
    return oracledb.connect(
        user="SKILLSWAP",
        password="SkillSwap123",
        dsn="localhost:1521/FREEPDB1"
    )
