import React from 'react';
import { Box, Card, Typography, alpha } from '@mui/material';

type ForecastHubCardProps = {
  title: string;
  value: string;
  subtitle: string;
  icon: React.ReactNode;
  color: string;
  onClick: () => void;
};

export const ForecastHubCard: React.FC<ForecastHubCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  color,
  onClick,
}) => (
  <Card
    role="button"
    tabIndex={0}
    aria-label={`${title}. ${value}. ${subtitle}`}
    onClick={onClick}
    onKeyDown={(event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onClick();
      }
    }}
    sx={{
      position: 'relative',
      height: { xs: 270, md: 300, xl: 310 },
      overflow: 'hidden',
      borderRadius: { xs: '20px', md: '23px' },
      border: '1px solid rgba(255,255,255,0.88)',
      background: `linear-gradient(145deg, rgba(255,255,255,0.58), ${alpha(color, 0.08)})`,
      backdropFilter: 'blur(22px) saturate(145%)',
      boxShadow: '0 12px 30px rgba(72, 111, 178, 0.13), inset 0 1px 0 rgba(255,255,255,0.82)',
      cursor: 'pointer',
      transition: 'transform 220ms ease, box-shadow 220ms ease, background 220ms ease',
      '&::before': {
        content: '""',
        position: 'absolute',
        inset: 0,
        background: `radial-gradient(circle at 88% 22%, ${alpha(color, 0.1)}, transparent 42%)`,
        pointerEvents: 'none',
      },
      '&:hover, &:focus-visible': {
        transform: 'translateY(-3px)',
        boxShadow: '0 18px 38px rgba(72, 111, 178, 0.19), inset 0 1px 0 rgba(255,255,255,0.95)',
      },
      '&:focus-visible': { outline: `3px solid ${alpha(color, 0.38)}`, outlineOffset: 3 },
    }}
  >
    <Box
      aria-hidden="true"
      sx={{
        position: 'absolute',
        zIndex: 0,
        left: 0,
        right: 0,
        bottom: 0,
        height: { xs: 82, md: 102 },
        opacity: 0.58,
        pointerEvents: 'none',
        '& svg': { display: 'block', width: '100%', height: '100%' },
      }}
    >
      <svg viewBox="0 0 490 105" preserveAspectRatio="none">
        <path d="M0 91 C64 63 92 77 134 91 C190 110 226 52 285 51 C342 50 367 70 414 54 C450 42 460 24 490 12 L490 105 L0 105Z" fill={color} opacity="0.055" />
        <path d="M0 91 C64 63 92 77 134 91 C190 110 226 52 285 51 C342 50 367 70 414 54 C450 42 460 24 490 12" fill="none" stroke={color} strokeWidth="2" opacity="0.3" />
        <path d="M0 104 C77 70 103 102 156 104 C226 107 266 73 320 82 C375 91 407 103 490 58" fill="none" stroke="#ffffff" strokeWidth="2.4" opacity="0.76" />
      </svg>
    </Box>

    <Box sx={{ position: 'relative', zIndex: 1, p: { xs: 2.5, md: 3 } }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.75, minHeight: { xs: 54, md: 68 } }}>
        <Box
          className="forecast-hub-card-icon"
          sx={{
            flexShrink: 0,
            width: { xs: 56, md: 68 },
            height: { xs: 56, md: 68 },
            display: 'grid',
            placeItems: 'center',
            borderRadius: '50%',
            color,
            bgcolor: alpha(color, 0.12),
            border: '1px solid rgba(255,255,255,0.92)',
            boxShadow: `0 4px 12px ${alpha(color, 0.08)}, inset 0 1px 0 rgba(255,255,255,0.72)`,
            '& svg': { fontSize: { xs: 30, md: 35 } },
          }}
        >
          {icon}
        </Box>
        <Typography
          component="h2"
          sx={{
            color: '#0d1d4b',
            fontSize: { xs: '0.9rem', md: '1.08rem' },
            lineHeight: 1.35,
            letterSpacing: '0.005em',
            fontWeight: 700,
          }}
        >
          {title}
        </Typography>
      </Box>

      <Typography
        component="p"
        sx={{
          mt: { xs: 1.25, md: 1.75 },
          color: '#0a1b4c',
          fontSize: { xs: '2.25rem', md: '3rem' },
          lineHeight: 1.08,
          letterSpacing: '0.005em',
          fontWeight: 760,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {value}
      </Typography>

      <Typography
        sx={{
          position: 'relative',
          zIndex: 1,
          mt: 1.2,
          maxWidth: '92%',
          color: '#465f89',
          fontSize: { xs: '0.9rem', md: '1rem' },
          lineHeight: 1.5,
        }}
      >
        {subtitle}
      </Typography>
    </Box>

    <Box
      className="forecast-hub-card-arrow"
      aria-hidden="true"
      sx={{
        position: 'absolute',
        zIndex: 2,
        right: { xs: 16, md: 20 },
        bottom: { xs: 16, md: 20 },
        width: { xs: 40, md: 48 },
        height: { xs: 40, md: 48 },
        display: 'grid',
        placeItems: 'center',
        borderRadius: '50%',
        border: '1px solid rgba(255,255,255,0.92)',
        color,
        bgcolor: 'rgba(255,255,255,0.58)',
        boxShadow: '0 4px 12px rgba(62, 99, 160, 0.11)',
        fontSize: { xs: '1.45rem', md: '1.7rem' },
        lineHeight: 1,
        transition: 'transform 180ms ease',
        '.MuiCard-root:hover &, .MuiCard-root:focus-visible &': { transform: 'translateX(3px)' },
      }}
    >
      →
    </Box>
  </Card>
);



