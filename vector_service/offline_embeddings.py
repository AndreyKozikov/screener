from pathlib import Path
from threading import Lock

from .algorithms.embedding_service import EmbeddingService


class LocalBGE(EmbeddingService):
    """Вычисляет те же гибридные векторы BGE-M3 непосредственно в процессе."""

    def __init__(self, model_dir: Path):
        directory = model_dir.resolve(strict=True)
        for filename in ("config.json", "sparse_linear.pt", "colbert_linear.pt"):
            if not (directory / filename).is_file():
                raise ValueError(f"Неполный комплект весов BGE-M3: отсутствует {filename} в {directory}")
        import torch
        from FlagEmbedding import BGEM3FlagModel

        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.inference_lock = Lock()
        self.model = BGEM3FlagModel(str(directory), devices=[device], use_fp16=device == "cuda")

    def _call_embedding_service(self, sentences):
        with self.inference_lock:
            result = self.model.encode(sentences, return_dense=True, return_sparse=True, return_colbert_vecs=False)
        return {
            "dense_embeddings": result["dense_vecs"].astype("float32").tolist(),
            "lexical_weights": [{str(k): float(v) for k, v in weights.items()}
                                for weights in result["lexical_weights"]],
        }
