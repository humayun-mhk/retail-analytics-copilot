"""SQLite database tool for Northwind queries."""

import sqlite3
from typing import Dict, List, Any, Optional
from pathlib import Path


class SQLiteTool:
    """Tool for interacting with the Northwind SQLite database."""
    
    def __init__(self, db_path: str = "data/northwind.sqlite"):
        self.db_path = db_path
        self._ensure_db_exists()
        self.schema = self._get_schema()
    
    def _ensure_db_exists(self):
        """Check if database exists."""
        if not Path(self.db_path).exists():
            raise FileNotFoundError(
                f"Database not found at {self.db_path}. "
                "Please download using the curl command from the assignment."
            )
    
    def _get_schema(self) -> str:
        """Get database schema using PRAGMA statements."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        schema_parts = []
        for table in tables:
            # Get columns for each table
            # Quote table name to handle spaces and special characters
            quoted_table = f'"{table}"' if ' ' in table or '-' in table else table
            try:
                cursor.execute(f"PRAGMA table_info({quoted_table});")
                columns = cursor.fetchall()
                
                if columns:  # Only add if we got column info
                    col_info = ", ".join([
                        f"{col[1]} ({col[2]})" for col in columns
                    ])
                    schema_parts.append(f"{table}: {col_info}")
            except:
                continue  # Skip problematic tables
        
        conn.close()
        return "\n".join(schema_parts)
    
    def execute_query(self, sql: str) -> Dict[str, Any]:
        """
        Execute SQL query and return results with metadata.
        
        Returns:
            Dict with keys: columns, rows, error
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Clean up SQL (remove markdown formatting if present)
            sql = sql.strip()
            if sql.startswith("```sql"):
                sql = sql.replace("```sql", "").replace("```", "").strip()
            elif sql.startswith("```"):
                sql = sql.replace("```", "").strip()
            
            cursor.execute(sql)
            
            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Get all rows
            rows = cursor.fetchall()
            
            conn.close()
            
            return {
                "columns": columns,
                "rows": rows,
                "error": None
            }
        
        except sqlite3.OperationalError as e:
            # Provide helpful error message
            error_msg = str(e)
            if "no such table" in error_msg.lower():
                return {
                    "columns": [],
                    "rows": [],
                    "error": f"Table not found. {error_msg}. Available tables: {', '.join(self._get_table_names())}"
                }
            return {
                "columns": [],
                "rows": [],
                "error": f"SQL syntax error: {error_msg}"
            }
        
        except Exception as e:
            return {
                "columns": [],
                "rows": [],
                "error": f"Query execution error: {str(e)}"
            }
    
    def _get_table_names(self) -> List[str]:
        """Get list of table names."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return tables
        except:
            return []
    
    def get_schema_summary(self) -> str:
        """Get a concise schema summary for prompts."""
        return self.schema
    
    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            conn.close()
            return True
        except Exception:
            return False