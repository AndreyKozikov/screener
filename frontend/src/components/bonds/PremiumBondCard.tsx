import React, { useMemo, useEffect, useState } from 'react';
import {
  Paper,
  Box,
  Typography,
  Chip,
  Grid,
  Stack,
  LinearProgress,
  Tooltip,
  Card,
  CardContent,
} from '@mui/material';
import {
  Notifications as NotificationsIcon,
  SwapHoriz as SwapHorizIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import type { BondDetail as BondDetailType } from '../../types/bond';
import { getEmitentBySecid, type EmitentInfo } from '../../api/emitent';
import {
  formatDate,
  formatNumber,
  formatPercent,
  formatBondStatus,
} from '../../utils/formatters';

interface PremiumBondCardProps {
  bondDetail: BondDetailType;
  couponType?: string | null;  // FIX or FLOAT
}

/**
 * Premium Bond Card Component
 * 
 * Displays a premium, compact card with key bond information
 * including identification, key metrics, coupon info, volume, and rating
 */
export const PremiumBondCard: React.FC<PremiumBondCardProps> = ({ bondDetail, couponType: couponTypeProp }) => {
  const securities = bondDetail?.securities;
  const market = bondDetail?.marketdata;
  const [emitentInfo, setEmitentInfo] = useState<EmitentInfo | null>(null);

  // Fetch emitent info
  useEffect(() => {
    const secid = typeof securities?.SECID === 'string' ? securities.SECID : null;
    if (!secid) return;

    let isCancelled = false;

    const loadEmitent = async () => {
      try {
        const info = await getEmitentBySecid(secid);
        if (!isCancelled) {
          setEmitentInfo(info);
        }
      } catch (error) {
        // Silently fail - emitent info is optional
        console.debug('Failed to load emitent info:', error);
      }
    };

    void loadEmitent();

    return () => {
      isCancelled = true;
    };
  }, [securities?.SECID]);

  // Extract key values
  const shortName = typeof securities?.SHORTNAME === 'string' ? securities.SHORTNAME : null;
  const secName = typeof securities?.SECNAME === 'string' ? securities.SECNAME : null;
  const isin = typeof securities?.ISIN === 'string' ? securities.ISIN : null;
  const regNumber = typeof securities?.REGNUMBER === 'string' ? securities.REGNUMBER : null;
  const status = typeof securities?.STATUS === 'string' ? securities.STATUS : null;
  const isActive = status === 'A';

  // Price - prefer PREVPRICE, fallback to PREVWAPRICE or LAST
  const price = useMemo(() => {
    const prevPrice = typeof securities?.PREVPRICE === 'number' ? securities.PREVPRICE : null;
    const prevWaprice = typeof securities?.PREVWAPRICE === 'number' ? securities.PREVWAPRICE : null;
    const last = market && typeof market.LAST === 'number' ? market.LAST : null;
    return prevPrice ?? prevWaprice ?? last;
  }, [securities, market]);

  // Yield
  const yieldValue = useMemo(() => {
    const yieldAtPrevWaprice = typeof securities?.YIELDATPREVWAPRICE === 'number' 
      ? securities.YIELDATPREVWAPRICE 
      : null;
    const marketYield = market && typeof market.YIELD === 'number' ? market.YIELD : null;
    return yieldAtPrevWaprice ?? marketYield;
  }, [securities, market]);

  // Accrued interest
  const accruedInt = typeof securities?.ACCRUEDINT === 'number' ? securities.ACCRUEDINT : null;

  // Maturity date
  const matDate = typeof securities?.MATDATE === 'string' ? securities.MATDATE : null;

  // Face value
  const faceValue = typeof securities?.FACEVALUE === 'number' ? securities.FACEVALUE : null;

  // Lot size
  const lotSize = typeof securities?.LOTSIZE === 'number' ? securities.LOTSIZE : null;
  const lotValue = useMemo(() => {
    if (lotSize !== null && faceValue !== null) {
      return lotSize * faceValue;
    }
    // Try LOTVALUE if available
    if (typeof securities?.LOTVALUE === 'number') {
      return securities.LOTVALUE;
    }
    return null;
  }, [lotSize, faceValue, securities]);

  // Coupon info
  const couponPercent = typeof securities?.COUPONPERCENT === 'number' ? securities.COUPONPERCENT : null;
  const couponValue = typeof securities?.COUPONVALUE === 'number' ? securities.COUPONVALUE : null;
  const nextCoupon = typeof securities?.NEXTCOUPON === 'string' ? securities.NEXTCOUPON : null;
  const couponPeriod = typeof securities?.COUPONPERIOD === 'number' ? securities.COUPONPERIOD : null;
  const couponType = couponTypeProp ?? null;

  // Volume and issue
  const faceUnit = typeof securities?.FACEUNIT === 'string' ? securities.FACEUNIT : null;

  // Risk indicators
  const offerDate = typeof securities?.OFFERDATE === 'string' ? securities.OFFERDATE : null;
  const callOptionDate = typeof securities?.CALLOPTIONDATE === 'string' ? securities.CALLOPTIONDATE : null;
  const putOptionDate = typeof securities?.PUTOPTIONDATE === 'string' ? securities.PUTOPTIONDATE : null;

  // Rating (may not be in detail, try to get from securities)
  const ratingAgency = securities?.RATING_AGENCY != null 
    ? String(securities.RATING_AGENCY) 
    : null;
  const ratingLevel = securities?.RATING_LEVEL != null 
    ? String(securities.RATING_LEVEL) 
    : null;

  // Calculate coupon progress
  const couponProgress = useMemo(() => {
    if (!nextCoupon || !couponPeriod) return null;

    try {
      const today = new Date();
      const nextCouponDate = new Date(nextCoupon);
      if (isNaN(nextCouponDate.getTime())) return null;

      // Find previous coupon date (nextCoupon - couponPeriod)
      const prevCouponDate = new Date(nextCouponDate);
      prevCouponDate.setDate(prevCouponDate.getDate() - couponPeriod);

      const totalDays = couponPeriod;
      const daysPassed = Math.floor((today.getTime() - prevCouponDate.getTime()) / (1000 * 60 * 60 * 24));
      const daysRemaining = Math.max(0, Math.floor((nextCouponDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24)));

      const progress = Math.min(100, Math.max(0, (daysPassed / totalDays) * 100));

      return {
        progress,
        daysRemaining,
        daysPassed,
        totalDays,
      };
    } catch {
      return null;
    }
  }, [nextCoupon, couponPeriod]);

  // Format currency symbol
  const getCurrencySymbol = (unit: string | null): string => {
    if (!unit) return '₽';
    const unitUpper = unit.toUpperCase();
    if (unitUpper === 'SUR' || unitUpper === 'RUB') return '₽';
    if (unitUpper === 'USD') return '$';
    if (unitUpper === 'EUR') return '€';
    return unit;
  };

  // Format bond type (for future use)
  // const formatBondType = (type: string | null): string => {
  //   if (!type) return '—';
  //   // SECTYPE 8 = биржевая облигация
  //   if (type === '8') return 'Биржевая облигация';
  //   return type;
  // };

  // Format days remaining text
  const formatDaysRemaining = (days: number): string => {
    if (days === 0) return 'сегодня';
    if (days === 1) return '1 день';
    if (days >= 2 && days <= 4) return `${days} дня`;
    if (days >= 5 && days <= 20) return `${days} дней`;
    const lastDigit = days % 10;
    if (lastDigit === 1) return `${days} день`;
    if (lastDigit >= 2 && lastDigit <= 4) return `${days} дня`;
    return `${days} дней`;
  };

  // Format coupon type
  const formatCouponType = (type: string | null): string => {
    if (!type) return '—';
    const typeUpper = type.toUpperCase();
    if (typeUpper === 'FIX') return 'Постоянный';
    if (typeUpper === 'FLOAT') return 'Плавающий';
    return type;
  };

  const currencySymbol = getCurrencySymbol(faceUnit);

  return (
    <Paper
      elevation={2}
      sx={{
        p: 3,
        borderRadius: 2,
        bgcolor: 'background.paper',
        border: '1px solid',
        borderColor: 'divider',
      }}
    >
      {/* 1. Верхний блок (идентификация + статус) */}
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
          <Box sx={{ flex: 1 }}>
            <Stack spacing={1}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.5 }}>
                <Typography variant="h5" fontWeight={700}>
                  {shortName || '—'}
                </Typography>
                <Chip
                  label={isActive ? 'Активна' : 'Не торгуется'}
                  color={isActive ? 'success' : 'default'}
                  size="small"
                />
              </Box>
              {secName && secName !== shortName && (
                <Typography variant="body2" color="text.secondary">
                  {secName}
                </Typography>
              )}
              <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ gap: 1 }}>
                {isin && (
                  <Typography variant="body2" color="text.secondary">
                    ISIN {isin}
                  </Typography>
                )}
                {regNumber && (
                  <Typography variant="body2" color="text.secondary">
                    Рег. № {regNumber}
                  </Typography>
                )}
              </Stack>
              {emitentInfo?.emitent_title && (
                <Typography variant="body2" color="text.secondary">
                  Эмитент: {emitentInfo.emitent_title}
                </Typography>
              )}
            </Stack>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 3.3 }}>
            {/* Карточка рейтинга */}
            <Card
              elevation={0}
              sx={{
                minWidth: 150,
                minHeight: 70,
                bgcolor: 'grey.50',
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
              }}
            >
              <CardContent sx={{ p: 2, textAlign: 'center', '&:last-child': { pb: 2 } }}>
                <Typography variant="caption" color="text.secondary" display="block" gutterBottom sx={{ mb: 0.5 }}>
                  Рейтинг
                </Typography>
                <Typography variant="body2" fontWeight={600} sx={{ textAlign: 'center' }}>
                  {ratingLevel || '—'}
                  {ratingLevel && ratingAgency && (
                    <Typography component="span" variant="caption" color="text.secondary" display="block" sx={{ mt: 0.25 }}>
                      ({ratingAgency})
                    </Typography>
                  )}
                </Typography>
              </CardContent>
            </Card>
          </Box>
        </Box>
      </Box>

      {/* 2. Основной инфоблок с ключевыми метриками */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 4 }}>
          <Card
            elevation={0}
            sx={{
              bgcolor: 'grey.50',
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
            }}
          >
            <CardContent sx={{ p: 1.5, textAlign: 'center', '&:last-child': { pb: 1.5 } }}>
              <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
                Цена
              </Typography>
              <Typography variant="h6" fontWeight={700} color="primary">
                {price !== null ? formatNumber(price, 2) : '—'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 4 }}>
          <Card
            elevation={0}
            sx={{
              bgcolor: 'grey.50',
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
            }}
          >
            <CardContent sx={{ p: 1.5, textAlign: 'center', '&:last-child': { pb: 1.5 } }}>
              <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
                Доходность
              </Typography>
              <Typography variant="h6" fontWeight={700} color="primary">
                {yieldValue !== null ? formatPercent(yieldValue, 2) : '—'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 4 }}>
          <Card
            elevation={0}
            sx={{
              bgcolor: 'grey.50',
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
            }}
          >
            <CardContent sx={{ p: 1.5, textAlign: 'center', '&:last-child': { pb: 1.5 } }}>
              <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
                НКД
              </Typography>
              <Typography variant="h6" fontWeight={700} color="primary">
                {accruedInt !== null ? formatNumber(accruedInt, 2) : '—'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 4 }}>
          <Card
            elevation={0}
            sx={{
              bgcolor: 'grey.50',
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
            }}
          >
            <CardContent sx={{ p: 1.5, textAlign: 'center', '&:last-child': { pb: 1.5 } }}>
              <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
                Погашение
              </Typography>
              <Typography variant="body2" fontWeight={600}>
                {matDate ? formatDate(matDate) : '—'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 4 }}>
          <Card
            elevation={0}
            sx={{
              bgcolor: 'grey.50',
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
            }}
          >
            <CardContent sx={{ p: 1.5, textAlign: 'center', '&:last-child': { pb: 1.5 } }}>
              <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
                Номинал
              </Typography>
              <Typography variant="body2" fontWeight={600}>
                {faceValue !== null ? `${formatNumber(faceValue, 0)} ${currencySymbol}` : '—'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 4 }}>
          <Card
            elevation={0}
            sx={{
              bgcolor: 'grey.50',
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
            }}
          >
            <CardContent sx={{ p: 1.5, textAlign: 'center', '&:last-child': { pb: 1.5 } }}>
              <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
                Лот
              </Typography>
              <Typography variant="body2" fontWeight={600}>
                {lotValue !== null ? `${formatNumber(lotValue, 0)} ${currencySymbol}` : '—'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* 3. Купонный блок */}
      <Card
        elevation={0}
        sx={{
          mb: 3,
          bgcolor: 'grey.50',
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1,
        }}
      >
        <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Grid container spacing={2}>
          <Grid size={{ xs: 6 }} sx={{ textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Купонная ставка
            </Typography>
            <Typography variant="body1" fontWeight={600}>
              {couponPercent !== null ? formatPercent(couponPercent, 2) : '—'}
            </Typography>
          </Grid>
          <Grid size={{ xs: 6 }} sx={{ textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Сумма купона
            </Typography>
            <Typography variant="body1" fontWeight={600}>
              {couponValue !== null ? `${formatNumber(couponValue, 2)} ${currencySymbol}` : '—'}
            </Typography>
          </Grid>
          <Grid size={{ xs: 6 }} sx={{ textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Ближайшая выплата
            </Typography>
            <Typography variant="body1" fontWeight={600}>
              {nextCoupon ? formatDate(nextCoupon) : '—'}
            </Typography>
          </Grid>
          <Grid size={{ xs: 6 }} sx={{ textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Периодичность
            </Typography>
            <Typography variant="body1" fontWeight={600}>
              {couponPeriod !== null ? `${couponPeriod} дней` : '—'}
            </Typography>
          </Grid>
          <Grid size={{ xs: 6 }} sx={{ textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Тип купона
            </Typography>
            <Typography variant="body1" fontWeight={600}>
              {formatCouponType(couponType)}
            </Typography>
          </Grid>
          {couponProgress && (
            <Grid size={{ xs: 12 }}>
              <Box sx={{ mt: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                  <Typography variant="caption" color="text.secondary">
                    До следующего купона осталось {couponProgress.daysRemaining > 0
                      ? formatDaysRemaining(couponProgress.daysRemaining)
                      : 'сегодня'}
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={couponProgress.progress}
                  sx={{ height: 6, borderRadius: 1 }}
                />
              </Box>
            </Grid>
          )}
        </Grid>
      </CardContent>
      </Card>

      {/* 5. Индикаторы риска */}
      {(offerDate || callOptionDate || putOptionDate || !isActive) && (
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {offerDate && (
            <Tooltip title={`Оферта: ${formatDate(offerDate)}`} arrow>
              <Chip
                icon={<NotificationsIcon fontSize="small" />}
                label="Оферта"
                size="small"
                color="warning"
                variant="outlined"
              />
            </Tooltip>
          )}
          {(callOptionDate || putOptionDate) && (
            <Tooltip
              title={`Досрочное погашение: ${callOptionDate ? formatDate(callOptionDate) : formatDate(putOptionDate || '')}`}
              arrow
            >
              <Chip
                icon={<SwapHorizIcon fontSize="small" />}
                label="Досрочное погашение"
                size="small"
                color="info"
                variant="outlined"
              />
            </Tooltip>
          )}
          {!isActive && (
            <Tooltip title={`Статус: ${formatBondStatus(status)}`} arrow>
              <Chip
                icon={<WarningIcon fontSize="small" />}
                label="Неактивна"
                size="small"
                color="error"
                variant="outlined"
              />
            </Tooltip>
          )}
        </Box>
      )}
    </Paper>
  );
};

