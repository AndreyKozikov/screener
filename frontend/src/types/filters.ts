/**
 * Filter state and request interfaces
 */

export interface BondFilters {
  couponMin: number | null;
  couponMax: number | null;
  yieldMin: number | null;
  yieldMax: number | null;
  couponYieldMin: number | null;
  couponYieldMax: number | null;
  matdateFrom: string | null;
  matdateTo: string | null;
  listlevel: number[];
  faceunit: string[];
  bondtype: string[];
  couponType: string[];
  ratingMin: string | null;
  ratingMax: string | null;
  search: string;
  skip: number;
  limit: number;
}

export interface FilterOptions {
  listlevels: number[];
  faceunits: string[];
  bondtypes: string[];
}
