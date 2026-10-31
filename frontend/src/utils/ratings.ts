/**
 * Utilities for working with bond and emitent ratings
 */

export interface Rating {
  agency_id?: number | null;
  agency_name_short_ru?: string | null;
  rating_level_id?: number | null;
  rating_date?: string | null;
  rating_publicate_date?: string | null;
  rating_level_name_short_ru?: string | null;
}

/**
 * Rating scale from highest to lowest
 */
const RATING_SCALE = [
  'AAA',
  'AA+', 'AA', 'AA-',
  'A+', 'A', 'A-',
  'BBB+', 'BBB', 'BBB-',
  'BB+', 'BB', 'BB-',
  'B+', 'B', 'B-',
  'CCC+', 'CCC', 'CCC-',
  'CC', 'C',
  'D'
];

/**
 * Normalize agency-specific labels while keeping the +/- grade modifier.
 */
const normalizeRating = (rating: string): string => {
  if (!rating || rating.trim() === '' || rating === '—' || rating === '-') {
    return '';
  }
  
  // Convert to uppercase and trim
  let normalized = rating.toUpperCase().trim();
  
  // Strip only known market/agency decorations; +/- remains part of the grade.
  let previous = '';
  while (normalized !== previous) {
    previous = normalized;
    normalized = normalized
      .replace(/\s*\(RU\)\s*$/i, '')
      .replace(/\.ru\s*$/i, '')
      .replace(/^\(RU\)\s*/i, '')
      .replace(/^RU\s*/i, '')
      .replace(/\|ru\|/i, '');
  }
  normalized = normalized.replace(/\.SF$/i, '').trim();
  const gradeCandidate = normalized.replace(/\s+/g, '').toUpperCase();

  const gradeMatch = gradeCandidate.match(/^(AAA|AA|A|BBB|BB|B|CCC|CC|C|D)([+-]?)$/);
  return gradeMatch ? `${gradeMatch[1]}${gradeMatch[2]}` : rating.trim();
};

/**
 * Get rating index in the rating scale (lower index = better rating)
 */
const getRatingIndex = (rating: string): number => {
  const normalized = normalizeRating(rating);
  if (!normalized) {
    return RATING_SCALE.length; // Worst possible (not found)
  }
  
  const index = RATING_SCALE.indexOf(normalized);
  return index === -1 ? RATING_SCALE.length : index;
};

/**
 * Find worst rating from a list of ratings, excluding "Отозван" if other ratings exist
 * 
 * @param ratings List of rating objects
 * @returns Worst rating object or null
 */
export const getWorstRating = (ratings: Rating[]): Rating | null => {
  if (!ratings || ratings.length === 0) {
    return null;
  }
  
  // Filter out "Отозван" ratings if other ratings exist
  const nonRevokedRatings = ratings.filter(r => {
    const level = r.rating_level_name_short_ru || '';
    return !level.toLowerCase().includes('отозван');
  });
  
  // If we have non-revoked ratings, use them; otherwise use all ratings
  const ratingsToCheck = nonRevokedRatings.length > 0 ? nonRevokedRatings : ratings;
  
  if (ratingsToCheck.length === 0) {
    return null;
  }
  
  // Find worst rating (highest index in rating scale)
  let worstRating: Rating | null = null;
  let worstIndex = -1;
  
  for (const rating of ratingsToCheck) {
    const level = rating.rating_level_name_short_ru || '';
    if (!level) continue;
    
    const index = getRatingIndex(level);
    if (index > worstIndex) {
      worstIndex = index;
      worstRating = rating;
    }
  }
  
  return worstRating;
};

/**
 * Get rating level string from rating object
 */
export const getRatingLevel = (rating: Rating | null): string | null => {
  if (!rating) return null;
  const level = rating.rating_level_name_short_ru;
  if (!level) return null;
  return normalizeRating(level) || null;
};

/**
 * Get rating agency string from rating object
 */
export const getRatingAgency = (rating: Rating | null): string | null => {
  if (!rating) return null;
  return rating.agency_name_short_ru || null;
};





