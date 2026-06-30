from typing import Optional

from app.services.vector_retrieval.pipeline import RetrievalPipeline

retrieval_pipeline: Optional[RetrievalPipeline] = None

def init_retrieval_pipeline() -> None:
    global retrieval_pipeline
    retrieval_pipeline = RetrievalPipeline()

def get_retrieval_pipeline() -> RetrievalPipeline:
    global retrieval_pipeline

    if retrieval_pipeline is None:
        retrieval_pipeline = RetrievalPipeline()

    return retrieval_pipeline