import os

from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./petadvice.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    if DATABASE_URL.startswith("sqlite"):
        inspector = inspect(engine)
        if "triagesession" in inspector.get_table_names():
            columns = {column["name"] for column in inspector.get_columns("triagesession")}
        else:
            columns = set()
        if "triagesession" in inspector.get_table_names() and "current_question_id" not in columns:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "ALTER TABLE triagesession ADD COLUMN current_question_id VARCHAR"
                )


def get_session():
    with Session(engine) as session:
        yield session
