import os

from sqlalchemy import MetaData, inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.models.schema import Pet

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./petadvice.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    if DATABASE_URL.startswith("sqlite"):
        inspector = inspect(engine)
        pet_columns = inspector.get_columns("pet") if "pet" in inspector.get_table_names() else []
        owner_column = next((column for column in pet_columns if column["name"] == "owner_id"), None)
        if owner_column and owner_column["nullable"] is False:
            with engine.begin() as connection:
                connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
                connection.exec_driver_sql("ALTER TABLE pet RENAME TO pet_legacy")
                new_table = Pet.__table__.to_metadata(MetaData(), name="pet_new")
                new_table.create(connection)
                columns = [column.name for column in new_table.columns]
                column_sql = ", ".join(columns)
                connection.execute(
                    text(
                        f"INSERT INTO pet_new ({column_sql}) "
                        f"SELECT {column_sql} FROM pet_legacy"
                    )
                )
                connection.exec_driver_sql("DROP TABLE pet_legacy")
                connection.exec_driver_sql("ALTER TABLE pet_new RENAME TO pet")
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
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
