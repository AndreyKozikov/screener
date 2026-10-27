/**
 * TypeScript типы данных инфляционных ожиданий
 */

export type InflationExpectationsIndicatorValue = string | number | boolean | null;

export type InflationExpectationsIndicatorBlock = Record<string, InflationExpectationsIndicatorValue>;

export type InflationExpectationsMonthData = Record<string, InflationExpectationsIndicatorBlock>;

export type InflationExpectationsYearData = Record<string, InflationExpectationsMonthData>;

export type InflationExpectationsData = Record<string, InflationExpectationsYearData>;

export interface InflationExpectationsLoadResponse {
  status: string;
  data: InflationExpectationsData;
}


