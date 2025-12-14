import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  Alert,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';

interface FeedbackDialogProps {
  open: boolean;
  onClose: () => void;
  onSend: (text: string, tabName: string) => Promise<void>;
  tabName: string;
}

/**
 * FeedbackDialog Component
 * 
 * Modal dialog for submitting feedback/suggestions for improvements
 */
export const FeedbackDialog: React.FC<FeedbackDialogProps> = ({
  open,
  onClose,
  onSend,
  tabName,
}) => {
  const [feedbackText, setFeedbackText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const MAX_LENGTH = 3000;
  const remainingChars = MAX_LENGTH - feedbackText.length;

  const handleClose = () => {
    if (!isSubmitting) {
      setFeedbackText('');
      setError(null);
      setSuccess(false);
      onClose();
    }
  };

  const handleSend = async () => {
    if (!feedbackText.trim()) {
      setError('Пожалуйста, введите текст предложения');
      return;
    }

    if (feedbackText.length > MAX_LENGTH) {
      setError(`Текст не должен превышать ${MAX_LENGTH} символов`);
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setSuccess(false);

    try {
      await onSend(feedbackText.trim(), tabName);
      setSuccess(true);
      // Закрываем окно через небольшую задержку после успешной отправки
      setTimeout(() => {
        setFeedbackText('');
        setSuccess(false);
        onClose();
      }, 1500);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Не удалось отправить предложение';
      setError(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      aria-labelledby="feedback-dialog-title"
    >
      <DialogTitle id="feedback-dialog-title">
        Предложение по улучшению
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Поделитесь своими идеями и предложениями по улучшению приложения. 
          Ваше мнение очень важно для нас!
        </Typography>

        {success && (
          <Alert severity="success" sx={{ mb: 2 }}>
            Предложение успешно отправлено. Спасибо!
          </Alert>
        )}

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <TextField
          autoFocus
          multiline
          rows={10}
          fullWidth
          value={feedbackText}
          onChange={(e) => {
            const newValue = e.target.value;
            if (newValue.length <= MAX_LENGTH) {
              setFeedbackText(newValue);
              setError(null);
            }
          }}
          placeholder="Введите ваше предложение по улучшению приложения..."
          variant="outlined"
          disabled={isSubmitting || success}
          helperText={`Осталось символов: ${remainingChars} из ${MAX_LENGTH}`}
          error={remainingChars < 0}
          sx={{ mt: 1 }}
        />
      </DialogContent>
      <DialogActions>
        <Button
          onClick={handleClose}
          disabled={isSubmitting}
        >
          Закрыть
        </Button>
        <Button
          onClick={handleSend}
          variant="contained"
          startIcon={<SendIcon />}
          disabled={!feedbackText.trim() || isSubmitting || success || feedbackText.length > MAX_LENGTH}
        >
          {isSubmitting ? 'Отправка...' : 'Отправить'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
