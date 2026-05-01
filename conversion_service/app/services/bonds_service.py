import sqlite3
from pathlib import Path
from typing import List, Optional

from config.paths import DB_PATH

def get_emitent_inn_by_secid(secid: str, db_path: Optional[Path] = None) -> Optional[str]:
    path = db_path or DB_PATH
    if not path.exists():
        return None
    
    query = """
        SELECT e.inn
        FROM bonds b
        JOIN emitents e ON b.emitent_id = e.id
        WHERE b.secid = ?
    """
    try:
        with sqlite3.connect(path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (secid,))
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception:
        return None

def get_reg_number_by_secid(secid: str, db_path: Optional[Path] = None) -> Optional[str]:
    path = db_path or DB_PATH
    if not path.exists():
        return None
        
    query = """
        SELECT bs.reg_number
        FROM bonds b
        JOIN bondsecurity bs ON bs.bond_id = b.id
        WHERE b.secid = ? 
            AND bs.reg_number IS NOT NULL AND trim(bs.reg_number) != ''
            AND (b.boardid IS NULL OR UPPER(TRIM(b.boardid)) != 'PACT')
    """
    try:
        with sqlite3.connect(path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (secid,))
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception:
        return None

def get_floater_secids(db_path: Optional[Path] = None, rating: Optional[str] = None) -> List[str]:
    path = db_path or DB_PATH
    if not path.exists():
        return []
        
    query = """
        SELECT secid 
        FROM bonds 
        WHERE bond_kind = 8 
          AND bond_type IS NOT NULL 
          AND bond_type NOT IN (2, 4, 5)
          AND (boardid IS NULL OR UPPER(TRIM(boardid)) != 'PACT')
    """
    params = []
    
    if rating and rating.strip():
        query += " AND UPPER(TRIM(rating)) = ?"
        params.append(rating.strip().upper())
        
    try:
        with sqlite3.connect(path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [row[0] for row in rows]
    except Exception:
        return []
