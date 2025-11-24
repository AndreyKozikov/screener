/**
 * Filter state and request interfaces
 */

export interface BondFilters {
  couponMin: number | null;
  couponMax: number | null;
  matdateFrom: string | null;
  matdateTo: string | null;
  listlevel: number[];
  faceunit: string[];
  search: string;
  skip: number;
  limit: number;
}

export interface FilterOptions {
  listlevels: number[];
  faceunits: string[];
}
