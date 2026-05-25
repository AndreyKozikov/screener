import React, { useState, useRef, useEffect } from 'react';
import {
  Box,
  Typography,
  TextField,
  IconButton,
  Paper,
  Stack,
  Avatar,
  CircularProgress,
  Drawer,
  Tooltip,
  Popover,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import {
  Send as SendIcon,
  Close as CloseIcon,
  SmartToy as BotIcon,
  Person as UserIcon,
  ContentCopy as CopyIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import { askBondQuestion } from '../../api/bonds';

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'bot';
  timestamp: Date;
}

interface BondChatProps {
  isOpen: boolean;
  onClose: () => void;
  secid: string;
  shortName: string;
}

export const BondChat: React.FC<BondChatProps> = ({ isOpen, onClose, secid, shortName }) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: `Привет! Я ваш помощник по облигации ${shortName}. Можете задать любой вопрос по её параметрам, условиям выпуска или купонам.`,
      sender: 'bot',
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [settingsAnchorEl, setSettingsAnchorEl] = useState<HTMLButtonElement | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>(() => {
    return localStorage.getItem('bond_chat_model') || 'gemini-3-flash-preview';
  });

  const handleSettingsClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setSettingsAnchorEl(event.currentTarget);
  };

  const handleSettingsClose = () => {
    setSettingsAnchorEl(null);
  };

  const handleModelChange = (event: any) => {
    const model = event.target.value as string;
    setSelectedModel(model);
    localStorage.setItem('bond_chat_model', model);
  };

  const isSettingsOpen = Boolean(settingsAnchorEl);
  const settingsId = isSettingsOpen ? 'bond-chat-settings-popover' : undefined;

  const AVAILABLE_MODELS = [
    { id: 'gemini-2.5-flash-lite', name: 'Gemini 2.5 Flash Lite' },
    { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash' },
    { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro' },
    { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash' },
    { id: 'gemini-3-flash-preview', name: 'Gemini 3 Flash Preview' },
    { id: 'gemini-3.1-pro-preview', name: 'Gemini 3.1 Pro Preview' },
    { id: 'openrouter/deepseek-v4-pro', name: 'DeepSeek v4 Pro (OpenRouter)' },
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: inputValue.trim(),
      sender: 'user',
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      const response = await askBondQuestion(secid, userMessage.text, selectedModel);
      
      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: response.answer,
        sender: 'bot',
        timestamp: new Date(),
      };
      
      setMessages((prev) => [...prev, botMessage]);
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: 'Извините, произошла ошибка при получении ответа. Попробуйте еще раз позже.',
        sender: 'bot',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCopyChat = () => {
    const chatContent = messages
      .map((msg) => {
        const sender = msg.sender === 'user' ? 'Вы' : 'ИИ';
        const time = msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        return `### ${sender} (${time})\n\n${msg.text}\n\n---`;
      })
      .join('\n\n');

    const header = `# Чат по облигации ${shortName} (${secid})\n\n`;
    const fullText = header + chatContent;

    navigator.clipboard.writeText(fullText).then(() => {
      // Можно добавить уведомление (Snackbar), если оно есть в проекте,
      // но в ТЗ только копирование.
    }).catch(err => {
      console.error('Ошибка при копировании: ', err);
    });
  };

  return (
    <Drawer
      anchor="right"
      open={isOpen}
      onClose={onClose}
      PaperProps={{
        sx: { width: { xs: '100%', sm: 450 }, display: 'flex', flexDirection: 'column' },
      }}
    >
      {/* Header */}
      <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', bgcolor: 'primary.main', color: 'white' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <BotIcon />
          <Box>
            <Typography variant="subtitle1" fontWeight={600}>Чат с ИИ: {shortName}</Typography>
            <Typography variant="caption" sx={{ opacity: 0.8 }}>Анализ документов и событий</Typography>
          </Box>
        </Box>
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="Настройки чата">
            <IconButton onClick={handleSettingsClick} size="small" sx={{ color: 'white' }}>
              <SettingsIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Скопировать весь чат (Markdown)">
            <IconButton onClick={handleCopyChat} size="small" sx={{ color: 'white' }}>
              <CopyIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <IconButton onClick={onClose} size="small" sx={{ color: 'white' }}>
            <CloseIcon />
          </IconButton>
        </Box>
      </Box>

      {/* Messages Area */}
      <Box sx={{ flexGrow: 1, p: 2, overflowY: 'auto', bgcolor: 'grey.50', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {messages.map((msg) => (
          <Box
            key={msg.id}
            sx={{
              display: 'flex',
              flexDirection: msg.sender === 'user' ? 'row-reverse' : 'row',
              alignItems: 'flex-start',
              gap: 1,
            }}
          >
            <Avatar
              sx={{
                width: 32,
                height: 32,
                bgcolor: msg.sender === 'user' ? 'primary.light' : 'secondary.main',
                fontSize: '0.8rem',
              }}
            >
              {msg.sender === 'user' ? <UserIcon fontSize="small" /> : <BotIcon fontSize="small" />}
            </Avatar>
            <Paper
              elevation={1}
              sx={{
                p: 1.5,
                maxWidth: '85%',
                borderRadius: 2,
                bgcolor: msg.sender === 'user' ? 'primary.main' : 'white',
                color: msg.sender === 'user' ? 'white' : 'text.primary',
                position: 'relative',
                '& p': { m: 0, mb: 0.5 },
                '& p:last-child': { mb: 0 },
                '& ul, & ol': { pl: 2, m: 0, mb: 1 },
                '& li': { mb: 0.5 },
                '& code': {
                  bgcolor: msg.sender === 'user' ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.05)',
                  px: 0.5,
                  borderRadius: 0.5,
                  fontFamily: 'monospace',
                },
                '& table': {
                  borderCollapse: 'collapse',
                  width: '100%',
                  mb: 1,
                  fontSize: '0.8rem',
                },
                '& th, & td': {
                  border: '1px solid',
                  borderColor: msg.sender === 'user' ? 'rgba(255,255,255,0.3)' : 'divider',
                  p: 0.5,
                }
              }}
            >
              <Box sx={{ 
                '& .katex-display': { my: 1, overflowX: 'auto', overflowY: 'hidden' },
                '& .katex': { fontSize: '1.05em' }
              }}>
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                >
                  {msg.text}
                </ReactMarkdown>
              </Box>
              <Typography
                variant="caption"
                sx={{
                  display: 'block',
                  mt: 0.5,
                  textAlign: 'right',
                  opacity: 0.7,
                  fontSize: '0.65rem',
                }}
              >
                {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </Typography>
            </Paper>
          </Box>
        ))}
        {isLoading && (
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Avatar sx={{ width: 32, height: 32, bgcolor: 'secondary.main' }}>
              <BotIcon fontSize="small" />
            </Avatar>
            <Paper elevation={1} sx={{ p: 1.5, borderRadius: 2, bgcolor: 'white' }}>
              <CircularProgress size={20} />
            </Paper>
          </Box>
        )}
        <div ref={messagesEndRef} />
      </Box>

      {/* Input Area */}
      <Box sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider' }}>
        <Stack direction="row" spacing={1}>
          <TextField
            fullWidth
            placeholder="Задать вопрос..."
            size="small"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={isLoading}
            multiline
            maxRows={4}
            autoFocus
          />
          <IconButton
            color="primary"
            onClick={handleSend}
            disabled={!inputValue.trim() || isLoading}
            sx={{ alignSelf: 'flex-end' }}
          >
            <SendIcon />
          </IconButton>
        </Stack>
      </Box>
      <Popover
        id={settingsId}
        open={isSettingsOpen}
        anchorEl={settingsAnchorEl}
        onClose={handleSettingsClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
        PaperProps={{
          sx: { p: 2, width: 280 }
        }}
      >
        <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600 }}>
          Настройки чата
        </Typography>
        <FormControl fullWidth size="small">
          <InputLabel id="model-select-label">Модель ИИ</InputLabel>
          <Select
            labelId="model-select-label"
            id="model-select"
            value={selectedModel}
            label="Модель ИИ"
            onChange={handleModelChange}
          >
            {AVAILABLE_MODELS.map((model) => (
              <MenuItem key={model.id} value={model.id}>
                {model.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Popover>
    </Drawer>
  );
};
