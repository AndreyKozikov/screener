import { apiClient } from './client';

export interface FeedbackRequest {
  text: string;
  tab_name: string;
}

export interface FeedbackResponse {
  success: boolean;
  feedback_id: number;
  message?: string;
}

/**
 * Submit feedback/suggestion for improvements
 */
export const submitFeedback = async (
  text: string,
  tabName: string
): Promise<FeedbackResponse> => {
  const response = await apiClient.post<FeedbackResponse>('/feedback', {
    text,
    tab_name: tabName,
  });
  return response.data;
};
