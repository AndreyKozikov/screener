import { apiClient } from './client';

/**
 * Run LLM prompt pipeline for a specific bond to update its float parameters
 */
export const runLlmPromptPipeline = async (
  secid: string,
  useLocalEvents: boolean = true,
  provider: string = 'gemini-3-flash',
  embeddingModel: string = 'local'
): Promise<any> => {
  const response = await apiClient.post(
    '/float-bonds-llm-analize/run',
    {
      secid,
      use_local_events: useLocalEvents,
      provider: provider,
      embedding_model: embeddingModel,
    },
    {
      timeout: 300000, // 5 minutes
    }
  );
  return response.data;
};



