import oracledb
from app.config import settings

pool = None

def init_pool():
    global pool
    if pool is None:
        pool = oracledb.create_pool(
            user=settings.db_user,
            password=settings.db_password,
            dsn=settings.db_dsn,
            min=2,
            max=10,
            increment=1
        )

def close_pool():
    global pool
    if pool is not None:
        pool.close()
        pool = None

def get_connection():
    connection = pool.acquire()
    try:
        yield connection
    finally:
        pool.release(connection)