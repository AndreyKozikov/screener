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
  Link,
} from '@mui/material';
import {
  Notifications as NotificationsIcon,
  SwapHoriz as SwapHorizIcon,
  Warning as WarningIcon,
  OpenInNew as OpenInNewIcon,
  Chat as ChatIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { BondChat } from './BondChat';
import { runLlmPromptPipeline } from '../../api/llm';
import { useUiStore } from '../../stores/uiStore';
import type { BondDetail as BondDetailType } from '../../types/bond';
import { getEmitentBySecid, type EmitentInfo } from '../../api/emitent';
import {
  formatDate,
  formatNumber,
  formatPercent,
  formatBondStatus,
} from '../../utils/formatters';
import { getWorstRating, getRatingLevel, getRatingAgency, type Rating } from '../../utils/ratings';
import { getRatingColor } from './BondsTable';

interface PremiumBondCardProps {
  bondDetail: BondDetailType;
}

/**
 * Premium Bond Card Component
 * 
 * Displays a premium, compact card with key bond information
 * including identification, key metrics, coupon info, volume, and rating
 */
export const PremiumBondCard: React.FC<PremiumBondCardProps> = ({ bondDetail }) => {
  const securities = bondDetail?.securities;
  const market = bondDetail?.marketdata;
  const [emitentInfo, setEmitentInfo] = useState<EmitentInfo | null>(null);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [isUpdatingParams, setIsUpdatingParams] = useState(false);
  const { triggerDataRefresh } = useUiStore();
  
  // Fetch emitent info with ratings
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
  const secid = typeof securities?.SECID === 'string' ? securities.SECID : null;
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

  // Volume and issue
  const faceUnit = typeof securities?.FACEUNIT === 'string' ? securities.FACEUNIT : null;

  // Risk indicators
  const offerDate = typeof securities?.OFFERDATE === 'string' ? securities.OFFERDATE : null;
  const callOptionDate = typeof securities?.CALLOPTIONDATE === 'string' ? securities.CALLOPTIONDATE : null;
  const putOptionDate = typeof securities?.PUTOPTIONDATE === 'string' ? securities.PUTOPTIONDATE : null;
  const hasAmort = typeof securities?.BONDTYPE43 === 'string' && securities.BONDTYPE43 === 'Амортизируемые облигации';

  // Rating - get from bond ratings or emitent ratings
  const bondRatings = useMemo(() => {
    const ratings = securities?.RATINGS;
    if (Array.isArray(ratings) && ratings.length > 0) {
      return ratings as Rating[];
    }
    // Fallback: if RATING_LEVEL exists but RATINGS doesn't, create a rating object
    if (securities?.RATING_LEVEL && securities?.RATING_AGENCY) {
      return [{
        rating_level_name_short_ru: String(securities.RATING_LEVEL),
        agency_name_short_ru: String(securities.RATING_AGENCY),
      }];
    }
    return null;
  }, [securities?.RATINGS, securities?.RATING_LEVEL, securities?.RATING_AGENCY]);

  const worstBondRating = useMemo(() => {
    if (!bondRatings) return null;
    return getWorstRating(bondRatings);
  }, [bondRatings]);

  const worstEmitentRating = useMemo(() => {
    if (!emitentInfo?.cci_rating_companies || emitentInfo.cci_rating_companies.length === 0) return null;
    return getWorstRating(emitentInfo.cci_rating_companies);
  }, [emitentInfo?.cci_rating_companies]);

  // Select final rating: bond rating first, then emitent rating
  const finalRating = worstBondRating || worstEmitentRating;
  const ratingLevel = getRatingLevel(finalRating);
  const ratingAgency = getRatingAgency(finalRating);

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

  const currencySymbol = getCurrencySymbol(faceUnit);

  const handleUpdateParams = async () => {
    if (!secid || isUpdatingParams) return;
    
    try {
      setIsUpdatingParams(true);
      await runLlmPromptPipeline(secid);
      triggerDataRefresh();
      // Можно добавить уведомление об успехе, если в проекте есть Snackbar
      alert(`Параметры для ${secid} успешно обновлены`);
    } catch (error) {
      console.error('Failed to update bond parameters:', error);
      alert('Ошибка при обновлении параметров');
    } finally {
      setIsUpdatingParams(false);
    }
  };

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
                {secid ? (
                  <Link
                    href={`https://www.moex.com/ru/issue.aspx?board=TQCB&code=${secid}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    sx={{
                      textDecoration: 'none',
                      color: 'primary.main',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.5,
                      '&:hover': {
                        textDecoration: 'underline',
                        color: 'primary.dark',
                      },
                      '&:visited': {
                        color: 'primary.main',
                      },
                    }}
                  >
                    <OpenInNewIcon sx={{ fontSize: 20 }} />
                    <Typography variant="h5" fontWeight={700} component="span">
                      {shortName || '—'}
                    </Typography>
                  </Link>
                ) : (
                  <Typography variant="h5" fontWeight={700}>
                    {shortName || '—'}
                  </Typography>
                )}
                <Chip
                  label={isActive ? 'Активна' : 'Не торгуется'}
                  color={isActive ? 'success' : 'default'}
                  size="small"
                />
                <Chip
                  icon={<ChatIcon sx={{ fontSize: '16px !important' }} />}
                  label="Чат с ИИ"
                  color="primary"
                  variant="filled"
                  size="small"
                  onClick={() => setIsChatOpen(true)}
                  sx={{ 
                    cursor: 'pointer',
                    fontWeight: 600,
                    '&:hover': {
                      bgcolor: 'primary.dark',
                    },
                    pl: 0.5
                  }}
                />
                <Chip
                  icon={<RefreshIcon sx={{ fontSize: '16px !important' }} />}
                  label={isUpdatingParams ? "Обновление..." : "Обновить параметры"}
                  color="secondary"
                  variant="filled"
                  size="small"
                  onClick={handleUpdateParams}
                  disabled={isUpdatingParams}
                  sx={{
                    cursor: isUpdatingParams ? 'default' : 'pointer',
                    fontWeight: 600,
                    '&:hover': {
                      bgcolor: 'secondary.dark',
                    },
                    pl: 0.5
                  }}
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
              {(bondDetail?.emitent_inn ?? emitentInfo?.emitent_inn) && (
                <Typography variant="body2" color="text.secondary">
                  ИНН: {bondDetail?.emitent_inn ?? emitentInfo?.emitent_inn}
                </Typography>
              )}
            </Stack>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 3.3, mt: 4 }}>
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
                {ratingLevel ? (
                  <Box>
                    <Box
                      sx={{
                        px: 1.5,
                        py: 0.75,
                        borderRadius: '6px',
                        fontSize: '14px',
                        backgroundColor: getRatingColor(ratingLevel).bg,
                        color: getRatingColor(ratingLevel).color,
                        fontWeight: 600,
                        display: 'inline-block',
                        textAlign: 'center',
                        minWidth: '60px',
                        mb: 0.5,
                      }}
                    >
                      {ratingLevel}
                    </Box>
                    {ratingAgency && (
                      <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                        ({ratingAgency})
                      </Typography>
                    )}
                  </Box>
                ) : (
                  <Typography variant="body2" fontWeight={600} sx={{ textAlign: 'center' }}>
                    —
                  </Typography>
                )}
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
      {(offerDate || callOptionDate || putOptionDate || hasAmort || !isActive) && (
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
          {hasAmort && (
            <Chip
              label="С амортизацией долга"
              size="small"
              color="secondary"
              variant="outlined"
            />
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
      
      {secid && (
        <BondChat
          isOpen={isChatOpen}
          onClose={() => setIsChatOpen(false)}
          secid={secid}
          shortName={shortName || 'облигация'}
        />
      )}
    </Paper>
  );
};

