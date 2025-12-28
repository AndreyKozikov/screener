import React from 'react';
import { Card, Avatar, Typography, Box, alpha } from '@mui/material';
import type { SxProps, Theme } from '@mui/material';

export interface HubCardProps {
  title: string;
  value: string | number;
  subtitle: string;
  icon: React.ReactNode;
  color?: string;
  trend?: number[]; // Optional sparkline data (array of numbers)
  onClick?: () => void;
  sx?: SxProps<Theme>;
}

/**
 * HubCard Component
 * 
 * A card component for the Portfolio Workbench Hub view
 * Displays icon, title, value, subtitle, and optional trend sparkline
 */
export const HubCard: React.FC<HubCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  color = '#1976d2',
  trend,
  onClick,
  sx,
}) => {
  // Format value if it's a number (for currency formatting)
  const formattedValue = typeof value === 'number'
    ? new Intl.NumberFormat('ru-RU', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      }).format(value)
    : value;

  // Determine trend color (green for positive, red for negative)
  const trendColor = trend && trend.length > 1
    ? trend[trend[trend.length - 1]] >= trend[0]
      ? '#4caf50' // Green for positive
      : '#f44336' // Red for negative
    : '#757575'; // Gray if no trend

  // Generate sparkline SVG path
  const generateSparklinePath = (data: number[]): string => {
    if (data.length === 0) return '';

    const width = 80;
    const height = 30;
    const padding = 2;

    // Normalize data to fit in the SVG area
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1; // Avoid division by zero

    const points = data.map((val, index) => {
      const x = (index / (data.length - 1 || 1)) * (width - padding * 2) + padding;
      const y = height - padding - ((val - min) / range) * (height - padding * 2);
      return `${x},${y}`;
    });

    return `M ${points.join(' L ')}`;
  };

  return (
    <Card
      variant="outlined"
      onClick={onClick}
      sx={{
        height: 180,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        borderRadius: '20px',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        backgroundColor: '#ffffff',
        border: '1px solid #E2E8F0',
        boxShadow: 'none',
        '&:hover': onClick ? {
          transform: 'translateY(-5px)',
          boxShadow: '0px 8px 24px rgba(0, 0, 0, 0.08)',
          '& .hub-card-icon': {
            transform: 'scale(1.05)',
          },
        } : {},
        ...sx,
      }}
    >
      <Box sx={{ p: 2, pb: 1 }}>
        {/* Top: Icon and Title */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
          <Avatar
            className="hub-card-icon"
            sx={{
              bgcolor: alpha(color, 0.1),
              color: color,
              width: 40,
              height: 40,
              transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
              backdropFilter: 'blur(10px)',
            }}
          >
            {icon}
          </Avatar>
          <Typography
            variant="body2"
            sx={{
              fontWeight: 600,
              fontSize: '0.875rem',
              color: 'text.primary',
              flex: 1,
              fontFamily: '"Inter", "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
              letterSpacing: '-0.01em',
            }}
          >
            {title}
          </Typography>
        </Box>

        {/* Middle: Value */}
        <Typography
          variant="h4"
          sx={{
            fontWeight: 600,
            fontSize: '2rem',
            color: 'text.primary',
            mb: 1,
            lineHeight: 1.2,
            fontFamily: '"Inter", "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            letterSpacing: '-0.02em',
          }}
        >
          {formattedValue}
        </Typography>
      </Box>

      {/* Bottom: Subtitle and Trend */}
      <Box sx={{ p: 2, pt: 1, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
        <Typography
          variant="caption"
          sx={{
            color: 'text.secondary',
            fontSize: '0.75rem',
            flex: 1,
            fontFamily: '"Inter", "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          }}
        >
          {subtitle}
        </Typography>
        {trend && trend.length > 0 && (
          <Box
            sx={{
              ml: 1,
              display: 'flex',
              alignItems: 'center',
              flexShrink: 0,
            }}
          >
            <svg
              width={80}
              height={30}
              style={{ display: 'block' }}
            >
              <path
                d={generateSparklinePath(trend)}
                fill="none"
                stroke={trendColor}
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </Box>
        )}
      </Box>
    </Card>
  );
};

