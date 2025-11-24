import { createTheme } from '@mui/material/styles';

/**
 * Custom Material UI theme for Bonds Screener
 * 
 * Design Approach: "Clean Data Application"
 * - Light theme optimized for data readability
 * - Blue accent colors for trust and finance
 * - Generous spacing for clarity
 * - Professional typography
 */
export const theme = createTheme({
  // Color Palette
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',      // Primary Blue
      light: '#42a5f5',
      dark: '#1565c0',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#424242',      // Dark Gray
      light: '#6d6d6d',
      dark: '#1b1b1b',
      contrastText: '#ffffff',
    },
    success: {
      main: '#4caf50',      // Success Green
      light: '#81c784',
      dark: '#388e3c',
    },
    error: {
      main: '#f44336',      // Error Red
      light: '#e57373',
      dark: '#d32f2f',
    },
    warning: {
      main: '#ff9800',      // Warning Orange
      light: '#ffb74d',
      dark: '#f57c00',
    },
    background: {
      default: '#f5f5f5',   // Light Gray Background
      paper: '#ffffff',      // White for cards/panels
    },
    text: {
      primary: '#212121',    // Almost Black
      secondary: '#757575',  // Medium Gray
      disabled: '#bdbdbd',   // Light Gray
    },
    divider: '#e0e0e0',
  },

  // Typography
  typography: {
    fontFamily: [
      'Inter',
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      'Roboto',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
    ].join(','),
    fontSize: 14,
    fontWeightLight: 300,
    fontWeightRegular: 400,
    fontWeightMedium: 500,
    fontWeightBold: 700,
    
    h1: {
      fontSize: '2rem',
      fontWeight: 700,
      lineHeight: 1.2,
      letterSpacing: '-0.02em',
    },
    h2: {
      fontSize: '1.5rem',
      fontWeight: 600,
      lineHeight: 1.3,
      letterSpacing: '-0.01em',
    },
    h3: {
      fontSize: '1.25rem',
      fontWeight: 600,
      lineHeight: 1.4,
    },
    h4: {
      fontSize: '1rem',
      fontWeight: 600,
      lineHeight: 1.5,
    },
    h5: {
      fontSize: '0.875rem',
      fontWeight: 600,
      lineHeight: 1.5,
    },
    h6: {
      fontSize: '0.75rem',
      fontWeight: 600,
      lineHeight: 1.5,
      textTransform: 'uppercase',
      letterSpacing: '0.08em',
    },
    body1: {
      fontSize: '0.875rem',
      lineHeight: 1.5,
    },
    body2: {
      fontSize: '0.75rem',
      lineHeight: 1.43,
    },
    button: {
      fontSize: '0.875rem',
      fontWeight: 500,
      textTransform: 'none', // No uppercase for better readability
    },
    caption: {
      fontSize: '0.75rem',
      lineHeight: 1.66,
      color: '#757575',
    },
  },

  // Spacing (8px base unit)
  spacing: 8,

  // Shape (border radius)
  shape: {
    borderRadius: 8,
  },

  // Shadows (subtle for clean look)
  shadows: [
    'none',
    '0px 1px 3px rgba(0, 0, 0, 0.08)',
    '0px 2px 4px rgba(0, 0, 0, 0.08)',
    '0px 3px 6px rgba(0, 0, 0, 0.08)',
    '0px 4px 8px rgba(0, 0, 0, 0.08)',
    '0px 6px 12px rgba(0, 0, 0, 0.08)',
    '0px 8px 16px rgba(0, 0, 0, 0.08)',
    '0px 12px 24px rgba(0, 0, 0, 0.08)',
    '0px 16px 32px rgba(0, 0, 0, 0.08)',
    '0px 20px 40px rgba(0, 0, 0, 0.08)',
    '0px 24px 48px rgba(0, 0, 0, 0.08)',
    '0px 2px 4px -1px rgba(0,0,0,0.06)',
    '0px 3px 5px -1px rgba(0,0,0,0.06)',
    '0px 4px 6px -1px rgba(0,0,0,0.06)',
    '0px 5px 7px -1px rgba(0,0,0,0.06)',
    '0px 6px 8px -1px rgba(0,0,0,0.06)',
    '0px 7px 9px -1px rgba(0,0,0,0.06)',
    '0px 8px 10px -1px rgba(0,0,0,0.06)',
    '0px 9px 11px -1px rgba(0,0,0,0.06)',
    '0px 10px 12px -1px rgba(0,0,0,0.06)',
    '0px 11px 13px -1px rgba(0,0,0,0.06)',
    '0px 12px 14px -1px rgba(0,0,0,0.06)',
    '0px 13px 15px -1px rgba(0,0,0,0.06)',
    '0px 14px 16px -1px rgba(0,0,0,0.06)',
    '0px 15px 17px -1px rgba(0,0,0,0.06)',
  ],

  // Component overrides
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          padding: '8px 16px',
          textTransform: 'none',
        },
        contained: {
          boxShadow: 'none',
          '&:hover': {
            boxShadow: '0px 2px 4px rgba(0, 0, 0, 0.08)',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: '0px 2px 8px rgba(0, 0, 0, 0.08)',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
        elevation1: {
          boxShadow: '0px 2px 4px rgba(0, 0, 0, 0.08)',
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 8,
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 6,
          fontWeight: 500,
        },
      },
    },
  },

  // Breakpoints (default values, documented for clarity)
  breakpoints: {
    values: {
      xs: 0,
      sm: 600,
      md: 900,
      lg: 1200,
      xl: 1536,
    },
  },
});

export default theme;
