import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  useMediaQuery,
  List,
  ListItem,
  ListItemText,
  Divider,
  Chip,
  Card,
  alpha,
  useTheme,
} from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { fetchBondCoupons } from '../../api/bonds';
import { formatNumber } from '../../utils/formatters';

/**
 * Payment event for a specific date
 */
interface PaymentEvent {
  date: Date;
  bondShortName: string;
  bondSecid: string;
  amount: number; // Сумма выплаты с учетом количества облигаций
  currency: string;
  type: 'coupon' | 'maturity'; // Тип выплаты: купон или погашение
}

/**
 * Month summary data
 */
interface MonthSummary {
  year: number;
  month: number; // 0-11
  totalAmount: number;
  currency: string;
}

/**
 * PaymentCalendar Component
 * 
 * Displays a calendar of bond payments with:
 * - Left side: Monthly overview table
 * - Right side: Calendar grid with daily payments
 */
export const PaymentCalendar: React.FC = () => {
  const portfolioBonds = usePortfolioStore((state) => state.portfolioBonds);
  const muiTheme = useTheme();
  const isMobile = useMediaQuery(muiTheme.breakpoints.down('md'));

  // Current selected month (default: current month)
  const [selectedDate, setSelectedDate] = useState<Date>(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  // Loading and error states
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // All payment events
  const [paymentEvents, setPaymentEvents] = useState<PaymentEvent[]>([]);

  // Load coupons for all portfolio bonds
  useEffect(() => {
    const loadCoupons = async () => {
      if (portfolioBonds.length === 0) {
        setPaymentEvents([]);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const allPayments: PaymentEvent[] = [];

        // Load coupons for each bond in portfolio
        for (const bond of portfolioBonds) {
          try {
            const couponsResponse = await fetchBondCoupons(bond.SECID);
            const coupons = couponsResponse.coupons || [];

            // Process coupons
            for (const coupon of coupons) {
              if (coupon.coupondate) {
                const couponDate = new Date(coupon.coupondate);
                const today = new Date();
                today.setHours(0, 0, 0, 0);

                // Only include future coupons
                if (couponDate >= today) {
                  const quantity = bond.quantity || 1;
                  const couponValue = coupon.value || 0;
                  const totalAmount = couponValue * quantity;

                  allPayments.push({
                    date: couponDate,
                    bondShortName: bond.SHORTNAME || bond.SECID,
                    bondSecid: bond.SECID,
                    amount: totalAmount,
                    currency: coupon.faceunit || bond.FACEUNIT || 'RUB',
                    type: 'coupon',
                  });
                }
              }
            }

            // Check for maturity date
            if (bond.MATDATE) {
              const matDate = new Date(bond.MATDATE);
              const today = new Date();
              today.setHours(0, 0, 0, 0);

              // Only include future maturity
              if (matDate >= today) {
                const quantity = bond.quantity || 1;
                const faceValue = bond.FACEVALUE || 0;
                const totalAmount = faceValue * quantity;

                allPayments.push({
                  date: matDate,
                  bondShortName: bond.SHORTNAME || bond.SECID,
                  bondSecid: bond.SECID,
                  amount: totalAmount,
                  currency: bond.FACEUNIT || 'RUB',
                  type: 'maturity',
                });
              }
            }
          } catch (err) {
            console.error(`Failed to load coupons for ${bond.SECID}:`, err);
            // Continue loading other bonds even if one fails
          }
        }

        // Sort by date
        allPayments.sort((a, b) => a.date.getTime() - b.date.getTime());

        setPaymentEvents(allPayments);
      } catch (err) {
        console.error('Failed to load payment calendar:', err);
        setError(err instanceof Error ? err.message : 'Не удалось загрузить календарь выплат');
      } finally {
        setIsLoading(false);
      }
    };

    void loadCoupons();
  }, [portfolioBonds]);

  // Calculate month summaries
  const monthSummaries = useMemo(() => {
    const summaries = new Map<string, MonthSummary>();

    paymentEvents.forEach((payment) => {
      const year = payment.date.getFullYear();
      const month = payment.date.getMonth();
      const key = `${year}-${month}`;

      if (!summaries.has(key)) {
        summaries.set(key, {
          year,
          month,
          totalAmount: 0,
          currency: payment.currency,
        });
      }

      const summary = summaries.get(key)!;
      // Sum amounts in the same currency
      if (summary.currency === payment.currency) {
        summary.totalAmount += payment.amount;
      }
    });

    // Convert to array and sort by date
    return Array.from(summaries.values()).sort((a, b) => {
      if (a.year !== b.year) return a.year - b.year;
      return a.month - b.month;
    });
  }, [paymentEvents]);

  // Get payments for selected month
  const selectedMonthPayments = useMemo(() => {
    const year = selectedDate.getFullYear();
    const month = selectedDate.getMonth();

    return paymentEvents.filter((payment) => {
      return (
        payment.date.getFullYear() === year &&
        payment.date.getMonth() === month
      );
    });
  }, [paymentEvents, selectedDate]);

  // Get calendar days for selected month
  const calendarDays = useMemo(() => {
    const year = selectedDate.getFullYear();
    const month = selectedDate.getMonth();

    // First day of month
    const firstDay = new Date(year, month, 1);
    const firstDayOfWeek = firstDay.getDay(); // 0 = Sunday, 6 = Saturday

    // Last day of month
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();

    // Create calendar grid (7 days × 6 weeks max)
    const days: Array<{
      date: number | null;
      payments: PaymentEvent[];
      isCurrentMonth: boolean;
      isToday: boolean;
    }> = [];

    // Add empty cells for days before month starts
    for (let i = 0; i < firstDayOfWeek; i++) {
      days.push({
        date: null,
        payments: [],
        isCurrentMonth: false,
        isToday: false,
      });
    }

    // Add days of month
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    for (let day = 1; day <= daysInMonth; day++) {
      const date = new Date(year, month, day);
      const dayPayments = selectedMonthPayments.filter((payment) => {
        const paymentDate = new Date(payment.date);
        paymentDate.setHours(0, 0, 0, 0);
        return paymentDate.getTime() === date.getTime();
      });

      days.push({
        date: day,
        payments: dayPayments,
        isCurrentMonth: true,
        isToday: date.getTime() === today.getTime(),
      });
    }

    return days;
  }, [selectedDate, selectedMonthPayments]);

  // Navigate months
  const handlePreviousMonth = () => {
    setSelectedDate((prev) => {
      const newDate = new Date(prev);
      newDate.setMonth(prev.getMonth() - 1);
      return newDate;
    });
  };

  const handleNextMonth = () => {
    setSelectedDate((prev) => {
      const newDate = new Date(prev);
      newDate.setMonth(prev.getMonth() + 1);
      return newDate;
    });
  };

  // Select month from overview table
  const handleMonthSelect = (year: number, month: number) => {
    setSelectedDate(new Date(year, month, 1));
  };

  // Format month name in Russian
  const formatMonthName = (year: number, month: number): string => {
    const date = new Date(year, month, 1);
    return date.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' });
  };

  // Get current month summary
  const currentMonthSummary = useMemo(() => {
    const year = selectedDate.getFullYear();
    const month = selectedDate.getMonth();
    return monthSummaries.find((s) => s.year === year && s.month === month);
  }, [monthSummaries, selectedDate]);

  // Weekday names (Russian, short)
  const weekdayNames = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];

  if (portfolioBonds.length === 0) {
    return null; // Don't show calendar if portfolio is empty
  }

  return (
    <Box sx={{ p: 3 }}>
      {isLoading && (
        <Box sx={{ py: 4, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            Загрузка данных о выплатах...
          </Typography>
        </Box>
      )}

      {error && (
        <Box sx={{ py: 2 }}>
          <Typography variant="body2" color="error">
            {error}
          </Typography>
        </Box>
      )}

      {!isLoading && !error && (
        <Box
          sx={{
            display: 'flex',
            flexDirection: isMobile ? 'column' : 'row',
            gap: 3,
          }}
        >
          {/* Left side: Monthly overview - modern List design */}
          {!isMobile && (
            <Card
              sx={{
                width: '30%',
                minWidth: '280px',
                borderRadius: '16px',
                border: '1px solid rgba(0,0,0,0.08)',
                boxShadow: 2,
                bgcolor: 'background.paper',
                height: 'fit-content',
                maxHeight: '600px',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
              }}
            >
              <Box sx={{ p: 2, pb: 1.5 }}>
                <Typography
                  variant="subtitle2"
                  sx={{
                    fontWeight: 600,
                    color: 'text.secondary',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    fontSize: '0.75rem',
                  }}
                >
                  Обзор
                </Typography>
              </Box>
              <Divider />
              <List
                sx={{
                  overflowY: 'auto',
                  flexGrow: 1,
                  py: 0,
                }}
              >
                {monthSummaries.length === 0 ? (
                  <ListItem>
                    <ListItemText
                      primary={
                        <Typography variant="body2" color="text.secondary" align="center">
                          Нет данных о выплатах
                        </Typography>
                      }
                    />
                  </ListItem>
                ) : (
                  monthSummaries.map((summary, index) => {
                    const isSelected =
                      summary.year === selectedDate.getFullYear() &&
                      summary.month === selectedDate.getMonth();

                    return (
                      <React.Fragment key={`${summary.year}-${summary.month}`}>
                        <ListItem
                          onClick={() =>
                            handleMonthSelect(summary.year, summary.month)
                          }
                          sx={{
                            cursor: 'pointer',
                            backgroundColor: isSelected
                              ? alpha(muiTheme.palette.primary.main, 0.08)
                              : 'transparent',
                            '&:hover': {
                              backgroundColor: isSelected
                                ? alpha(muiTheme.palette.primary.main, 0.12)
                                : 'rgba(0, 0, 0, 0.04)',
                            },
                            transition: 'background-color 0.2s ease-in-out',
                            py: 1.5,
                          }}
                        >
                          <ListItemText
                            primary={
                              <Typography
                                variant="body2"
                                sx={{
                                  fontWeight: isSelected ? 600 : 400,
                                  color: isSelected ? 'primary.main' : 'text.primary',
                                }}
                              >
                                {formatMonthName(summary.year, summary.month)}
                              </Typography>
                            }
                            secondary={
                              <Typography
                                variant="body2"
                                sx={{
                                  fontWeight: 600,
                                  color: 'text.primary',
                                  mt: 0.5,
                                }}
                              >
                                {formatNumber(summary.totalAmount, 0)} {summary.currency}
                              </Typography>
                            }
                          />
                        </ListItem>
                        {index < monthSummaries.length - 1 && <Divider component="li" />}
                      </React.Fragment>
                    );
                  })
                )}
              </List>
            </Card>
          )}

          {/* Right side: Calendar */}
          <Card
            sx={{
              flex: 1,
              minWidth: 0,
              width: isMobile ? '100%' : 'auto',
              borderRadius: '16px',
              border: '1px solid rgba(0,0,0,0.08)',
              boxShadow: 2,
              bgcolor: 'background.paper',
              overflow: 'hidden',
              transition: 'box-shadow 0.2s ease-in-out',
              '&:hover': {
                boxShadow: 4,
              },
            }}
          >
            <Box sx={{ p: 2 }}>
              {/* Calendar header with navigation */}
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  mb: 2,
                }}
              >
                <IconButton
                  onClick={handlePreviousMonth}
                  size="small"
                  sx={{
                    color: 'text.secondary',
                    '&:hover': {
                      backgroundColor: 'rgba(0, 0, 0, 0.04)',
                    },
                  }}
                >
                  <ChevronLeftIcon />
                </IconButton>
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 600,
                    color: 'text.primary',
                  }}
                >
                  {formatMonthName(
                    selectedDate.getFullYear(),
                    selectedDate.getMonth()
                  )}
                </Typography>
                <IconButton
                  onClick={handleNextMonth}
                  size="small"
                  sx={{
                    color: 'text.secondary',
                    '&:hover': {
                      backgroundColor: 'rgba(0, 0, 0, 0.04)',
                    },
                  }}
                >
                  <ChevronRightIcon />
                </IconButton>
              </Box>

              {/* Calendar grid */}
              <Box
                sx={{
                  border: '1px solid rgba(0,0,0,0.08)',
                  borderRadius: '12px',
                  overflow: 'hidden',
                  bgcolor: 'background.paper',
                }}
              >
                {/* Weekday headers */}
                <Box
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(7, 1fr)',
                    borderBottom: '1px solid rgba(0,0,0,0.08)',
                    backgroundColor: 'rgba(0, 0, 0, 0.02)',
                  }}
                >
                  {weekdayNames.map((day) => (
                    <Box
                      key={day}
                      sx={{
                        p: 1,
                        textAlign: 'center',
                        fontWeight: 600,
                        fontSize: '0.875rem',
                        color: 'text.secondary',
                        borderRight: '1px solid rgba(0,0,0,0.08)',
                        '&:last-child': {
                          borderRight: 'none',
                        },
                      }}
                    >
                      {day}
                    </Box>
                  ))}
                </Box>

                {/* Calendar days */}
                <Box
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(7, 1fr)',
                    bgcolor: 'background.paper',
                  }}
                >
                  {calendarDays.map((day, index) => (
                    <Box
                      key={index}
                      sx={{
                        minHeight: '100px',
                        borderRight: '1px solid rgba(0,0,0,0.08)',
                        borderBottom: '1px solid rgba(0,0,0,0.08)',
                        p: 1,
                        backgroundColor: day.isCurrentMonth
                          ? 'background.paper'
                          : 'rgba(0, 0, 0, 0.02)',
                        position: 'relative',
                        ...(day.isToday && {
                          border: '2px solid',
                          borderColor: 'primary.main',
                          borderRadius: '4px',
                          zIndex: 1,
                        }),
                        '&:nth-of-type(7n)': {
                          borderRight: 'none',
                        },
                      }}
                    >
                      {day.date !== null && (
                        <>
                          {/* Day number */}
                          <Typography
                            variant="caption"
                            sx={{
                              display: 'block',
                              fontWeight: day.isToday ? 700 : 500,
                              color: day.isCurrentMonth
                                ? 'text.primary'
                                : 'text.disabled',
                              mb: 1,
                            }}
                          >
                            {day.date}
                          </Typography>

                          {/* Payments list - using Chips */}
                          <Box
                            sx={{
                              display: 'flex',
                              flexDirection: 'column',
                              gap: 0.5,
                            }}
                          >
                            {day.payments.map((payment, paymentIndex) => (
                              <Chip
                                key={paymentIndex}
                                label={`${payment.bondShortName}: ${formatNumber(
                                  payment.amount,
                                  0
                                )} ${payment.currency}${payment.type === 'maturity' ? ' (погашение)' : ''}`}
                                size="small"
                                sx={{
                                  height: 'auto',
                                  py: 0.5,
                                  fontSize: '0.7rem',
                                  fontWeight: 500,
                                  backgroundColor: payment.type === 'maturity'
                                    ? alpha(muiTheme.palette.warning.main, 0.15)
                                    : alpha(muiTheme.palette.primary.main, 0.15),
                                  color: payment.type === 'maturity'
                                    ? 'warning.dark'
                                    : 'primary.dark',
                                  '& .MuiChip-label': {
                                    px: 1,
                                    whiteSpace: 'normal',
                                    overflow: 'visible',
                                    textOverflow: 'clip',
                                    display: 'block',
                                    lineHeight: 1.3,
                                  },
                                }}
                                title={`${payment.bondShortName}: ${formatNumber(
                                  payment.amount,
                                  0
                                )} ${payment.currency}`}
                              />
                            ))}
                          </Box>
                        </>
                      )}
                    </Box>
                  ))}
                </Box>
              </Box>

              {/* Summary for selected month */}
              {currentMonthSummary && (
                <Box
                  sx={{
                    mt: 2,
                    p: 2,
                    backgroundColor: 'rgba(0, 0, 0, 0.02)',
                    borderRadius: '12px',
                    border: '1px solid rgba(0,0,0,0.08)',
                  }}
                >
                  <Typography variant="body2" color="text.secondary">
                    Всего выплат в {formatMonthName(
                      currentMonthSummary.year,
                      currentMonthSummary.month
                    )}:{' '}
                    <Typography
                      component="span"
                      sx={{ fontWeight: 600, color: 'text.primary' }}
                    >
                      {formatNumber(
                        currentMonthSummary.totalAmount,
                        0
                      )}{' '}
                      {currentMonthSummary.currency}
                    </Typography>
                  </Typography>
                </Box>
              )}
            </Box>
          </Card>
        </Box>
      )}
    </Box>
  );
};

