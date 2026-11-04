import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Box, Chip, IconButton, InputBase, Tooltip } from '@mui/material';
import { keyframes } from '@emotion/react';
import SendRoundedIcon from '@mui/icons-material/SendRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded';

/**
 * Примеры запросов, которые «печатаются» в строке ввода до начала ввода пользователем
 * и показываются в виде подсказок-чипов под строкой.
 */
const HUB_QUERY_EXAMPLES: string[] = [
  'Подбери рублёвые облигации с доходностью от 15%',
  'Покажи последнее значение ключевой ставки с датой',
  'Расскажи об облигации RU000A10D9J2',
  'Найди флоатеры с рейтингом не ниже AA-',
  'Покажи график купонов RU000A10D9J2',
  'Найди формулу купона RU000A10D9J2 в документах',
  'Какие облигации погашаются в ближайшие 6 месяцев?',
  'Подбери ОФЗ с погашением до 3 лет',
  'Найди облигации без амортизации и оферт',
  'Найди облигации с будущими выплатами в ноябре',
  'Найди облигации со ставкой купона от 16% годовых',
  'Подбери долларовые облигации с фиксированным купоном',
];

const CHIPS_VISIBLE = 3;
const TYPE_DELAY_MS = 42;
const DELETE_DELAY_MS = 18;
const HOLD_FULL_MS = 2200;
const HOLD_EMPTY_MS = 450;

const caretBlink = keyframes`
  0%, 45% { opacity: 1; }
  50%, 95% { opacity: 0; }
  100% { opacity: 1; }
`;

const orbSpin = keyframes`
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
`;

interface UseTypewriterOptions {
  phrases: string[];
  active: boolean;
}

/**
 * Эффект «печатающейся машинки»: по очереди набирает и стирает фразы.
 * Останавливается, когда `active === false` (пользователь начал вводить текст).
 */
function useTypewriter({ phrases, active }: UseTypewriterOptions): string {
  const [text, setText] = useState('');
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [phase, setPhase] = useState<'typing' | 'holding' | 'deleting'>('typing');
  const prefersReducedMotion = useMemo(
    () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches,
    [],
  );

  useEffect(() => {
    if (!active || phrases.length === 0) {
      return;
    }

    if (prefersReducedMotion) {
      const id = window.setTimeout(() => setPhraseIndex((i) => (i + 1) % phrases.length), HOLD_FULL_MS * 2);
      setText(phrases[phraseIndex] ?? '');
      return () => window.clearTimeout(id);
    }

    const current = phrases[phraseIndex] ?? '';
    let timeoutId: number;

    if (phase === 'typing') {
      if (text.length < current.length) {
        timeoutId = window.setTimeout(() => setText(current.slice(0, text.length + 1)), TYPE_DELAY_MS);
      } else {
        timeoutId = window.setTimeout(() => setPhase('deleting'), HOLD_FULL_MS);
      }
    } else if (phase === 'deleting') {
      if (text.length > 0) {
        timeoutId = window.setTimeout(() => setText(current.slice(0, text.length - 1)), DELETE_DELAY_MS);
      } else {
        timeoutId = window.setTimeout(() => {
          setPhraseIndex((i) => (i + 1) % phrases.length);
          setPhase('typing');
        }, HOLD_EMPTY_MS);
      }
    } else {
      timeoutId = window.setTimeout(() => setPhase('deleting'), HOLD_FULL_MS);
    }

    return () => window.clearTimeout(timeoutId);
  }, [active, phrases, phraseIndex, phase, text, prefersReducedMotion]);

  return active ? text : '';
}

export interface HubQueryBarProps {
  /** Вызывается при отправке запроса (Enter или кнопка). Пока без интеграции с backend. */
  onSubmit?: (query: string) => void;
}

/**
 * Строка интеллектуального запроса для главной страницы:
 * стеклянное поле ввода с анимированным плейсхолдером, кнопкой отправки
 * и чипами-подсказками с примерами запросов.
 */
export const HubQueryBar: React.FC<HubQueryBarProps> = ({ onSubmit }) => {
  const [value, setValue] = useState('');
  const [focused, setFocused] = useState(false);
  const [chipOffset, setChipOffset] = useState(0);
  const [spinning, setSpinning] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const isEmpty = value.trim().length === 0;
  const typed = useTypewriter({ phrases: HUB_QUERY_EXAMPLES, active: value.length === 0 });

  const visibleChips = useMemo(() => {
    const result: string[] = [];
    for (let i = 0; i < Math.min(CHIPS_VISIBLE, HUB_QUERY_EXAMPLES.length); i += 1) {
      result.push(HUB_QUERY_EXAMPLES[(chipOffset + i) % HUB_QUERY_EXAMPLES.length]);
    }
    return result;
  }, [chipOffset]);

  const handleSubmit = useCallback(() => {
    if (isEmpty) return;
    onSubmit?.(value.trim());
  }, [isEmpty, onSubmit, value]);

  const handleChipClick = useCallback((example: string) => {
    setValue(example);
    inputRef.current?.focus();
  }, []);

  const handleShuffle = useCallback(() => {
    setChipOffset((offset) => (offset + CHIPS_VISIBLE) % HUB_QUERY_EXAMPLES.length);
    setSpinning(true);
    window.setTimeout(() => setSpinning(false), 500);
  }, []);

  const showTypewriter = value.length === 0 && typed.length > 0;

  return (
    <Box
      component="section"
      aria-label="Строка интеллектуального запроса"
      sx={{
        width: '100%',
        maxWidth: 1660,
        mx: 'auto',
        px: { xs: 1.5, md: 3.5, xl: 4.5 },
        pb: { xs: 2, md: 3 },
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: { xs: 1.25, md: 1.5 },
      }}
    >
      <Box
        sx={{
          width: '100%',
          maxWidth: 880,
          display: 'flex',
          alignItems: 'center',
          gap: { xs: 1, md: 1.5 },
        }}
      >
        <Box
          aria-hidden="true"
          sx={{
            position: 'relative',
            flexShrink: 0,
            width: { xs: 40, md: 52 },
            height: { xs: 40, md: 52 },
            borderRadius: '50%',
            display: 'grid',
            placeItems: 'center',
            color: '#FFFFFF',
            background: 'conic-gradient(from 180deg, #7C5CFF, #4FA3FF, #C86DFF, #7C5CFF)',
            boxShadow: '0 10px 26px rgba(104, 92, 255, 0.35), inset 0 1px 0 rgba(255,255,255,0.6)',
            '&::before': {
              content: '""',
              position: 'absolute',
              inset: -3,
              borderRadius: '50%',
              background: 'conic-gradient(from 0deg, rgba(124,92,255,0.0), rgba(79,163,255,0.55), rgba(200,109,255,0.0))',
              animation: `${orbSpin} 6s linear infinite`,
              zIndex: -1,
              filter: 'blur(4px)',
            },
          }}
        >
          <AutoAwesomeRoundedIcon sx={{ fontSize: { xs: 20, md: 26 } }} />
        </Box>

        <Box
          onClick={() => inputRef.current?.focus()}
          sx={{
            position: 'relative',
            flexGrow: 1,
            minWidth: 0,
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            pl: { xs: 2, md: 2.75 },
            pr: { xs: 0.75, md: 1 },
            py: { xs: 0.75, md: 0.9 },
            borderRadius: '999px',
            border: `1px solid ${focused ? 'rgba(124, 92, 255, 0.55)' : 'rgba(255,255,255,0.82)'}`,
            background: 'rgba(255,255,255,0.62)',
            backdropFilter: 'blur(22px) saturate(150%)',
            boxShadow: focused
              ? '0 16px 40px rgba(104, 92, 255, 0.22), 0 0 0 4px rgba(124, 92, 255, 0.12), inset 0 1px 0 rgba(255,255,255,0.9)'
              : '0 14px 34px rgba(68, 104, 171, 0.14), inset 0 1px 0 rgba(255,255,255,0.9)',
            transition: 'box-shadow 220ms ease, border-color 220ms ease, background 220ms ease',
            cursor: 'text',
            '&:hover': { background: 'rgba(255,255,255,0.72)' },
          }}
        >
          <Box sx={{ position: 'relative', flexGrow: 1, minWidth: 0, display: 'flex', alignItems: 'center' }}>
            {showTypewriter && (
              <Box
                aria-hidden="true"
                sx={{
                  position: 'absolute',
                  inset: 0,
                  display: 'flex',
                  alignItems: 'center',
                  pointerEvents: 'none',
                  overflow: 'hidden',
                  whiteSpace: 'nowrap',
                  fontSize: { xs: '0.95rem', md: '1.08rem' },
                  color: '#2B4470',
                  fontWeight: 500,
                }}
              >
                <Box component="span" sx={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{typed}</Box>
                <Box
                  component="span"
                  sx={{
                    ml: '2px',
                    width: 2,
                    height: '1.15em',
                    borderRadius: 1,
                    bgcolor: '#7C5CFF',
                    animation: `${caretBlink} 1s steps(1) infinite`,
                  }}
                />
              </Box>
            )}
            <InputBase
              inputRef={inputRef}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  handleSubmit();
                }
              }}
              placeholder={showTypewriter ? '' : 'Задайте вопрос по рынку облигаций…'}
              inputProps={{ 'aria-label': 'Запрос к ассистенту BondsScreener', maxLength: 500 }}
              fullWidth
              sx={{
                fontSize: { xs: '0.95rem', md: '1.08rem' },
                fontWeight: 500,
                color: '#10264A',
                '& .MuiInputBase-input': {
                  p: 0,
                  height: { xs: 28, md: 32 },
                  lineHeight: { xs: '28px', md: '32px' },
                  '&::placeholder': { color: '#5B739A', opacity: 1 },
                },
              }}
            />
          </Box>

          <Tooltip title={isEmpty ? 'Введите запрос' : 'Отправить запрос'} placement="top">
            <span>
              <IconButton
                aria-label="Отправить запрос"
                onClick={(event) => {
                  event.stopPropagation();
                  handleSubmit();
                }}
                disabled={isEmpty}
                sx={{
                  width: { xs: 38, md: 44 },
                  height: { xs: 38, md: 44 },
                  color: '#FFFFFF',
                  background: 'linear-gradient(135deg, #7C5CFF 0%, #4FA3FF 100%)',
                  boxShadow: '0 8px 20px rgba(104, 92, 255, 0.32)',
                  transition: 'transform 180ms ease, box-shadow 180ms ease, opacity 180ms ease',
                  '&:hover': {
                    background: 'linear-gradient(135deg, #6C4BF5 0%, #3F95FF 100%)',
                    transform: 'translateX(1px) translateY(-1px)',
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
                <SendRoundedIcon sx={{ fontSize: { xs: 18, md: 21 }, transform: 'rotate(-20deg) translateX(1px)' }} />
              </IconButton>
            </span>
          </Tooltip>
        </Box>
      </Box>

      <Box
        sx={{
          width: '100%',
          maxWidth: 880,
          display: 'flex',
          alignItems: 'center',
          justifyContent: { xs: 'flex-start', md: 'center' },
          flexWrap: 'wrap',
          gap: { xs: 0.75, md: 1 },
          pl: { xs: 0, md: 0 },
        }}
      >
        <Tooltip title="Другие примеры" placement="top">
          <IconButton
            aria-label="Показать другие примеры запросов"
            size="small"
            onClick={handleShuffle}
            sx={{
              width: 32,
              height: 32,
              color: '#4A5F85',
              border: '1px solid rgba(255,255,255,0.8)',
              bgcolor: 'rgba(255,255,255,0.5)',
              backdropFilter: 'blur(14px)',
              '&:hover': { bgcolor: 'rgba(255,255,255,0.75)', color: '#7C5CFF' },
              '& svg': {
                transition: 'transform 500ms cubic-bezier(0.4, 0, 0.2, 1)',
                transform: spinning ? 'rotate(360deg)' : 'rotate(0deg)',
              },
            }}
          >
            <RefreshRoundedIcon fontSize="small" />
          </IconButton>
        </Tooltip>

        {visibleChips.map((example, index) => {
          const highlighted = index === 0;
          return (
            <Chip
              key={example}
              label={example}
              onClick={() => handleChipClick(example)}
              clickable
              sx={{
                height: 32,
                px: 0.5,
                fontSize: { xs: '0.74rem', md: '0.8rem' },
                fontWeight: 600,
                color: highlighted ? '#5B3BE8' : '#1D355B',
                border: `1px solid ${highlighted ? 'rgba(124, 92, 255, 0.45)' : 'rgba(255,255,255,0.84)'}`,
                background: highlighted
                  ? 'linear-gradient(135deg, rgba(124,92,255,0.18), rgba(79,163,255,0.16))'
                  : 'rgba(255,255,255,0.56)',
                backdropFilter: 'blur(14px) saturate(140%)',
                boxShadow: '0 4px 12px rgba(68, 104, 171, 0.1), inset 0 1px 0 rgba(255,255,255,0.85)',
                transition: 'transform 180ms ease, background 180ms ease, box-shadow 180ms ease',
                '&:hover': {
                  transform: 'translateY(-1px)',
                  background: highlighted
                    ? 'linear-gradient(135deg, rgba(124,92,255,0.28), rgba(79,163,255,0.24))'
                    : 'rgba(255,255,255,0.78)',
                  boxShadow: '0 8px 18px rgba(68, 104, 171, 0.16), inset 0 1px 0 rgba(255,255,255,0.95)',
                },
                '& .MuiChip-label': { px: 1.25, whiteSpace: 'nowrap' },
              }}
            />
          );
        })}
      </Box>
    </Box>
  );
};

export default HubQueryBar;
