from contextlib import contextmanager

import pymysql
from dbutils.pooled_db import PooledDB

from app.config.settings import settings


class DatabasePool:
    """MySQL connection pool helpers."""

    _pool = None

    @classmethod
    def get_pool(cls):
        if cls._pool is None:
            cls._pool = PooledDB(
                creator=pymysql,
                maxconnections=settings.MYSQL_MAX_CONNECTIONS,
                host=settings.MYSQL_HOST,
                user=settings.MYSQL_USER,
                password=settings.MYSQL_PASSWORD,
                port=settings.MYSQL_PORT,
                database=settings.MYSQL_DATABASE,
                charset=settings.MYSQL_CHARSET,
                connect_timeout=settings.MYSQL_CONNECT_TIMEOUT,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
                blocking=True,
            )
        return cls._pool

    @classmethod
    def get_connection(cls):
        return cls.get_pool().connection()

    @classmethod
    @contextmanager
    def connection(cls):
        connection = cls.get_connection()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @classmethod
    @contextmanager
    def cursor(cls):
        with cls.connection() as connection:
            with connection.cursor() as cursor:
                yield cursor


pool = DatabasePool.get_pool()
