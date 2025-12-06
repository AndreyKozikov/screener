import React, { useState, useEffect } from 'react';
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
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';

export interface RefreshTask {
  id: string;
  label: string;
  checked: boolean;
}

interface RefreshDataDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (selectedTasks: string[]) => Promise<void>;
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

  // Reset selected tasks when dialog opens or tasks change
  useEffect(() => {
    if (open) {
      const initial: Record<string, boolean> = {};
      tasks.forEach(task => {
        initial[task.id] = task.checked;
      });
      setSelectedTasks(initial);
    }
  }, [open, tasks]);

  const handleTaskToggle = (taskId: string) => {
    setSelectedTasks(prev => ({
      ...prev,
      [taskId]: !prev[taskId],
    }));
  };

  const handleConfirm = async () => {
    const selected = tasks
      .filter(task => selectedTasks[task.id])
      .map(task => task.id);
    
    if (selected.length === 0) {
      return;
    }

    await onConfirm(selected);
  };

  const handleClose = () => {
    if (!isRefreshing) {
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
                {isTaskLoading && (
                  <Box sx={{ mt: 1, ml: 4 }}>
                    <LinearProgress size="small" />
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
