import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from db_repository.models.repository_rpc import RepositoryCall
from db_repository.repository.operations.bonds_repository import BondsRepository
from db_repository.services import repository_rpc_service as rpc


class VectorBondCatalogTests(unittest.TestCase):
    def test_rpc_includes_missing_regnumber_and_excludes_pact(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.db"
            with sqlite3.connect(path) as conn:
                conn.executescript("""
                    CREATE TABLE bonds(id INTEGER, secid TEXT, isin TEXT, secname TEXT, boardid TEXT);
                    CREATE TABLE bond_emitents(secid TEXT, emitent_id INTEGER);
                    CREATE TABLE emitents(id INTEGER, inn TEXT);
                    CREATE TABLE bondsecurity(bond_id INTEGER, reg_number TEXT);
                    INSERT INTO emitents VALUES (1, ' 123 '), (2, '456');
                    INSERT INTO bonds VALUES (1,'A','IA','А БО-1',NULL),
                        (2,'B','IB','Б',' pact '), (3,'C','IC','В','TQCB');
                    INSERT INTO bond_emitents VALUES ('A',1),('B',1),('C',2);
                """)
            conn.close()
            repository = BondsRepository(path)
            try:
                with patch.object(rpc, "_get_repository", return_value=repository):
                    payload = RepositoryCall(repository="bonds", method="get_bonds_by_emitent_inn", args=["123"])
                    self.assertEqual(rpc.call_repository(payload), [
                        dict(secid="A", isin="IA", secname="А БО-1", reg_number=None)
                    ])
            finally:
                repository._engine.dispose()
