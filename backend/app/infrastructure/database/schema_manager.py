from app.infrastructure.database.database_pool import DatabasePool
from app.infrastructure.logging.logger import logger


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id VARCHAR(64) PRIMARY KEY,
        username VARCHAR(64) NOT NULL UNIQUE,
        display_name VARCHAR(64) NOT NULL,
        password_salt VARCHAR(64) NOT NULL,
        password_hash VARCHAR(128) NOT NULL,
        is_active TINYINT(1) NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS user_auth_tokens (
        token_id VARCHAR(36) PRIMARY KEY,
        user_id VARCHAR(64) NOT NULL,
        token_hash CHAR(64) NOT NULL UNIQUE,
        expires_at DATETIME NOT NULL,
        created_at DATETIME NOT NULL,
        last_used_at DATETIME NOT NULL,
        CONSTRAINT fk_user_auth_tokens_user
            FOREIGN KEY (user_id) REFERENCES users(user_id)
            ON DELETE CASCADE,
        INDEX idx_user_auth_tokens_user_id (user_id),
        INDEX idx_user_auth_tokens_expires_at (expires_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_sessions (
        session_id VARCHAR(128) PRIMARY KEY,
        user_id VARCHAR(64) NOT NULL,
        last_message_preview VARCHAR(255) NULL,
        total_messages INT NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        CONSTRAINT fk_chat_sessions_user
            FOREIGN KEY (user_id) REFERENCES users(user_id)
            ON DELETE CASCADE,
        INDEX idx_chat_sessions_user_updated (user_id, updated_at DESC)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
)


def ensure_database_schema() -> None:
    with DatabasePool.cursor() as cursor:
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
    logger.info("Database schema check completed")
