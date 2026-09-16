import React, { useState, useEffect, useRef } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormGroup,
  FormControlLabel,
  Checkbox,
  Box,
  Typography,
  LinearProgress,
  Alert,
  Select,
  MenuItem,
  Chip,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import UploadFileIcon from '@mui/icons-material/UploadFile';

export interface RefreshTask {
  id: string;
  label: string;
  checked: boolean;
}

interface RefreshDataDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (
    selectedTasks: string[],
    forceUpdateRatings?: boolean,
    forceRefreshCoupons?: boolean,
    floatersProvider?: string,
    ipcFile?: File | null,
    inflationExpectationsFile?: File | null,
  ) => Promise<void>;
  tasks: RefreshTask[];
  isRefreshing: boolean;
  refreshStatus: Record<string, { status: 'idle' | 'loading' | 'success' | 'error'; error?: string }>;
}

/**
 * RefreshDataDialog Component
 * 
 * Modal dialog for selecting which data refresh tasks to execute
 */
export const RefreshDataDialog: React.FC<RefreshDataDialogProps> = ({
  open,
  onClose,
  onConfirm,
  tasks,
  isRefreshing,
  refreshStatus,
}) => {
  const [selectedTasks, setSelectedTasks] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    tasks.forEach(task => {
      initial[task.id] = task.checked;
    });
    return initial;
  });
  const [forceUpdateRatings, setForceUpdateRatings] = useState(false);
  const [forceRefreshCoupons, setForceRefreshCoupons] = useState(false);
  const [floatersProvider, setFloatersProvider] = useState<string>('gemini');
  const [ipcFile, setIpcFile] = useState<File | null>(null);
  const [ipcFileError, setIpcFileError] = useState<string | null>(null);
  const ipcFileInputRef = useRef<HTMLInputElement>(null);
  const [inflationExpectationsFile, setInflationExpectationsFile] = useState<File | null>(null);
  const [inflationExpectationsFileError, setInflationExpectationsFileError] = useState<string | null>(null);
  const inflationExpectationsFileInputRef = useRef<HTMLInputElement>(null);

  // Reset selected tasks when dialog opens or tasks change
  useEffect(() => {
    if (open) {
      const initial: Record<string, boolean> = {};
      tasks.forEach(task => {
        initial[task.id] = task.checked;
      });
      setSelectedTasks(initial);
      setForceUpdateRatings(false);
      setForceRefreshCoupons(false);
      setFloatersProvider('gemini');
      setIpcFile(null);
      setIpcFileError(null);
      if (ipcFileInputRef.current) {
        ipcFileInputRef.current.value = '';
      }
      setInflationExpectationsFile(null);
      setInflationExpectationsFileError(null);
      if (inflationExpectationsFileInputRef.current) {
        inflationExpectationsFileInputRef.current.value = '';
      }
    }
  }, [open, tasks]);

  const handleTaskToggle = (taskId: string) => {
    setSelectedTasks(prev => ({
      ...prev,
      [taskId]: !prev[taskId],
    }));
  };

  const handleIpcFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    setIpcFileError(null);
    if (!file) {
      setIpcFile(null);
      return;
    }
    const name = file.name.toLowerCase();
    if (!name.endsWith('.xlsx')) {
      setIpcFileError('Допустим только формат .xlsx');
      setIpcFile(null);
      return;
    }
    setIpcFile(file);
  };

  const handleInflationExpectationsFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    setInflationExpectationsFileError(null);
    if (!file) {
      setInflationExpectationsFile(null);
      return;
    }
    const name = file.name.toLowerCase();
    if (!name.endsWith('.xlsx')) {
      setInflationExpectationsFileError('Допустим только формат .xlsx');
      setInflationExpectationsFile(null);
      return;
    }
    setInflationExpectationsFile(file);
  };

  const handleConfirm = async () => {
    const selected = tasks
      .filter(task => selectedTasks[task.id])
      .map(task => task.id);
    
    if (selected.length === 0) {
      return;
    }

    // Close dialog immediately without waiting for server response
    onClose();
    // Start refresh in background (fire and forget)
    void onConfirm(selected, forceUpdateRatings, forceRefreshCoupons, floatersProvider, ipcFile, inflationExpectationsFile);
  };

  const handleClose = () => {
    if (!isRefreshing) {
      setIpcFile(null);
      setIpcFileError(null);
      if (ipcFileInputRef.current) {
        ipcFileInputRef.current.value = '';
      }
      setInflationExpectationsFile(null);
      setInflationExpectationsFileError(null);
      if (inflationExpectationsFileInputRef.current) {
        inflationExpectationsFileInputRef.current.value = '';
      }
      onClose();
    }
  };

  const selectedCount = tasks.filter(task => selectedTasks[task.id]).length;
  const hasSelection = selectedCount > 0;

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      aria-labelledby="refresh-data-dialog-title"
      PaperProps={{
        sx: {
          borderRadius: '20px',
          border: '1px solid #E2E8F0',
        },
      }}
    >
      <DialogTitle id="refresh-data-dialog-title">
        Обновить данные
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Выберите задачи для обновления. Выбранные задачи будут выполнены параллельно.
        </Typography>
        
        <FormGroup>
          {tasks.map((task) => {
            const taskStatus = refreshStatus[task.id] || { status: 'idle' as const };
            const isTaskLoading = taskStatus.status === 'loading';
            const isTaskSuccess = taskStatus.status === 'success';
            const isTaskError = taskStatus.status === 'error';
            const isRatingsTask = task.id === 'ratings';
            const isCouponsTask = task.id === 'coupons';
            const isFloatersTask = task.id === 'floaters';
            const isIpcTask = task.id === 'ipc';
            const isInflationExpectationsTask = task.id === 'inflation-expectations';
            
            return (
              <Box key={task.id} sx={{ mb: 2 }}>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={selectedTasks[task.id]}
                      onChange={() => handleTaskToggle(task.id)}
                      disabled={isRefreshing}
                    />
                  }
                  label={task.label}
                />
                {isRatingsTask && selectedTasks[task.id] && (
                  <Box sx={{ ml: 4, mt: 1 }}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={forceUpdateRatings}
                          onChange={(e) => setForceUpdateRatings(e.target.checked)}
                          disabled={isRefreshing}
                          size="small"
                        />
                      }
                      label={
                        <Typography variant="body2" color="text.secondary">
                          Принудительно обновить все рейтинги (игнорировать дату последнего обновления)
                        </Typography>
                      }
                    />
                  </Box>
                )}
                {isCouponsTask && selectedTasks[task.id] && (
                  <Box sx={{ ml: 4, mt: 1 }}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={forceRefreshCoupons}
                          onChange={(e) => setForceRefreshCoupons(e.target.checked)}
                          disabled={isRefreshing}
                          size="small"
                        />
                      }
                      label={
                        <Typography variant="body2" color="text.secondary">
                          Принудительно обновить купоны (игнорировать кэш, обновить все данные с MOEX API)
                        </Typography>
                      }
                    />
                  </Box>
                )}
                {isFloatersTask && selectedTasks[task.id] && (
                  <Box sx={{ ml: 4, mt: 1 }}>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                      Выберите AI провайдер:
                    </Typography>
                    <Select
                      size="small"
                      value={floatersProvider}
                      onChange={(e) => setFloatersProvider(e.target.value)}
                      disabled={isRefreshing}
                      sx={{ minWidth: 240 }}
                    >
                      <MenuItem value="gemini">Google Gemini 2.5 Flash Lite</MenuItem>
                      <MenuItem value="gemini-flash">Google Gemini 2.5 Flash</MenuItem>
                      <MenuItem value="gemini-2.5-pro">Google Gemini 2.5 Pro</MenuItem>
                      <MenuItem value="gemini-2-flash">Google Gemini 2 Flash</MenuItem>
                      <MenuItem value="gemini-3-flash">Google Gemini 3 Flash</MenuItem>
                      <MenuItem value="gemini-3.1-pro">Google Gemini 3.1 Pro</MenuItem>
                      <MenuItem value="openai-gpt-5.1">OpenAI GPT-5.1</MenuItem>
                      <MenuItem value="openrouter">OpenRouter: Gemini 2.5 Flash Lite</MenuItem>
                      <MenuItem value="local">Локальная модель (Qwen3-4B)</MenuItem>
                    </Select>
                  </Box>
                )}
                {isIpcTask && selectedTasks[task.id] && (
                  <Box
                    sx={{
                      ml: 4,
                      mt: 1,
                      p: 1.5,
                      bgcolor: '#F8FAFC',
                      borderRadius: '12px',
                      border: '1px dashed #CBD5E1',
                    }}
                  >
                    <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5, color: '#334155' }}>
                      Файл данных Росстата (.xlsx):
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                      Выберите файл с индексами ИПЦ или оставьте поле пустым для использования файла по умолчанию на сервере.
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
                      <input
                        ref={ipcFileInputRef}
                        type="file"
                        accept=".xlsx"
                        onChange={handleIpcFileChange}
                        style={{ display: 'none' }}
                        id="ipc-excel-upload-input"
                        disabled={isRefreshing}
                      />
                      <label htmlFor="ipc-excel-upload-input">
                        <Button
                          variant="outlined"
                          component="span"
                          size="small"
                          startIcon={<UploadFileIcon />}
                          disabled={isRefreshing}
                          sx={{ borderRadius: '8px', textTransform: 'none' }}
                        >
                          {ipcFile ? 'Заменить файл' : 'Выбрать Excel файл'}
                        </Button>
                      </label>
                      {ipcFile ? (
                        <Chip
                          label={ipcFile.name}
                          size="small"
                          onDelete={() => {
                            setIpcFile(null);
                            if (ipcFileInputRef.current) {
                              ipcFileInputRef.current.value = '';
                            }
                          }}
                          disabled={isRefreshing}
                          color="primary"
                          variant="outlined"
                        />
                      ) : (
                        <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                          (файл не выбран — парсинг серверного файла по умолчанию)
                        </Typography>
                      )}
                    </Box>
                    {ipcFileError && (
                      <Typography variant="caption" color="error" sx={{ display: 'block', mt: 0.5 }}>
                        {ipcFileError}
                      </Typography>
                    )}
                  </Box>
                )}
                {isInflationExpectationsTask && selectedTasks[task.id] && (
                  <Box
                    sx={{
                      ml: 4,
                      mt: 1,
                      p: 1.5,
                      bgcolor: '#F8FAFC',
                      borderRadius: '12px',
                      border: '1px dashed #CBD5E1',
                    }}
                  >
                    <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5, color: '#334155' }}>
                      Файл данных инфляционных ожиданий (.xlsx):
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                      Выберите Excel-файл с данными инфляционных ожиданий для отправки на сервер.
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
                      <input
                        ref={inflationExpectationsFileInputRef}
                        type="file"
                        accept=".xlsx"
                        onChange={handleInflationExpectationsFileChange}
                        style={{ display: 'none' }}
                        id="inflation-expectations-excel-upload-input"
                        disabled={isRefreshing}
                      />
                      <label htmlFor="inflation-expectations-excel-upload-input">
                        <Button
                          variant="outlined"
                          component="span"
                          size="small"
                          startIcon={<UploadFileIcon />}
                          disabled={isRefreshing}
                          sx={{ borderRadius: '8px', textTransform: 'none' }}
                        >
                          {inflationExpectationsFile ? 'Заменить файл' : 'Выбрать Excel файл'}
                        </Button>
                      </label>
                      {inflationExpectationsFile ? (
                        <Chip
                          label={inflationExpectationsFile.name}
                          size="small"
                          onDelete={() => {
                            setInflationExpectationsFile(null);
                            if (inflationExpectationsFileInputRef.current) {
                              inflationExpectationsFileInputRef.current.value = '';
                            }
                          }}
                          disabled={isRefreshing}
                          color="primary"
                          variant="outlined"
                        />
                      ) : (
                        <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                          (файл не выбран)
                        </Typography>
                      )}
                    </Box>
                    {inflationExpectationsFileError && (
                      <Typography variant="caption" color="error" sx={{ display: 'block', mt: 0.5 }}>
                        {inflationExpectationsFileError}
                      </Typography>
                    )}
                  </Box>
                )}
                {isTaskLoading && (
                  <Box sx={{ mt: 1, ml: 4 }}>
                    <LinearProgress />
                  </Box>
                )}
                {isTaskSuccess && (
                  <Alert severity="success" sx={{ mt: 1, ml: 4 }}>
                    Успешно обновлено
                  </Alert>
                )}
                {isTaskError && (
                  <Alert severity="error" sx={{ mt: 1, ml: 4 }}>
                    {taskStatus.error || 'Ошибка при обновлении'}
                  </Alert>
                )}
              </Box>
            );
          })}
        </FormGroup>

        {!hasSelection && !isRefreshing && (
          <Alert severity="info" sx={{ mt: 2 }}>
            Выберите хотя бы одну задачу для обновления
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button
          onClick={handleClose}
          disabled={isRefreshing}
        >
          {isRefreshing ? 'Закрыть (после завершения)' : 'Отмена'}
        </Button>
        <Button
          onClick={handleConfirm}
          variant="contained"
          startIcon={isRefreshing ? <RefreshIcon /> : undefined}
          disabled={!hasSelection || isRefreshing}
        >
          {isRefreshing ? 'Обновление...' : 'Обновить'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
