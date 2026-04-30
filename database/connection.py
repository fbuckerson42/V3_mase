import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from typing import Optional
from config.settings import settings


class DatabaseConnection:
    def __init__(self):
        self.connection: Optional[psycopg2.extensions.connection] = None
        self.cursor: Optional[psycopg2.extensions.cursor] = None
    
    def connect(self) -> None:
        try:
            self.connection = psycopg2.connect(
                settings.DATABASE_URL,
                cursor_factory=RealDictCursor
            )
            self.cursor = self.connection.cursor()
        except psycopg2.Error as e:
            raise
    
    def disconnect(self) -> None:
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
    
    def commit(self) -> None:
        if self.connection:
            self.connection.commit()
    
    def rollback(self) -> None:
        if self.connection:
            self.connection.rollback()
    
    def execute(self, query: str, params: tuple = None) -> None:
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
        except psycopg2.Error as e:
            raise
    
    def execute_batch(self, query: str, params_list: list) -> int:
        try:
            return execute_values(self.cursor, query, params_list, template=None, page_size=1000)
        except psycopg2.Error as e:
            raise
    
    def fetchone(self, query: str, params: tuple = None) -> Optional[dict]:
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            return self.cursor.fetchone()
        except psycopg2.Error as e:
            raise
    
    def fetchall(self, query: str, params: tuple = None) -> list:
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            return self.cursor.fetchall()
        except psycopg2.Error as e:
            raise
    
    def run_migration(self, migration_file: str) -> None:
        try:
            with open(migration_file, 'r', encoding='utf-8') as f:
                sql = f.read()
            self.cursor.execute(sql)
            self.commit()
        except Exception as e:
            self.rollback()
            raise
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.disconnect()


_db_instance: Optional[DatabaseConnection] = None


def get_db() -> DatabaseConnection:
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseConnection()
    return _db_instance