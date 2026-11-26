import pyarrow as pa


def schemas(dim: int) -> dict[str, pa.Schema]:
    string = pa.string()
    integer = pa.int32()
    boolean = pa.bool_()

    def fields(names):
        return [(name, string) for name in names.split()]

    return {
        "bond_event_map": pa.schema(fields(
            "bond_secid bond_isin bond_reg_number bond_series bond_first_tradedate "
            "event_key write_id bond_event_write_key bond_event_key chunk_id chunk_write_key "
            "event_date match_reason"
        ) + [("event_year", integer), ("source_index", integer), ("is_corrected_by_another_event", boolean), ("issuename", string)]),
        "event_chunks": pa.schema(fields(
            "chunk_id event_key write_id event_write_key pseudo_guid text source_type source_id "
            "event_name event_date text_pipeline_version created_at"
        ) + [("event_year", integer), ("is_corrected_by_another_event", boolean)]),
        "event_vectors": pa.schema(fields(
            "sentence_id chunk_id write_id chunk_write_key event_key sentence_text created_at"
        ) + [("sentence_index", integer), ("vector", pa.list_(pa.float32(), dim)),
             ("terms", pa.list_(string)), ("weights", pa.list_(pa.float32()))]),
        "event_state": pa.schema(fields("event_key active_write_id status committed_at")
                                 + [("commit_seq", pa.int64())]),
        "bond_index_state": pa.schema(fields("bond_secid indexed_at")),
        "index_meta": pa.schema(fields(
            "model_id sparse_source sentence_splitter_version text_pipeline_version series_source "
            "series_extractor_version commit_protocol_version schema_version built_at fingerprint"
        ) + [("embedding_dim", integer), ("alpha", pa.float64()), ("supports_sparse", boolean),
             ("catalog_epoch", pa.int64())]),
    }


INDEXES = {
    "bond_event_map": "bond_secid bond_isin bond_reg_number bond_series event_year event_date chunk_id event_key bond_event_key bond_event_write_key chunk_write_key".split(),
    "event_chunks": ["event_key", "event_write_key"],
    "event_vectors": ["chunk_id", "chunk_write_key"],
    "event_state": ["event_key", "status"],
    "bond_index_state": ["bond_secid"],
}
