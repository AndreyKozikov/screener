/**
 * Global application settings interface.
 * All configurable API parameters exposed to the user.
 */
export interface AppSettings {
  // ── LLM Analysis (Bonds Screener → AI Analysis) ──────────────────────────
  /** OpenAI GPT model identifier used for LLM bond analysis */
  llmGptModel: string;
  /** Qwen model identifier used for Qwen bond analysis (via OpenRouter) */
  llmQwenModel: string;
  /** Grok model identifier used for Grok bond analysis (via OpenRouter) */
  llmGrokModel: string;

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
  llmGptModel: 'gpt-5.1',
  llmQwenModel: 'qwen/qwen3-235b-a22b:free',
  llmGrokModel: 'x-ai/grok-4.1-fast:free',
  bondChatModel: 'gemini-3-flash-preview',
  bondChatEmbeddingModel: 'local',
  floatersProvider: 'gemini',
  floatPipelineProvider: 'gemini-3-flash',
  floatPipelineEmbeddingModel: 'local',
};
