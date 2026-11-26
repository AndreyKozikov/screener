import ast
import unittest
from pathlib import Path


class AlgorithmParityTests(unittest.TestCase):
    def test_legacy_definitions(self):
        root = Path(__file__).resolve().parents[2]
        legacy = root / "backend/app/services/vector_retrieval"
        service = root / "vector_service/algorithms"
        definitions = {
            "models": ["Chunk", "EmbeddedChunk", "ScoredChunk"],
            "chunking_service": ["chunk_events"],
            "retrieval_engine": ["RetrievalEngine"],
            "context_builder": ["ContextBuilder"],
        }
        for module, names in definitions.items():
            for name in names:
                with self.subTest(module=module, name=name):
                    expected, actual = (
                        self.definition(directory / f"{module}.py", name)
                        for directory in (legacy, service)
                    )
                    self.assertEqual(expected, actual)

    @staticmethod
    def definition(path, name):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        node, = [
            item for item in ast.walk(tree)
            if isinstance(item, (ast.ClassDef, ast.FunctionDef)) and item.name == name
        ]
        return ast.dump(node)
