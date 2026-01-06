import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Typography,
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
import { getCurrencyRates, type CurrencyRatesResponse } from '../../api/currency';
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
 * Month summary data with amounts grouped by currency
 */
interface MonthSummary {
  year: number;
  month: number; // 0-11
  amountsByCurrency: { [currency: string]: number }; // Суммы по каждой валюте отдельно
  totalInRubles: number; // Итоговая сумма всех выплат в рублях
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
  const couponsBySecid = usePortfolioStore((state) => state.couponsBySecid);
  const muiTheme = useTheme();
  const isMobile = useMediaQuery(muiTheme.breakpoints.down('md'));

  // Current selected month (default: current month)
  const [selectedDate, setSelectedDate] = useState<Date>(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  // Currency rates for conversion to rubles
  const [currencyRates, setCurrencyRates] = useState<CurrencyRatesResponse | null>(null);

  // Calculate payment events from store data
  const paymentEvents = useMemo(() => {
    if (portfolioBonds.length === 0) {
      return [];
    }

    const allPayments: PaymentEvent[] = [];
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // Process all bonds in portfolio
    for (const bond of portfolioBonds) {
      const coupons = couponsBySecid[bond.SECID] || [];
      const bondPayments: PaymentEvent[] = [];

      // Process all coupons for this bond
      for (const coupon of coupons) {
        if (coupon.coupondate) {
          const couponDate = new Date(coupon.coupondate);
          couponDate.setHours(0, 0, 0, 0);

          // Only include future coupons
          if (couponDate >= today) {
            const quantity = bond.quantity || 1;
            const couponValue = coupon.value || 0;
            const totalAmount = couponValue * quantity;
            
            // Используем валюту из купона, если она есть, иначе из облигации
            const currency = coupon.faceunit || bond.FACEUNIT || 'RUB';

            bondPayments.push({
              date: couponDate,
              bondShortName: bond.SHORTNAME || bond.SECID,
              bondSecid: bond.SECID,
              amount: totalAmount,
              currency: currency,
              type: 'coupon',
            });
          }
        }
      }

      // Check for maturity date
      if (bond.MATDATE) {
        const matDate = new Date(bond.MATDATE);
        matDate.setHours(0, 0, 0, 0);

        // Only include future maturity
        if (matDate >= today) {
          const quantity = bond.quantity || 1;
          const faceValue = bond.FACEVALUE || 0;
          const totalAmount = faceValue * quantity;

          bondPayments.push({
            date: matDate,
            bondShortName: bond.SHORTNAME || bond.SECID,
            bondSecid: bond.SECID,
            amount: totalAmount,
            currency: bond.FACEUNIT || 'RUB',
            type: 'maturity',
          });
        }
      }

      allPayments.push(...bondPayments);
    }

    // Deduplicate payments by date, SECID, and type to avoid duplicates
    const paymentMap = new Map<string, PaymentEvent>();
    for (const payment of allPayments) {
      // Create unique key: date + SECID + type
      const dateStr = payment.date.toISOString().split('T')[0];
      const key = `${dateStr}-${payment.bondSecid}-${payment.type}`;
      
      if (paymentMap.has(key)) {
        // If duplicate found, sum the amounts
        const existing = paymentMap.get(key)!;
        existing.amount += payment.amount;
        // If bond names differ, combine them
        if (existing.bondShortName !== payment.bondShortName) {
          existing.bondShortName = `${existing.bondShortName}, ${payment.bondShortName}`;
        }
      } else {
        paymentMap.set(key, { ...payment });
      }
    }

    // Convert map back to array and sort by date
    const uniquePayments = Array.from(paymentMap.values());
    uniquePayments.sort((a, b) => a.date.getTime() - b.date.getTime());

    return uniquePayments;
  }, [portfolioBonds, couponsBySecid]);

  // Load currency rates
  useEffect(() => {
    const loadCurrencyRates = async () => {
      try {
        const rates = await getCurrencyRates();
        setCurrencyRates(rates);
      } catch (err) {
        console.error('Failed to load currency rates:', err);
        // Don't set error state - currency conversion is optional
      }
    };

    void loadCurrencyRates();
  }, []);

  // Helper function to convert amount to rubles
  const convertToRubles = (amount: number, currency: string): number => {
    if (currency === 'RUB') {
      return amount;
    }

    if (!currencyRates || !currencyRates.rates) {
      return 0; // Can't convert without rates
    }

    const rate = currencyRates.rates[currency];
    if (!rate) {
      return 0; // Unknown currency
    }

    // rate.rate is the exchange rate for rate.nominal units
    // So 1 unit of currency = rate.rate / rate.nominal rubles
    return amount * (rate.rate / rate.nominal);
  };

  // Calculate month summaries grouped by currency
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
          amountsByCurrency: {},
          totalInRubles: 0,
        });
      }

      const summary = summaries.get(key)!;
      const currency = payment.currency || 'RUB';
      
      // Sum amounts by currency separately
      if (!summary.amountsByCurrency[currency]) {
        summary.amountsByCurrency[currency] = 0;
      }
      summary.amountsByCurrency[currency] += payment.amount;

      // Add to total in rubles
      summary.totalInRubles += convertToRubles(payment.amount, currency);
    });

    // Convert to array and sort by date
    return Array.from(summaries.values()).sort((a, b) => {
      if (a.year !== b.year) return a.year - b.year;
      return a.month - b.month;
    });
  }, [paymentEvents, currencyRates]);

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
                              <Box sx={{ mt: 0.5 }}>
                                {Object.entries(summary.amountsByCurrency).map(([currency, amount]) => (
                                  <Typography
                                    key={currency}
                                    variant="body2"
                                    sx={{
                                      fontWeight: 600,
                                      color: 'text.primary',
                                    }}
                                  >
                                    {formatNumber(amount, 2)} {currency}
                                  </Typography>
                                ))}
                                {summary.totalInRubles > 0 && (
                                  <Typography
                                    variant="body2"
                                    sx={{
                                      fontWeight: 700,
                                      color: 'primary.main',
                                      mt: 0.5,
                                    }}
                                  >
                                    Итого: {formatNumber(summary.totalInRubles, 2)} RUB
                                  </Typography>
                                )}
                              </Box>
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
                                  2
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
                                  2
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
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    Всего выплат в {formatMonthName(
                      currentMonthSummary.year,
                      currentMonthSummary.month
                    )}:
                  </Typography>
                  {Object.entries(currentMonthSummary.amountsByCurrency).map(([currency, amount]) => (
                    <Typography
                      key={currency}
                      variant="body2"
                      sx={{
                        fontWeight: 600,
                        color: 'text.primary',
                        mb: 0.5,
                      }}
                    >
                      {formatNumber(amount, 2)} {currency}
                    </Typography>
                  ))}
                  {currentMonthSummary.totalInRubles > 0 && (
                    <Typography
                      variant="body2"
                      sx={{
                        fontWeight: 700,
                        color: 'primary.main',
                        mt: 1,
                        pt: 1,
                        borderTop: '1px solid rgba(0,0,0,0.1)',
                      }}
                    >
                      Итого: {formatNumber(currentMonthSummary.totalInRubles, 2)} RUB
                    </Typography>
                  )}
                </Box>
              )}
            </Box>
          </Card>
        </Box>
    </Box>
  );
};

