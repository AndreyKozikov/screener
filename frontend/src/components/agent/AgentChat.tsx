import React, { useEffect, useRef, useState } from 'react';
import {
  Avatar,
  Box,
  Chip,
  CircularProgress,
  IconButton,
  InputBase,
  Paper,
  Tooltip,
  Typography,
  List, ListItemButton, ListItemText, Divider,
} from '@mui/material';
import {
  ContentCopy as CopyIcon,
  Person as UserIcon,
  Refresh as ResetIcon,
  Send as SendIcon,
  SmartToy as BotIcon,
  MenuOpen as CollapseIcon, Menu as ExpandIcon, DeleteOutline as DeleteIcon, Add as AddIcon,
} from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { useAgentStore, type AgentMessage } from '../../stores/agentStore';

const GREETING =
  'Привет! Я ИИ-ассистент BondsScreener. Подберу для вас облигации, ' +
  'отвечу по ключевой ставке, купонам и деталям бумаг. ' +
  'Например, напишите: «Подбери облигации с доходностью выше 15%».';

const MessageBubble: React.FC<{ msg: AgentMessage }> = ({ msg }) => {
  const isUser = msg.role === 'user';
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: isUser ? 'row-reverse' : 'row',
        alignItems: 'flex-start',
        gap: 1.25,
        maxWidth: '100%',
      }}
    >
      <Avatar
        sx={{
          flexShrink: 0,
          width: 34,
          height: 34,
          color: '#FFFFFF',
          fontSize: '0.8rem',
          bgcolor: isUser ? 'transparent' : 'transparent',
          background: isUser
            ? 'linear-gradient(135deg, #7C5CFF 0%, #4FA3FF 100%)'
            : 'linear-gradient(145deg, rgba(255,255,255,0.95), rgba(240,247,255,0.9))',
          border: isUser ? 'none' : '1px solid rgba(124,92,255,0.35)',
          boxShadow: isUser
            ? '0 6px 14px rgba(104, 92, 255, 0.28)'
            : '0 4px 12px rgba(68, 104, 171, 0.14), inset 0 1px 0 rgba(255,255,255,0.9)',
        }}
      >
        {isUser ? <UserIcon fontSize="small" /> : <BotIcon fontSize="small" sx={{ color: '#5B3BE8' }} />}
      </Avatar>
      <Paper
        elevation={0}
        sx={{
          p: { xs: 1.25, md: 1.5 },
          maxWidth: { xs: 'calc(100% - 48px)', md: '78%' },
          borderRadius: isUser ? '18px 18px 6px 18px' : '18px 18px 18px 6px',
          border: `1px solid ${isUser ? 'rgba(124, 92, 255, 0.35)' : 'rgba(255,255,255,0.9)'}`,
          background: isUser
            ? 'linear-gradient(135deg, #7C5CFF 0%, #4FA3FF 100%)'
            : 'rgba(255,255,255,0.78)',
          color: isUser ? '#FFFFFF' : '#10264A',
          boxShadow: isUser
            ? '0 10px 22px rgba(104, 92, 255, 0.22)'
            : '0 8px 20px rgba(68, 104, 171, 0.1), inset 0 1px 0 rgba(255,255,255,0.85)',
          backdropFilter: 'blur(16px)',
          fontFamily: 'var(--app-font-family)',
          '& p': { m: 0, mb: 0.5, fontSize: '0.92rem', lineHeight: 1.55 },
          '& p:last-child': { mb: 0 },
          '& ul, & ol': { pl: 2, m: 0, mb: 1, fontSize: '0.92rem' },
          '& li': { mb: 0.5 },
          '& h1, & h2, & h3, & h4': { fontSize: '1rem', fontWeight: 650, m: '0 0 0.5rem 0' },
          '& a': { color: isUser ? '#FFFFFF' : '#1769E8', fontWeight: 600 },
          '& code': {
            bgcolor: isUser ? 'rgba(255,255,255,0.22)' : 'rgba(21,88,166,0.1)',
            color: isUser ? '#FFFFFF' : '#1D355B',
            px: 0.5,
            py: 0.1,
            borderRadius: 0.5,
            fontFamily: 'ui-monospace, "Cascadia Code", "Source Code Pro", monospace',
            fontSize: '0.82em',
          },
          '& table': { borderCollapse: 'collapse', width: '100%', mb: 1, fontSize: '0.8rem' },
          '& th, & td': {
            border: '1px solid',
            borderColor: isUser ? 'rgba(255,255,255,0.35)' : 'rgba(160,184,214,0.55)',
            p: 0.5,
          },
        }}
      >
        <Box sx={{ '& .katex-display': { my: 1 }, '& .katex': { fontSize: '1.05em' } }}>
          <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
            {msg.content}
          </ReactMarkdown>
        </Box>
        {!isUser && msg.sources && msg.sources.length > 0 && (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
            {msg.sources.map((src) => (
              <Chip
                key={src.secid}
                size="small"
                label={src.secid}
                variant="outlined"
                sx={{
                  fontSize: '0.68rem',
                  height: 22,
                  color: '#5B3BE8',
                  borderColor: 'rgba(124,92,255,0.4)',
                  bgcolor: 'rgba(124,92,255,0.06)',
                }}
                title={src.shortname || undefined}
              />
            ))}
          </Box>
        )}
        <Typography
          variant="caption"
          sx={{
            display: 'block',
            mt: 0.5,
            textAlign: 'right',
            opacity: 0.65,
            fontSize: '0.64rem',
          }}
        >
          {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </Typography>
      </Paper>
    </Box>
  );
};

/**
 * Полностраничный чат с ИИ-ассистентом. Заполняет родительский контейнер целиком
 * и выдержан в стеклянном стиле главной страницы BondsScreener.
 */
export const AgentChat: React.FC = () => {
  const { messages, isLoading, resetChat, send, error, sessionId, chats, loadChats, openChat, removeChat } = useAgentStore();
  const [inputValue, setInputValue] = useState('');
  const [historyOpen, setHistoryOpen] = useState(true);
  const [copied, setCopied] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null);

  const handleCopyId = async () => {
    if (!sessionId) return;
    try {
      await navigator.clipboard.writeText(sessionId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* буфер обмена недоступен — игнорируем */
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);
  useEffect(() => { void loadChats(); }, [loadChats]);

  const handleSend = () => {
    const value = inputValue.trim();
    if (!value || isLoading) return;
    setInputValue('');
    void send(value);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const visibleMessages = messages.length > 0 ? messages : [];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'row-reverse', gap: 1, width: '100%', height: '100%', minWidth: 0 }}>
    <Box
      sx={{ width: historyOpen ? { xs: 220, md: 270 } : 48, flexShrink: 0, display: 'flex', flexDirection: 'column', minHeight: 0, borderRadius: 3, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.82)', bgcolor: 'rgba(255,255,255,0.52)', backdropFilter: 'blur(18px)', transition: 'width 180ms ease' }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: historyOpen ? 'space-between' : 'center', p: 0.75 }}>
        {historyOpen && <Typography sx={{ pl: 1, fontWeight: 650, color: '#17345B', fontSize: '.9rem' }}>Мои чаты</Typography>}
        <Tooltip title={historyOpen ? 'Свернуть историю' : 'Показать историю'}><IconButton size="small" onClick={() => setHistoryOpen((v) => !v)} aria-label={historyOpen ? 'Свернуть историю чатов' : 'Показать историю чатов'}>{historyOpen ? <CollapseIcon /> : <ExpandIcon />}</IconButton></Tooltip>
      </Box>
      {historyOpen && <>
        <Box sx={{ px: 1, pb: 1 }}><IconButton size="small" onClick={resetChat} aria-label="Новый чат"><AddIcon /><Typography sx={{ ml: .5, fontSize: '.82rem' }}>Новый чат</Typography></IconButton></Box>
        <Divider />
        <List dense sx={{ overflowY: 'auto', flex: 1, p: .75 }}>
          {chats.map((chat) => <ListItemButton key={chat.session_id} selected={sessionId === chat.session_id} onClick={() => void openChat(chat.session_id)} sx={{ borderRadius: 1.5, pr: .5, mb: .4 }}>
            <ListItemText primary={chat.title || 'Новый чат'} secondary={chat.preview || ''} primaryTypographyProps={{ noWrap: true, fontSize: '.82rem', fontWeight: 600 }} secondaryTypographyProps={{ noWrap: true, fontSize: '.7rem' }} />
            <IconButton size="small" aria-label="Удалить чат" onClick={(event) => { event.stopPropagation(); void removeChat(chat.session_id); }}><DeleteIcon sx={{ fontSize: 17 }} /></IconButton>
          </ListItemButton>)}
          {chats.length === 0 && <Typography sx={{ p: 1, color: '#587092', fontSize: '.78rem' }}>Сохранённых чатов пока нет</Typography>}
        </List>
      </>}
    </Box>
    <Box
      sx={{
        flexGrow: 1,
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        border: '1px solid rgba(255,255,255,0.82)',
        borderRadius: { xs: '18px', md: '24px' },
        background: 'rgba(255,255,255,0.5)',
        boxShadow: '0 14px 34px rgba(73, 105, 160, 0.14), inset 0 1px 0 rgba(255,255,255,0.75)',
        backdropFilter: 'blur(22px) saturate(145%)',
      }}
    >
      <Box
        sx={{
          flexShrink: 0,
          px: { xs: 1.5, md: 2.25 },
          py: { xs: 1.25, md: 1.5 },
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 1.5,
          borderBottom: '1px solid rgba(255,255,255,0.72)',
          background: 'linear-gradient(135deg, rgba(255,255,255,0.62), rgba(240,247,255,0.4))',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, minWidth: 0 }}>
          <Box
            aria-hidden="true"
            sx={{
              flexShrink: 0,
              width: { xs: 40, md: 46 },
              height: { xs: 40, md: 46 },
              borderRadius: '50%',
              display: 'grid',
              placeItems: 'center',
              color: '#FFFFFF',
              background: 'conic-gradient(from 180deg, #7C5CFF, #4FA3FF, #C86DFF, #7C5CFF)',
              boxShadow: '0 10px 26px rgba(104, 92, 255, 0.35), inset 0 1px 0 rgba(255,255,255,0.6)',
            }}
          >
            <BotIcon sx={{ fontSize: { xs: 20, md: 24 } }} />
          </Box>
          <Box sx={{ minWidth: 0 }}>
            <Typography
              sx={{
                fontSize: { xs: '0.98rem', md: '1.08rem' },
                fontWeight: 650,
                lineHeight: 1.25,
                color: '#10264A',
                fontFamily: 'var(--app-font-family)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              ИИ-ассистент BondsScreener
            </Typography>
            <Typography
              sx={{
                mt: 0.15,
                fontSize: { xs: '0.72rem', md: '0.78rem' },
                lineHeight: 1.3,
                color: '#587092',
                fontFamily: 'var(--app-font-family)',
              }}
            >
              Подбор облигаций и ответы по рынку
            </Typography>
            {sessionId && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.35 }}>
                <Typography
                  sx={{
                    opacity: 0.85,
                    fontFamily: 'ui-monospace, "Cascadia Code", "Source Code Pro", monospace',
                    fontSize: '0.66rem',
                    lineHeight: 1.2,
                    color: '#5B739A',
                    wordBreak: 'break-all',
                    maxWidth: { xs: 180, md: 420 },
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  ID: {sessionId}
                </Typography>
                <Tooltip title={copied ? 'Скопировано' : 'Скопировать ID диалога'}>
                  <IconButton
                    size="small"
                    onClick={handleCopyId}
                    sx={{
                      p: 0.35,
                      color: '#5B3BE8',
                      bgcolor: 'rgba(255,255,255,0.6)',
                      border: '1px solid rgba(255,255,255,0.85)',
                      '&:hover': { bgcolor: 'rgba(255,255,255,0.9)' },
                    }}
                  >
                    <CopyIcon sx={{ fontSize: 13 }} />
                  </IconButton>
                </Tooltip>
              </Box>
            )}
          </Box>
        </Box>
        <Tooltip title="Начать новый диалог">
          <IconButton
            size="small"
          onClick={resetChat}
            aria-label="Начать новый диалог"
            sx={{
              flexShrink: 0,
              width: { xs: 34, md: 38 },
              height: { xs: 34, md: 38 },
              color: '#29476F',
              bgcolor: 'rgba(255,255,255,0.5)',
              border: '1px solid rgba(255,255,255,0.82)',
              '&:hover': { bgcolor: 'rgba(255,255,255,0.85)', color: '#5B3BE8' },
            }}
          >
            <ResetIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      <Box
        sx={{
          flexGrow: 1,
          minHeight: 0,
          p: { xs: 1.5, md: 2.5 },
          overflowY: 'auto',
          overscrollBehaviorY: 'contain',
          display: 'flex',
          flexDirection: 'column',
          gap: 1.75,
          scrollbarWidth: 'thin',
          scrollbarColor: 'rgba(21,88,166,0.28) transparent',
          '&::-webkit-scrollbar': { width: 8 },
          '&::-webkit-scrollbar-thumb': { bgcolor: 'rgba(21,88,166,0.28)', borderRadius: 4 },
          '&::-webkit-scrollbar-track': { background: 'transparent' },
        }}
      >
        {visibleMessages.length === 0 && (
          <MessageBubble msg={{ id: 'greeting', role: 'assistant', content: GREETING, timestamp: 0 }} />
        )}
        {visibleMessages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}
        {isLoading && (
          <Box sx={{ display: 'flex', gap: 1.25, alignItems: 'flex-start' }}>
            <Avatar
              sx={{
                width: 34,
                height: 34,
                color: '#FFFFFF',
                background: 'linear-gradient(145deg, rgba(255,255,255,0.95), rgba(240,247,255,0.9))',
                border: '1px solid rgba(124,92,255,0.35)',
                boxShadow: '0 4px 12px rgba(68, 104, 171, 0.14)',
              }}
            >
              <BotIcon fontSize="small" sx={{ color: '#5B3BE8' }} />
            </Avatar>
            <Paper
              elevation={0}
              sx={{
                p: 1.5,
                borderRadius: '18px 18px 18px 6px',
                border: '1px solid rgba(255,255,255,0.9)',
                bgcolor: 'rgba(255,255,255,0.78)',
                boxShadow: '0 8px 20px rgba(68, 104, 171, 0.1)',
              }}
            >
              <CircularProgress size={20} sx={{ color: '#7C5CFF' }} />
            </Paper>
          </Box>
        )}
        {error && (
          <Paper
            elevation={0}
            sx={{
              p: 1.5,
              borderRadius: 2.5,
              bgcolor: 'rgba(255,82,82,0.08)',
              border: '1px solid rgba(244,67,54,0.32)',
              color: '#C62828',
              fontFamily: 'var(--app-font-family)',
            }}
          >
            <Typography variant="body2">{error}</Typography>
          </Paper>
        )}
        <div ref={messagesEndRef} />
      </Box>

      <Box
        sx={{
          flexShrink: 0,
          px: { xs: 1.25, md: 2.25 },
          py: { xs: 1.25, md: 1.75 },
          borderTop: '1px solid rgba(255,255,255,0.72)',
          background: 'linear-gradient(180deg, rgba(255,255,255,0.3), rgba(240,247,255,0.18))',
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'flex-end',
            gap: { xs: 0.75, md: 1 },
            border: '1px solid rgba(255,255,255,0.85)',
            borderRadius: '999px',
            background: 'rgba(255,255,255,0.62)',
            backdropFilter: 'blur(18px) saturate(140%)',
            boxShadow: '0 10px 24px rgba(68, 104, 171, 0.12), inset 0 1px 0 rgba(255,255,255,0.9)',
            transition: 'box-shadow 220ms ease, border-color 220ms ease, background 220ms ease',
            py: { xs: 0.5, md: 0.65 },
            pr: { xs: 0.5, md: 0.75 },
            pl: 1.75,
            '&:focus-within': {
              borderColor: 'rgba(124, 92, 255, 0.55)',
              boxShadow: '0 14px 34px rgba(104, 92, 255, 0.2), 0 0 0 4px rgba(124, 92, 255, 0.12)',
            },
          }}
        >
          <InputBase
            inputRef={inputRef}
            fullWidth
            multiline
            maxRows={5}
            autoFocus
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            onKeyDown={handleKeyPress}
            disabled={isLoading}
            placeholder={isLoading ? 'Ассистент отвечает…' : 'Задайте вопрос или уточните условия подбора…'}
            inputProps={{ 'aria-label': 'Сообщение ассистенту BondsScreener', maxLength: 500 }}
            sx={{
              flexGrow: 1,
              alignSelf: 'center',
              fontSize: { xs: '0.92rem', md: '0.98rem' },
              fontWeight: 500,
              color: '#10264A',
              fontFamily: 'var(--app-font-family)',
              '& .MuiInputBase-input': {
                py: { xs: 0.5, md: 0.55 },
                px: 0,
                lineHeight: 1.45,
                '&::placeholder': { color: '#5B739A', opacity: 1 },
              },
            }}
          />
          <Tooltip title={!inputValue.trim() ? 'Введите сообщение' : 'Отправить сообщение'} placement="top">
            <span>
              <IconButton
                aria-label="Отправить сообщение"
                onClick={handleSend}
                disabled={!inputValue.trim() || isLoading}
                sx={{
                  width: { xs: 40, md: 46 },
                  height: { xs: 40, md: 46 },
                  flexShrink: 0,
                  color: '#FFFFFF',
                  background: 'linear-gradient(135deg, #7C5CFF 0%, #4FA3FF 100%)',
                  boxShadow: '0 8px 20px rgba(104, 92, 255, 0.32)',
                  transition: 'transform 180ms ease, box-shadow 180ms ease, opacity 180ms ease',
                  '&:hover': {
                    background: 'linear-gradient(135deg, #6C4BF5 0%, #3F95FF 100%)',
                    transform: 'translateY(-1px)',
                    boxShadow: '0 12px 26px rgba(104, 92, 255, 0.4)',
                  },
                  '&.Mui-disabled': {
                    color: '#FFFFFF',
                    opacity: 0.55,
                    background: 'linear-gradient(135deg, #9D8CFF 0%, #8DC0FF 100%)',
                    boxShadow: 'none',
                  },
                }}
              >
                <SendIcon sx={{ fontSize: { xs: 18, md: 21 }, transform: 'rotate(-20deg) translateX(1px)' }} />
              </IconButton>
            </span>
          </Tooltip>
        </Box>
      </Box>
    </Box>
    </Box>
  );
};

export default AgentChat;
