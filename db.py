import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

db_pool = None

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(dsn=os.getenv("DATABASE_URL"))
