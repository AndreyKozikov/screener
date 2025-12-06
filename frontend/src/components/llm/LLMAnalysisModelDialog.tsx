import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  RadioGroup,
  FormControlLabel,
  Radio,
  Typography,
  Box,
} from '@mui/material';
import PsychologyIcon from '@mui/icons-material/Psychology';

export type LLMModel = 'llm' | 'qwen' | 'grok';

interface LLMAnalysisModelDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (model: LLMModel) => void;
}

/**
 * LLMAnalysisModelDialog Component
 * 
 * Modal dialog for selecting which LLM model to use for analysis
 */
export const LLMAnalysisModelDialog: React.FC<LLMAnalysisModelDialogProps> = ({
  open,
  onClose,
  onConfirm,
}) => {
  const [selectedModel, setSelectedModel] = useState<LLMModel>('llm');

  // Reset selection when dialog opens
  useEffect(() => {
    if (open) {
      setSelectedModel('llm');
    }
  }, [open]);

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSelectedModel(event.target.value as LLMModel);
  };

  const handleConfirm = () => {
    onConfirm(selectedModel);
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      aria-labelledby="llm-analysis-model-dialog-title"
    >
      <DialogTitle id="llm-analysis-model-dialog-title">
        Выберите модель для анализа
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Выберите одну из доступных моделей для анализа выбранных облигаций.
        </Typography>
        
        <RadioGroup
          aria-labelledby="llm-analysis-model-dialog-title"
          name="llm-model-radio-group"
          value={selectedModel}
          onChange={handleChange}
        >
          <Box sx={{ mb: 1 }}>
            <FormControlLabel
              value="llm"
              control={<Radio />}
              label={
                <Box>
                  <Typography variant="body1" fontWeight={500}>
                    Отправить на анализ LLM
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    GPT-5.1 модель
                  </Typography>
                </Box>
              }
            />
          </Box>
          <Box sx={{ mb: 1 }}>
            <FormControlLabel
              value="qwen"
              control={<Radio />}
              label={
                <Box>
                  <Typography variant="body1" fontWeight={500}>
                    Отправить Qwen 3
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Qwen 3-235B модель
                  </Typography>
                </Box>
              }
            />
          </Box>
          <Box sx={{ mb: 1 }}>
            <FormControlLabel
              value="grok"
              control={<Radio />}
              label={
                <Box>
                  <Typography variant="body1" fontWeight={500}>
                    Отправить Grok 4.1 Fast
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Grok 4.1 Fast модель
                  </Typography>
                </Box>
              }
            />
          </Box>
        </RadioGroup>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>
          Отмена
        </Button>
        <Button
          onClick={handleConfirm}
          variant="contained"
          startIcon={<PsychologyIcon />}
        >
          Продолжить
        </Button>
      </DialogActions>
    </Dialog>
  );
};
