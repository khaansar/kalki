import certifi
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings

settings = get_settings()

connect_args = (
    {"ssl": {"ca": settings.mysql_tls_ca_path or certifi.where(), "check_hostname": True}}
    if settings.mysql_tls_enabled
    else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(engine, expire_on_commit=False)
