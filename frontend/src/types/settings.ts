/**
 * Global application settings interface.
 * All configurable API parameters exposed to the user.
 */
export interface AppSettings {
  // ── Bond Chat / Vector Retrieval ──────────────────────────────────────────
  /** Language model used in the bond Q&A chat (vector retrieval) */
  bondChatModel: string;
  /** Embedding model used in the bond Q&A chat (vector retrieval) */
  bondChatEmbeddingModel: string;

  // ── Data Refresh → Floaters (eDisclosure) ─────────────────────────────────
  /** AI provider used when refreshing floater bond parameters via eDisclosure */
  floatersProvider: string;

  // ── LLM Pipeline (Float Params) ───────────────────────────────────────────
  /** LLM provider used for the float-params pipeline (per-bond update) */
  floatPipelineProvider: string;
  /** Embedding model used for the float-params pipeline */
  floatPipelineEmbeddingModel: string;
}

/** Default values — match current hardcoded defaults in the codebase */
export const DEFAULT_SETTINGS: AppSettings = {
  bondChatModel: 'gemini-3-flash-preview',
  bondChatEmbeddingModel: 'local',
  floatersProvider: 'gemini',
  floatPipelineProvider: 'gemini-3-flash',
  floatPipelineEmbeddingModel: 'local',
};



