import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

def get_all_bond_secids(db_path: Optional[Path] = None, rating: Optional[str] = None) -> List[str]:
    """Returns SECIDs for all bonds that have a registration number."""
    path = db_path or DB_PATH
    if not path.exists():
        return []
        
    query = """
        SELECT b.secid 
        FROM bonds b
        JOIN bondsecurity bs ON bs.bond_id = b.id
        WHERE bs.reg_number IS NOT NULL AND trim(bs.reg_number) != ''
          AND (b.boardid IS NULL OR UPPER(TRIM(b.boardid)) != 'PACT')
    """
    params = []
    
    if rating and rating.strip():
        query += " AND UPPER(TRIM(b.rating)) = ?"
        params.append(rating.strip().upper())
        
    try:
        with sqlite3.connect(path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [row[0] for row in rows]
    except Exception:
        return []


def get_all_bonds_metadata(
    db_path: Optional[Path] = None, rating: Optional[str] = None
) -> Dict[str, Tuple[str, str]]:
    """Returns a dict mapping secid to (inn, reg_number) for all bonds with registration numbers."""
    path = db_path or DB_PATH
    if not path.exists():
        return {}

    query = """
        SELECT b.secid, trim(e.inn), trim(bs.reg_number)
        FROM bonds b
        JOIN bondsecurity bs ON bs.bond_id = b.id
        JOIN emitents e ON b.emitent_id = e.id
        WHERE bs.reg_number IS NOT NULL AND trim(bs.reg_number) != ''
          AND (b.boardid IS NULL OR UPPER(TRIM(b.boardid)) != 'PACT')
    """
    params = []

    if rating and rating.strip():
        query += " AND UPPER(TRIM(b.rating)) = ?"
        params.append(rating.strip().upper())

    try:
        with sqlite3.connect(path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return {
                str(row[0]).strip(): (str(row[1]).strip(), str(row[2]).strip())
                for row in rows
                if row[0] and row[1] and row[2]
            }
    except Exception:
        return {}

