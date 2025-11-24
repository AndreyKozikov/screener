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
  Button,
  Stack,
  Tooltip,
  Alert,
  Tabs,
  Tab,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
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

  // Load coupons when tab changes to "Купонные выплаты" or when bond is selected
  useEffect(() => {
    if (!selectedBondId || activeTab !== 1) {
      return;
    }

    // Reset coupon count when switching bonds or opening tab
    // This ensures we detect when coupons are loaded for the first time
    const currentSecIdRef = selectedBondId;
    const hadCouponsBefore = prevCouponsCountRef.current > 0;
    prevCouponsCountRef.current = 0;

    // Only load if we don't have coupons already
    if (coupons.length > 0 && !couponsError) {
      // If we already have coupons but they were from a different bond,
      // we should still trigger refresh to update the table
      // (in case data was just downloaded)
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
          
          // If coupons were loaded, always trigger data refresh to update the main table
          // This ensures the table shows the coupon value after data is downloaded or updated
          if (hasCouponsNow) {
            prevCouponsCountRef.current = response.coupons.length;
            // Add a small delay to allow backend to save data and clear caches
            setTimeout(() => {
              // Double-check we're still on the same bond
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

  const renderRecord = (record: Record<string, BondFieldValue> | null) => {
    if (!record || Object.keys(record).length === 0) {
      return (
        <Typography variant="body2" color="text.secondary">
          Данные отсутствуют
        </Typography>
      );
    }

    const sortedEntries = Object.entries(record).sort((a, b) =>
      collator.compare(getFieldLabel(a[0]), getFieldLabel(b[0])),
    );

    return (
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.3fr) minmax(0, 1fr)',
          columnGap: 2,
          rowGap: 1.5,
          alignItems: 'start',
        }}
      >
        {sortedEntries.map(([field, value]) => {
          const label = getFieldLabel(field);
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
                  {label}
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
        })}
      </Box>
    );
  };

  const prepareRecordForExport = (record: Record<string, BondFieldValue> | null): Record<string, string> => {
    if (!record) {
      return {};
    }

    return Object.fromEntries(
      Object.entries(record).map(([field, value]) => [
        getFieldLabel(field),
        formatFieldValue(field, value),
      ]),
    );
  };


  const mainMetrics = useMemo(() => {
    if (!bondDetail) {
      return [];
    }

    const securities = bondDetail.securities;
    const market = bondDetail.marketdata;

    return [
      { label: 'Купонная ставка', field: 'COUPONPERCENT', value: securities.COUPONPERCENT ?? null },
      {
        label: 'Доходность',
        field: 'YIELDATPREVWAPRICE',
        value: securities.YIELDATPREVWAPRICE ?? market?.YIELD ?? null,
      },
      { label: 'Номинал', field: 'FACEVALUE', value: securities.FACEVALUE ?? null },
      { label: 'Цена', field: 'PREVPRICE', value: securities.PREVPRICE ?? market?.LAST ?? null },
      { label: 'НКД', field: 'ACCRUEDINT', value: securities.ACCRUEDINT ?? null },
      { label: 'Размер лота', field: 'LOTSIZE', value: securities.LOTSIZE ?? null },
      { label: 'Дата погашения', field: 'MATDATE', value: securities.MATDATE ?? null },
      { label: 'Следующий купон', field: 'NEXTCOUPON', value: securities.NEXTCOUPON ?? null },
      {
        label: 'Валюта',
        field: 'FACEUNIT',
        value: securities.FACEUNIT ?? securities.CURRENCYID ?? null,
      },
    ];
  }, [bondDetail]);

  const bondStatus =
    bondDetail && typeof bondDetail.securities.STATUS === 'string'
      ? bondDetail.securities.STATUS
      : null;
  const tradingStatus =
    bondDetail && bondDetail.marketdata && typeof bondDetail.marketdata.TRADINGSTATUS === 'string'
      ? bondDetail.marketdata.TRADINGSTATUS
      : null;

  return (
    <Drawer
      anchor="right"
      open={isOpen}
      onClose={handleClose}
      PaperProps={{
        sx: { width: { xs: '100%', sm: 500, md: 600 } },
      }}
    >
      <Box sx={{ p: 3 }}>
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
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <Paper elevation={0} sx={{ p: 2, bgcolor: 'grey.50' }}>
              <Stack spacing={1.5}>
                <Box>
                  <Typography variant="h6" gutterBottom fontWeight={600}>
                    {typeof bondDetail.securities.SHORTNAME === 'string'
                      ? bondDetail.securities.SHORTNAME
                      : bondDetail.securities.SECID}
                  </Typography>
                  {typeof bondDetail.securities.SECNAME === 'string' && (
                    <Typography variant="body2" color="text.secondary">
                      {bondDetail.securities.SECNAME}
                    </Typography>
                  )}
                </Box>
                <Stack direction="row" spacing={1}>
                  {bondStatus && (
                    <Chip
                      label={formatBondStatus(bondStatus)}
                      size="small"
                      color="primary"
                      variant="outlined"
                    />
                  )}
                  {tradingStatus && (
                    <Chip
                      label={formatTradingStatus(tradingStatus)}
                      size="small"
                      color="success"
                      variant="outlined"
                    />
                  )}
                </Stack>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                  <Typography variant="caption" color="text.secondary">
                    SECID
                  </Typography>
                  <Typography variant="body2">
                    {typeof bondDetail.securities.SECID === 'string'
                      ? bondDetail.securities.SECID
                      : '—'}
                  </Typography>
                  {typeof bondDetail.securities.ISIN === 'string' && (
                    <Typography variant="body2" color="text.secondary">
                      ISIN: {bondDetail.securities.ISIN}
                    </Typography>
                  )}
                  {typeof bondDetail.securities.REGNUMBER === 'string' && (
                    <Typography variant="body2" color="text.secondary">
                      Рег. номер: {bondDetail.securities.REGNUMBER}
                    </Typography>
                  )}
                </Box>
                {isMetadataLoading && (
                  <Typography variant="body2" color="text.secondary">
                    Загружаем метаданные...
                  </Typography>
                )}
                {metadataError && (
                  <Alert severity="warning" variant="outlined">
                    {metadataError}
                  </Alert>
                )}
              </Stack>
            </Paper>

            {/* Tabs */}
            <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
              <Tabs value={activeTab} onChange={(_, newValue) => setActiveTab(newValue)}>
                <Tab label="Основные данные" />
                <Tab label="Купонные выплаты" />
              </Tabs>
            </Box>

            {/* Tab content */}
            {activeTab === 0 && (() => {
              // Поля, которые нужно исключить из отображения
              const excludedFields = new Set([
                // Вмененные значения
                'IR',           // Вмененная RUONIA
                'ICPI',         // Вмененная инфляция
                'BEI',          // Вмененная инфляция (BEI)
                'BEICLOSE',     // Вмененная инфляция (BEI)
                'CBR',          // Вмененная Банка России
                'CBRCLOSE',     // Вмененная Банка России
                'IRICPICLOSE',  // Вмененная ставка
                // Временные поля
                'SYSTIME',      // Время загрузки
                'UPDATETIME',   // Время обновления
                'TIME',         // Время последней
                'TRADEMOMENT',  // Время последней
                // Объемы котировок
                'BIDDEPTH',     // Объем лучшей котировки на покупку, штук
                'OFFERDEPTH',   // Объем лучшей котировки на продажу, штук
              ]);
              
              // Объединяем все данные из всех разделов в один объект
              const allFields: Record<string, BondFieldValue> = {};
              
              // Добавляем данные из securities
              if (bondDetail.securities) {
                Object.entries(bondDetail.securities).forEach(([key, value]) => {
                  if (!excludedFields.has(key)) {
                    allFields[key] = value;
                  }
                });
              }
              
              // Добавляем данные из marketdata
              if (bondDetail.marketdata) {
                Object.entries(bondDetail.marketdata).forEach(([key, value]) => {
                  if (!excludedFields.has(key)) {
                    allFields[key] = value;
                  }
                });
              }
              
              // Добавляем данные из marketdata_yields (объединяем все записи)
              if (bondDetail.marketdata_yields && bondDetail.marketdata_yields.length > 0) {
                bondDetail.marketdata_yields.forEach((entry) => {
                  Object.entries(entry).forEach(([key, value]) => {
                    if (!excludedFields.has(key)) {
                      allFields[key] = value;
                    }
                  });
                });
              }
              
              // Фильтруем похожие поля даты дохода - оставляем только то, которое имеет значение
              // YIELDDATE ("Дата, к кот.рассч.дох.") и BUYBACKDATE ("Дата, к кот.рассч.доходность")
              const yieldDate = allFields['YIELDDATE'];
              const buybackDate = allFields['BUYBACKDATE'];
              
              // Проверяем, есть ли реальное значение (не null, не пустая строка, не undefined)
              const hasYieldDate = yieldDate != null && yieldDate !== '' && yieldDate !== undefined;
              const hasBuybackDate = buybackDate != null && buybackDate !== '' && buybackDate !== undefined;
              
              if (hasYieldDate && !hasBuybackDate) {
                // Если YIELDDATE имеет значение, а BUYBACKDATE нет - удаляем BUYBACKDATE
                delete allFields['BUYBACKDATE'];
              } else if (hasBuybackDate && !hasYieldDate) {
                // Если BUYBACKDATE имеет значение, а YIELDDATE нет - удаляем YIELDDATE
                delete allFields['YIELDDATE'];
              } else if (!hasYieldDate && !hasBuybackDate) {
                // Если оба пустые, удаляем оба
                delete allFields['YIELDDATE'];
                delete allFields['BUYBACKDATE'];
              } else if (hasYieldDate && hasBuybackDate) {
                // Если оба имеют значение, оставляем только YIELDDATE (приоритет marketdata_yields)
                delete allFields['BUYBACKDATE'];
              }
              
              return (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                  <Box>
                    <Typography variant="h6" gutterBottom fontWeight={600}>
                      Основные показатели
                    </Typography>
                    <Grid container spacing={2}>
                      {mainMetrics.map(({ label, field, value }) => (
                        <Grid item xs={12} sm={6} key={field}>
                          <Typography variant="caption" color="text.secondary">
                            {label}
                          </Typography>
                          <Typography variant="body1" fontWeight={500}>
                            {formatFieldValue(field, value ?? null)}
                          </Typography>
                        </Grid>
                      ))}
                    </Grid>
                  </Box>

                  {/* Все параметры облигации в одном списке */}
                  <Box>
                    <Typography variant="h6" gutterBottom fontWeight={600}>
                      Все параметры
                    </Typography>
                    {renderRecord(allFields)}
                  </Box>
                </Box>
              );
            })()}

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
          </Box>
        )}
      </Box>
    </Drawer>
  );
};

export default BondDetails;
