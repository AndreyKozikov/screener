from sqlmodel import create_engine, Session
from pathlib import Path

class DataBase:
    def __init__(self, db_path: Path):
        self.engine = create_engine(f"sqlite:///{db_path}")

    def get_session(self) -> Session:
        return Session(self.engine)

database = None

def init_database(db_path: Path):
    global database
    database = DataBase(db_path)

def get_session() -> Session:
    return database.get_session()