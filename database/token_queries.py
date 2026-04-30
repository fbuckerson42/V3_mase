from typing import Optional, Dict, Any
from datetime import datetime
from database.connection import DatabaseConnection


class TokenQueries:
    
    def __init__(self, db: DatabaseConnection):
        self.db = db
    
    def get_token(self, token_type: str = 'bearer_token') -> Optional[str]:
        query = """
            SELECT token_value FROM tokens 
            WHERE token_type = %s AND is_active = TRUE
            ORDER BY updated_at DESC
            LIMIT 1
        """
        result = self.db.fetchone(query, (token_type,))
        return result['token_value'] if result else None
    
    def save_token(self, token_value: str, token_type: str = 'bearer_token', expires_at: Optional[datetime] = None) -> None:
        query = """
            INSERT INTO tokens (token_type, token_value, expires_at, created_at, updated_at, is_active)
            VALUES (%s, %s, %s, NOW(), NOW(), TRUE)
            ON CONFLICT (token_type) 
            DO UPDATE SET 
                token_value = EXCLUDED.token_value,
                updated_at = NOW(),
                expires_at = EXCLUDED.expires_at,
                is_active = TRUE
        """
        
        try:
            self.db.execute(query, (token_type, token_value, expires_at))
        except Exception as e:
            raise
    
    def deactivate_token(self, token_type: str = 'bearer_token') -> None:
        query = "UPDATE tokens SET is_active = FALSE, updated_at = NOW() WHERE token_type = %s"
        self.db.execute(query, (token_type,))
    
    def delete_token(self, token_type: str = 'bearer_token') -> None:
        query = "DELETE FROM tokens WHERE token_type = %s"
        self.db.execute(query, (token_type,))
    
    def get_all_tokens(self) -> list:
        query = """
            SELECT token_type, created_at, updated_at, expires_at, is_active 
            FROM tokens 
            ORDER BY updated_at DESC
        """
        return self.db.fetchall(query)
    
    def token_exists(self, token_type: str = 'bearer_token') -> bool:
        query = "SELECT id FROM tokens WHERE token_type = %s AND is_active = TRUE"
        result = self.db.fetchone(query, (token_type,))
        return result is not None