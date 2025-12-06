import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Drawer,
  Box,
  Typography,
  IconButton,
  Divider,
  Grid,
  Chip,
  Paper,
  Stack,
  Tooltip,
  Alert,
  Tabs,
  Tab,
  tabsClasses,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { useUiStore } from '../../stores/uiStore';
import { fetchBondDetail, fetchBondCoupons } from '../../api/bonds';

const { triggerDataRefresh } = useUiStore.getState();
import { fetchColumnMapping, fetchDescriptions } from '../../api/metadata';
import type { ColumnMapping } from '../../types/api';
import type { DescriptionsResponse } from '../../api/metadata';
import type { BondDetail as BondDetailType, BondFieldValue } from '../../types/bond';
import type { Coupon } from '../../types/coupon';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorMessage } from '../common/ErrorMessage';
import { CouponsTable } from './CouponsTable';
import { PremiumBondCard } from './PremiumBondCard';
import {
  formatDate,
  formatNumber,
  formatPercent,
  formatBondStatus,
  formatTradingStatus,
} from '../../utils/formatters';

type FieldDescriptionMap = Record<string, string>;

const isoDateRegex = /^\d{4}-\d{2}-\d{2}/;
const isoDateTimeRegex = /^\d{4}-\d{2}-\d{2}T\d{2}:/;
const numericPattern = /^-?\d+(?:[.,]\d+)?$/;
const percentKeywords = ['PERCENT', 'YIELD', 'RATE', 'SPREAD'];
const zeroDecimalKeywords = ['SIZE', 'VOLUME', 'COUNT', 'LOT', 'NUM', 'NUMBER', 'PERIOD', 'QUANTITY'];
const currencyKeywords = ['VALUE', 'PRICE', 'AMOUNT', 'SUM', 'CAPITAL', 'COST', 'VOLTODAY', 'VALTODAY', 'WAPRICE', 'LAST', 'BID', 'OFFER'];

const formatNumericValue = (fieldUpper: string, numericValue: number): string => {
  if (!Number.isFinite(numericValue)) {
    return '-';
  }

  if (percentKeywords.some((keyword) => fieldUpper.includes(keyword))) {
    return formatPercent(numericValue);
  }

  if (currencyKeywords.some((keyword) => fieldUpper.includes(keyword))) {
    return formatNumber(numericValue, 2);
  }

  if (zeroDecimalKeywords.some((keyword) => fieldUpper.includes(keyword))) {
    return formatNumber(numericValue, 0);
  }

  return formatNumber(numericValue, Math.abs(numericValue) < 1 ? 4 : 2);
};

const formatFieldValue = (field: string, rawValue: BondFieldValue): string => {
  if (rawValue === null || rawValue === undefined) {
    return '—';
  }

  if (Array.isArray(rawValue)) {
    const formatted = rawValue
      .map((value) => formatFieldValue(field, value as BondFieldValue))
      .filter((value) => value !== '—');

    return formatted.length > 0 ? formatted.join(', ') : '—';
  }

  if (typeof rawValue === 'boolean') {
    return rawValue ? 'Да' : 'Нет';
  }

  const fieldUpper = field.toUpperCase();

  if (typeof rawValue === 'number') {
    return formatNumericValue(fieldUpper, rawValue);
  }

  if (typeof rawValue === 'string') {
    const trimmed = rawValue.trim();

    if (trimmed.length === 0 || trimmed.toLowerCase() === 'nan') {
      return '—';
    }

    if (fieldUpper.includes('DATE') || isoDateRegex.test(trimmed) || isoDateTimeRegex.test(trimmed)) {
      return formatDate(trimmed);
    }

    if (numericPattern.test(trimmed)) {
      const parsed = Number(trimmed.replace(',', '.'));
      return formatNumericValue(fieldUpper, parsed);
    }

    return trimmed;
  }

  return String(rawValue);
};

const flattenDescriptions = (descriptions: DescriptionsResponse): FieldDescriptionMap => {
  const result: FieldDescriptionMap = {};

  Object.values(descriptions).forEach((section) => {
    if (section && typeof section === 'object' && !Array.isArray(section)) {
      Object.entries(section).forEach(([field, description]) => {
        if (typeof description === 'string' && description.trim().length > 0) {
          result[field] = description;
        }
      });
    }
  });

  return result;
};

/**
 * BondDetails Component
 * 
 * Drawer displaying detailed information about a selected bond
 * with optimized UX structure according to the specification
 */
export const BondDetails: React.FC = () => {
  const { selectedBondId, setSelectedBond, triggerDataRefresh } = useUiStore();
  const [bondDetail, setBondDetail] = useState<BondDetailType | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [columnMapping, setColumnMapping] = useState<ColumnMapping>({});
  const [fieldDescriptions, setFieldDescriptions] = useState<FieldDescriptionMap>({});
  const [isMetadataLoading, setIsMetadataLoading] = useState(false);
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const metadataLoadedRef = useRef(false);
  
  // Coupons state
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [couponType, setCouponType] = useState<string | null>(null);  // FIX or FLOAT
  const [isLoadingCoupons, setIsLoadingCoupons] = useState(false);
  const [couponsError, setCouponsError] = useState<string | null>(null);
  
  // Tab state
  const [activeTab, setActiveTab] = useState(0);
  
  // Track previous coupons count to detect when new data is loaded
  const prevCouponsCountRef = useRef(0);

  const collator = useMemo(() => new Intl.Collator('ru-RU'), []);
  const isOpen = Boolean(selectedBondId);

  useEffect(() => {
    if (!selectedBondId) {
      setBondDetail(null);
      setError(null);
      setCoupons([]);
      setCouponType(null);
      setCouponsError(null);
      setActiveTab(0);
      prevCouponsCountRef.current = 0;
      return;
    }

    let isCancelled = false;

    const loadDetails = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const details = await fetchBondDetail(selectedBondId);
        if (!isCancelled) {
          setBondDetail(details);
        }
      } catch (err: unknown) {
        if (!isCancelled) {
          setError(err instanceof Error ? err.message : 'Не удалось загрузить детали облигации');
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadDetails();

    return () => {
      isCancelled = true;
    };
  }, [selectedBondId]);

  // Load coupon_type when bond is selected (needed for "Основные данные" tab)
  useEffect(() => {
    if (!selectedBondId || couponType !== null) {
      return;
    }

    let isCancelled = false;
    const currentSecIdRef = selectedBondId;

    const loadCouponType = async () => {
      try {
        const response = await fetchBondCoupons(currentSecIdRef);
        if (!isCancelled && currentSecIdRef === selectedBondId) {
          setCouponType(response.coupon_type || null);
        }
      } catch (err) {
        // Silently fail - coupon_type is optional
        console.warn('Failed to load coupon_type:', err);
      }
    };

    void loadCouponType();

    return () => {
      isCancelled = true;
    };
  }, [selectedBondId, couponType]);

  // Load coupons when tab changes to "Купонные выплаты"
  useEffect(() => {
    // Find the index of "Купонные выплаты" tab (it should be after "Основные данные")
    // Based on the tab structure: 0 is "Основные данные", 1 is "Купонные выплаты"
    const couponsTabIndex = 1;
    
    if (!selectedBondId || activeTab !== couponsTabIndex) {
      return;
    }

    // Reset coupon count when switching bonds or opening tab
    const currentSecIdRef = selectedBondId;
    const hadCouponsBefore = prevCouponsCountRef.current > 0;
    prevCouponsCountRef.current = 0;

    // Only load if we don't have coupons already
    if (coupons.length > 0 && !couponsError) {
      if (!hadCouponsBefore) {
        setTimeout(() => {
          triggerDataRefresh();
        }, 300);
      }
      return;
    }

    let isCancelled = false;

    const loadCoupons = async () => {
      try {
        setIsLoadingCoupons(true);
        setCouponsError(null);
        const response = await fetchBondCoupons(currentSecIdRef);
        if (!isCancelled && currentSecIdRef === selectedBondId) {
          const hasCouponsNow = response.coupons.length > 0;
          setCoupons(response.coupons);
          setCouponType(response.coupon_type || null);
          
          if (hasCouponsNow) {
            prevCouponsCountRef.current = response.coupons.length;
            setTimeout(() => {
              if (currentSecIdRef === selectedBondId) {
                triggerDataRefresh();
              }
            }, 500);
          }
        }
      } catch (err: unknown) {
        if (!isCancelled && currentSecIdRef === selectedBondId) {
          setCouponsError(err instanceof Error ? err.message : 'Не удалось загрузить данные о купонах');
        }
      } finally {
        if (!isCancelled && currentSecIdRef === selectedBondId) {
          setIsLoadingCoupons(false);
        }
      }
    };

    void loadCoupons();

    return () => {
      isCancelled = true;
    };
  }, [selectedBondId, activeTab, coupons.length, couponsError, triggerDataRefresh]);

  useEffect(() => {
    if (!isOpen || metadataLoadedRef.current) {
      return;
    }

    let isCancelled = false;

    const loadMetadata = async () => {
      try {
        setIsMetadataLoading(true);
        setMetadataError(null);

        const [mapping, descriptionsResponse] = await Promise.all([
          fetchColumnMapping(),
          fetchDescriptions(),
        ]);

        if (isCancelled) {
          return;
        }

        setColumnMapping(mapping);
        setFieldDescriptions(flattenDescriptions(descriptionsResponse));
        metadataLoadedRef.current = true;
      } catch (err: unknown) {
        if (!isCancelled) {
          setMetadataError(err instanceof Error ? err.message : 'Не удалось загрузить описания полей');
        }
      } finally {
        if (!isCancelled) {
          setIsMetadataLoading(false);
        }
      }
    };

    void loadMetadata();

    return () => {
      isCancelled = true;
    };
  }, [isOpen]);

  const handleClose = () => {
    setSelectedBond(null);
  };

  const getFieldLabel = (field: string): string => columnMapping[field] ?? field;
  const getFieldDescription = (field: string): string | undefined => {
    const direct = fieldDescriptions[field];
    if (direct) {
      return direct;
    }

    if (field.endsWith('BP')) {
      const trimmed = field.slice(0, -2);
      return fieldDescriptions[trimmed];
    }

    return undefined;
  };

  // Helper function to render a field with label and value
  const renderField = (field: string, value: BondFieldValue, label?: string) => {
    const fieldLabel = label || getFieldLabel(field);
    const description = getFieldDescription(field);

    return (
      <React.Fragment key={field}>
        <Box sx={{ pr: 1, wordBreak: 'break-word', whiteSpace: 'normal' }}>
          <Typography
            variant="body2"
            fontWeight={600}
            component="span"
            sx={{ wordBreak: 'break-word', whiteSpace: 'normal' }}
          >
            {fieldLabel}
          </Typography>
          {description && (
            <Tooltip title={description} arrow>
              <Box
                component="span"
                sx={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  ml: 0.5,
                  verticalAlign: 'text-top',
                }}
              >
                <InfoOutlinedIcon fontSize="small" color="action" />
              </Box>
            </Tooltip>
          )}
        </Box>
        <Typography
          variant="body2"
          color="text.primary"
          sx={{ wordBreak: 'break-word', whiteSpace: 'normal' }}
        >
          {formatFieldValue(field, value)}
        </Typography>
      </React.Fragment>
    );
  };

  // Helper function to render a section with fields
  const renderSection = (title: string, fields: Array<{ field: string; value: BondFieldValue; label?: string }>) => {
    return (
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle1" fontWeight={600} gutterBottom sx={{ mb: 2 }}>
          {title}
        </Typography>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1.3fr) minmax(0, 1fr)',
            columnGap: 2,
            rowGap: 1.5,
            alignItems: 'start',
          }}
        >
          {fields.map(({ field, value, label }) => renderField(field, value, label))}
        </Box>
      </Box>
    );
  };

  // Get all data fields
  const getAllFields = useMemo(() => {
    if (!bondDetail) {
      return {};
    }

    const excludedFields = new Set([
      'IR', 'ICPI', 'BEI', 'BEICLOSE', 'CBR', 'CBRCLOSE', 'IRICPICLOSE',
      'SYSTIME', 'UPDATETIME', 'TIME', 'TRADEMOMENT',
      'BIDDEPTH', 'OFFERDEPTH',
    ]);

    const allFields: Record<string, BondFieldValue> = {};

    if (bondDetail.securities) {
      Object.entries(bondDetail.securities).forEach(([key, value]) => {
        if (!excludedFields.has(key)) {
          allFields[key] = value;
        }
      });
    }

    if (bondDetail.marketdata) {
      Object.entries(bondDetail.marketdata).forEach(([key, value]) => {
        if (!excludedFields.has(key)) {
          allFields[key] = value;
        }
      });
    }

    if (bondDetail.marketdata_yields && bondDetail.marketdata_yields.length > 0) {
      bondDetail.marketdata_yields.forEach((entry) => {
        Object.entries(entry).forEach(([key, value]) => {
          if (!excludedFields.has(key)) {
            allFields[key] = value;
          }
        });
      });
    }

    // Handle YIELDDATE vs BUYBACKDATE
    const yieldDate = allFields['YIELDDATE'];
    const buybackDate = allFields['BUYBACKDATE'];
    const hasYieldDate = yieldDate != null && yieldDate !== '' && yieldDate !== undefined;
    const hasBuybackDate = buybackDate != null && buybackDate !== '' && buybackDate !== undefined;

    if (hasYieldDate && !hasBuybackDate) {
      delete allFields['BUYBACKDATE'];
    } else if (hasBuybackDate && !hasYieldDate) {
      delete allFields['YIELDDATE'];
    } else if (!hasYieldDate && !hasBuybackDate) {
      delete allFields['YIELDDATE'];
      delete allFields['BUYBACKDATE'];
    } else if (hasYieldDate && hasBuybackDate) {
      delete allFields['BUYBACKDATE'];
    }

    return allFields;
  }, [bondDetail]);

  const securities = bondDetail?.securities;
  const market = bondDetail?.marketdata;
  const yields = bondDetail?.marketdata_yields?.[0] || {};

  const bondStatus =
    bondDetail && typeof bondDetail.securities.STATUS === 'string'
      ? bondDetail.securities.STATUS
      : null;
  const tradingStatus =
    bondDetail && bondDetail.marketdata && typeof bondDetail.marketdata.TRADINGSTATUS === 'string'
      ? bondDetail.marketdata.TRADINGSTATUS
      : null;

  // Key metrics for header
  const keyMetrics = useMemo(() => {
    if (!bondDetail) return null;

    return {
      price: securities?.PREVPRICE ?? market?.LAST ?? null,
      yield: securities?.YIELDATPREVWAPRICE ?? market?.YIELD ?? yields?.EFFECTIVEYIELD ?? null,
      accruedInt: securities?.ACCRUEDINT ?? null,
      maturityDate: securities?.MATDATE ?? null,
    };
  }, [bondDetail, securities, market, yields]);

  return (
    <Drawer
      anchor="right"
      open={isOpen}
      onClose={handleClose}
      PaperProps={{
        sx: { width: { xs: '100%', sm: 600, md: 700 } },
      }}
    >
      <Box sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h5" fontWeight={700}>
            Детали облигации
          </Typography>
          <IconButton onClick={handleClose}>
            <CloseIcon />
          </IconButton>
        </Box>

        <Divider sx={{ mb: 3 }} />

        {isLoading && <LoadingSpinner message="Загрузка деталей..." />}

        {error && <ErrorMessage message={error} />}

        {!isLoading && !error && !bondDetail && (
          <Typography variant="body2" color="text.secondary">
            Выберите облигацию в таблице, чтобы увидеть подробную информацию.
          </Typography>
        )}

        {bondDetail && !isLoading && !error && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, flexGrow: 1, overflow: 'hidden' }}>
            {/* Премиальная карточка облигации */}
            <PremiumBondCard bondDetail={bondDetail} />

            {/* A. Верхний блок (Header) - оставляем для совместимости, но можно скрыть */}
            <Paper elevation={0} sx={{ p: 0, bgcolor: 'grey.50', borderRadius: 2, mx: -3, px: 3, py: 2.5, display: 'none' }}>
              {/* 1. Название */}
              <Box sx={{ mb: 2 }}>
                <Typography variant="h6" fontWeight={700} gutterBottom>
                  {typeof securities?.SECNAME === 'string' ? securities.SECNAME : securities?.SHORTNAME || securities?.SECID}
                </Typography>
                {typeof securities?.SHORTNAME === 'string' && securities.SHORTNAME !== securities?.SECNAME && (
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    {securities.SHORTNAME}
                  </Typography>
                )}
                <Stack direction="row" spacing={1} sx={{ mt: 1, mb: 1 }}>
                  {typeof securities?.ISIN === 'string' && (
                    <Typography variant="body2" color="text.secondary">
                      ISIN: {securities.ISIN}
                    </Typography>
                  )}
                  {bondStatus && (
                    <Chip
                      label={formatBondStatus(bondStatus)}
                      size="small"
                      color="primary"
                      variant="outlined"
                    />
                  )}
                </Stack>
              </Box>

              {/* 2. Основные характеристики в одну строку */}
              <Box sx={{ mb: 2 }}>
                <Stack direction="row" spacing={2} flexWrap="wrap" sx={{ gap: 1 }}>
                  {securities?.FACEUNIT && (
                    <Typography variant="body2" color="text.secondary">
                      Валюта: <strong>{formatFieldValue('FACEUNIT', securities.FACEUNIT)}</strong>
                    </Typography>
                  )}
                  {securities?.FACEVALUE && (
                    <Typography variant="body2" color="text.secondary">
                      Номинал: <strong>{formatFieldValue('FACEVALUE', securities.FACEVALUE)}</strong>
                    </Typography>
                  )}
                  {securities?.SECTORID && (
                    <Typography variant="body2" color="text.secondary">
                      Сектор: <strong>{formatFieldValue('SECTORID', securities.SECTORID)}</strong>
                    </Typography>
                  )}
                  {securities?.LISTLEVEL !== null && securities?.LISTLEVEL !== undefined && (
                    <Typography variant="body2" color="text.secondary">
                      Уровень листинга: <strong>{formatFieldValue('LISTLEVEL', securities.LISTLEVEL)}</strong>
                    </Typography>
                  )}
                  {securities?.LOTSIZE && (
                    <Typography variant="body2" color="text.secondary">
                      Размер лота: <strong>{formatFieldValue('LOTSIZE', securities.LOTSIZE)}</strong>
                    </Typography>
                  )}
                </Stack>
              </Box>

              {/* 3. Ключевые показатели (выделенные) */}
              <Grid container spacing={2}>
                <Grid item xs={6} sm={3}>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Цена
                  </Typography>
                  <Typography variant="h6" fontWeight={700} color="primary">
                    {keyMetrics?.price ? formatFieldValue('PRICE', keyMetrics.price) : '—'}
                  </Typography>
                </Grid>
                <Grid item xs={6} sm={3}>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Доходность к погашению
                  </Typography>
                  <Typography variant="h6" fontWeight={700} color="primary">
                    {keyMetrics?.yield ? formatFieldValue('YIELD', keyMetrics.yield) : '—'}
                  </Typography>
                </Grid>
                <Grid item xs={6} sm={3}>
                  <Typography variant="caption" color="text.secondary" display="block">
                    НКД
                  </Typography>
                  <Typography variant="h6" fontWeight={700} color="primary">
                    {keyMetrics?.accruedInt ? formatFieldValue('ACCRUEDINT', keyMetrics.accruedInt) : '—'}
                  </Typography>
                </Grid>
                <Grid item xs={6} sm={3}>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Дата погашения
                  </Typography>
                  <Typography variant="h6" fontWeight={700} color="primary">
                    {keyMetrics?.maturityDate ? formatFieldValue('MATDATE', keyMetrics.maturityDate) : '—'}
                  </Typography>
                </Grid>
              </Grid>
            </Paper>

            {/* B. Вкладки основной информации */}
            <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
              <Box sx={{ borderBottom: 1, borderColor: 'divider', mx: -3, px: 3 }}>
                <Tabs
                  value={activeTab}
                  onChange={(_, newValue) => setActiveTab(newValue)}
                  variant="scrollable"
                  scrollButtons
                  allowScrollButtonsMobile
                  sx={{ 
                    minHeight: 'auto',
                    [`& .${tabsClasses.scrollButtons}`]: {
                      '&.Mui-disabled': { opacity: 0.3 },
                    },
                    '& .MuiTabs-flexContainer': {
                      justifyContent: 'flex-start',
                    },
                    '& .MuiTab-root': {
                      minHeight: 'auto',
                      padding: '8px 12px',
                      textTransform: 'none',
                      minWidth: 'auto',
                    }
                  }}
                >
                  <Tab label="Основные данные" />
                  <Tab label="Купонные выплаты" />
                  <Tab label="Доходность и расчёты" />
                  <Tab label="Цена и динамика" />
                  <Tab label="Рынок и ликвидность" />
                  <Tab label="Параметры выпуска" />
                  <Tab label="Расширенные метрики" />
                  <Tab label="Служебные данные" />
                </Tabs>
              </Box>

              <Box sx={{ flexGrow: 1, overflow: 'auto', mt: 2 }}>
                {/* Вкладка 0: Основные данные */}
                {activeTab === 0 && (
                  <Box sx={{ pl: 0 }}>
                    {renderSection('Идентификация', [
                      { field: 'SECNAME', value: securities?.SECNAME ?? null },
                      { field: 'SHORTNAME', value: securities?.SHORTNAME ?? null },
                      { field: 'ISIN', value: securities?.ISIN ?? null },
                      { field: 'REGNUMBER', value: securities?.REGNUMBER ?? null },
                      { field: 'SECTYPE', value: securities?.SECTYPE ?? null },
                    ])}

                    {renderSection('Выпуск', [
                      { field: 'FACEVALUE', value: securities?.FACEVALUE ?? null, label: 'Номинал' },
                      { field: 'FACEUNIT', value: securities?.FACEUNIT ?? null },
                      { field: 'CURRENCYID', value: securities?.CURRENCYID ?? null, label: 'Валюта расчётов' },
                      { field: 'ISSUESIZE', value: securities?.ISSUESIZE ?? null },
                      { field: 'ISSUESIZEPLACED', value: securities?.ISSUESIZEPLACED ?? null, label: 'Количество бумаг в обращении' },
                      { field: 'FACEVALUE', value: securities?.FACEVALUE ?? null, label: 'Непогашенный долг' },
                    ])}

                    {renderSection('Купон', [
                      { field: 'COUPONPERCENT', value: securities?.COUPONPERCENT ?? null },
                      { field: 'COUPONPERIOD', value: securities?.COUPONPERIOD ?? null },
                      { field: 'COUPONVALUE', value: securities?.COUPONVALUE ?? null },
                      { field: 'ACCRUEDINT', value: securities?.ACCRUEDINT ?? null },
                      { field: 'NEXTCOUPON', value: securities?.NEXTCOUPON ?? null, label: 'Дата следующего купона' },
                      { 
                        field: 'COUPONTYPE', 
                        value: couponType === 'FIX' ? 'постоянный' : couponType === 'FLOAT' ? 'плавающий' : null,
                        label: 'Тип купона'
                      },
                    ])}

                    {renderSection('Сроки', [
                      { field: 'MATDATE', value: securities?.MATDATE ?? null },
                      { field: 'OFFERDATE', value: securities?.OFFERDATE ?? null },
                      { field: 'PUTOPTIONDATE', value: securities?.PUTOPTIONDATE ?? null },
                      { field: 'CALLOPTIONDATE', value: securities?.CALLOPTIONDATE ?? null },
                    ])}
                  </Box>
                )}

                {/* Вкладка 1: Купонные выплаты */}
                {activeTab === 1 && (
                  <Box>
                    <CouponsTable
                      coupons={coupons}
                      isLoading={isLoadingCoupons}
                      error={couponsError}
                      currency={coupons.length > 0 ? coupons[0]?.faceunit || null : null}
                    />
                  </Box>
                )}

                {/* Вкладка 2: Доходность и расчёты */}
                {activeTab === 2 && (
                  <Box>
                    {renderSection('Основные доходности', [
                      { field: 'YIELD', value: market?.YIELD ?? yields?.EFFECTIVEYIELD ?? securities?.YIELDATPREVWAPRICE ?? null, label: 'Доходность к погашению' },
                      { field: 'YIELDTOOFFER', value: market?.YIELDTOOFFER ?? yields?.YIELDTOOFFER ?? null },
                      { field: 'CALLOPTIONYIELD', value: market?.CALLOPTIONYIELD ?? null },
                      { field: 'EFFECTIVEYIELD', value: yields?.EFFECTIVEYIELD ?? null },
                      { field: 'EFFECTIVEYIELDWAPRICE', value: yields?.EFFECTIVEYIELDWAPRICE ?? null },
                    ])}

                    {renderSection('Спрэды', [
                      { field: 'GSPREADBP', value: yields?.GSPREADBP ?? null },
                      { field: 'ZSPREADBP', value: yields?.ZSPREADBP ?? null },
                    ])}

                    {renderSection('Дата расчёта', [
                      { field: 'YIELDDATE', value: yields?.YIELDDATE ?? securities?.BUYBACKDATE ?? null, label: 'Дата, к которой рассчитывается доходность' },
                      { field: 'DATEYIELDFROMISSUER', value: securities?.DATEYIELDFROMISSUER ?? null, label: 'Дата, указанная эмитентом для расчёта' },
                    ])}
                  </Box>
                )}

                {/* Вкладка 3: Цена и динамика */}
                {activeTab === 3 && (
                  <Box>
                    {renderSection('Текущие цены', [
                      { field: 'LCURRENTPRICE', value: market?.LCURRENTPRICE ?? null },
                      { field: 'LAST', value: market?.LAST ?? null },
                      { field: 'LCLOSEPRICE', value: market?.LCLOSEPRICE ?? null },
                      { field: 'PREVLEGALCLOSEPRICE', value: securities?.PREVLEGALCLOSEPRICE ?? null },
                      { field: 'OPEN', value: market?.OPEN ?? null },
                      { field: 'BUYBACKPRICE', value: securities?.BUYBACKPRICE ?? null },
                    ])}

                    {renderSection('Средневзвешенные цены', [
                      { field: 'WAPRICE', value: market?.WAPRICE ?? yields?.WAPRICE ?? null },
                      { field: 'PREVWAPRICE', value: securities?.PREVWAPRICE ?? null },
                    ])}

                    {renderSection('Изменения', [
                      { field: 'LASTTOPREVPRICE', value: market?.LASTTOPREVPRICE ?? null, label: 'Изменение цены последней сделки к предыдущему дню' },
                      { field: 'LASTCNGTOLASTWAPRICE', value: market?.LASTCNGTOLASTWAPRICE ?? null, label: 'Изменение к средневзвешенной цене' },
                      { field: 'WAPTOPREVWAPRICEPRCNT', value: market?.WAPTOPREVWAPRICEPRCNT ?? null, label: 'Изменение средневзвешенной к предыдущему дню' },
                      { field: 'LASTCHANGEPRCNT', value: market?.LASTCHANGEPRCNT ?? null, label: 'Изменение цены последней к предыдущей сделке' },
                    ])}
                  </Box>
                )}

                {/* Вкладка 4: Рынок и ликвидность */}
                {activeTab === 4 && (
                  <Box>
                    {renderSection('Глубина рынка', [
                      { field: 'BID', value: market?.BID ?? null },
                      { field: 'OFFER', value: market?.OFFER ?? null },
                      { field: 'HIGHBID', value: market?.HIGHBID ?? null },
                      { field: 'LOWOFFER', value: market?.LOWOFFER ?? null },
                      { field: 'SPREAD', value: market?.SPREAD ?? null },
                    ])}

                    {renderSection('Активность', [
                      { field: 'NUMTRADES', value: market?.NUMTRADES ?? null },
                      { field: 'VOLTODAY', value: market?.VOLTODAY ?? null },
                      { field: 'QTY', value: market?.QTY ?? null, label: 'Объем последней сделки (лоты/рубли)' },
                      { field: 'VALUE', value: market?.VALUE ?? null },
                      { field: 'VALTODAY', value: market?.VALTODAY ?? null },
                    ])}

                    {renderSection('Статус торгов', [
                      { field: 'TRADINGSESSION', value: market?.TRADINGSESSION ?? null },
                      { field: 'TRADINGSTATUS', value: market?.TRADINGSTATUS ?? null },
                    ])}
                  </Box>
                )}

                {/* Вкладка 5: Параметры выпуска */}
                {activeTab === 5 && (
                  <Box>
                    {renderSection('Структурная информация', [
                      { field: 'ISSUESIZE', value: securities?.ISSUESIZE ?? null },
                      { field: 'ISSUESIZEPLACED', value: securities?.ISSUESIZEPLACED ?? null },
                      { field: 'FACEVALUEONSETTLEDATE', value: securities?.FACEVALUEONSETTLEDATE ?? null },
                      { field: 'OFFERDEPTHT', value: market?.OFFERDEPTHT ?? null },
                      { field: 'BOARDNAME', value: securities?.BOARDNAME ?? null },
                      { field: 'MARKETCODE', value: securities?.MARKETCODE ?? null },
                    ])}
                  </Box>
                )}

                {/* Вкладка 6: Расширенные метрики */}
                {activeTab === 6 && (
                  <Box>
                    {renderSection('Дюрация', [
                      { field: 'DURATION', value: market?.DURATION ?? yields?.DURATION ?? null },
                      { field: 'CALLOPTIONDURATION', value: market?.CALLOPTIONDURATION ?? null },
                      { field: 'DURATIONWAPRICE', value: yields?.DURATIONWAPRICE ?? securities?.DURATIONWAPRICE ?? null },
                    ])}

                    {renderSection('Прочие показатели', [
                      { field: 'MARKETPRICE2', value: market?.MARKETPRICE2 ?? null },
                      { field: 'YIELDDATETYPE', value: yields?.YIELDDATETYPE ?? null },
                    ])}
                  </Box>
                )}

                {/* Вкладка 7: Служебные данные (скрыта по умолчанию) */}
                {activeTab === 7 && (
                  <Box>
                    <Accordion defaultExpanded={false}>
                      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography variant="subtitle2" color="text.secondary">
                          Служебные данные (вспомогательные)
                        </Typography>
                      </AccordionSummary>
                      <AccordionDetails>
                        <Box
                          sx={{
                            display: 'grid',
                            gridTemplateColumns: 'minmax(0, 1.3fr) minmax(0, 1fr)',
                            columnGap: 2,
                            rowGap: 1.5,
                            alignItems: 'start',
                          }}
                        >
                          {renderField('SECID', securities?.SECID ?? null)}
                          {renderField('SEQNUM', market?.SEQNUM ?? yields?.SEQNUM ?? null, 'Номер обновления')}
                          {renderField('REMARKS', securities?.REMARKS ?? null)}
                          {renderField('ZCYCMOMENT', yields?.ZCYCMOMENT ?? null, 'Маркер КБД')}
                          {renderField('DECIMALS', securities?.DECIMALS ?? null)}
                          {renderField('BOARDID', securities?.BOARDID ?? market?.BOARDID ?? null)}
                        </Box>
                      </AccordionDetails>
                    </Accordion>
                  </Box>
                )}

              </Box>
            </Box>
          </Box>
        )}
      </Box>
    </Drawer>
  );
};

export default BondDetails;
