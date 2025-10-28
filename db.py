import asyncpg
import os

db_pool = None

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(dsn=os.environ["DATABASE_URL"])
