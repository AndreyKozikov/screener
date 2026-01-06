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
 * Normalize rating string to extract base rating (AAA, AA, A, BBB, etc.)
 */
const normalizeRating = (rating: string): string => {
  if (!rating || rating.trim() === '' || rating === '—' || rating === '-') {
    return '';
  }
  
  // Convert to uppercase and trim
  let normalized = rating.toUpperCase().trim();
  
  // Remove prefixes: RU, (RU) at the start
  normalized = normalized.replace(/^RU\s*/i, '');
  normalized = normalized.replace(/^\(RU\)\s*/i, '');
  
  // Remove all brackets and their contents
  normalized = normalized.replace(/\([^)]*\)/g, '');
  
  // Remove suffixes: .SF, -SF, .sf at the end
  normalized = normalized.replace(/[.\-]?SF$/i, '');
  normalized = normalized.replace(/\.sf$/i, '');
  
  // Remove + and - at the end
  normalized = normalized.replace(/[+\-]+$/, '');
  
  // Remove all dots and dashes
  normalized = normalized.replace(/[.\-]/g, '');
  
  // Extract base letter part (AAA, AA, A, BBB, BB, B, CCC, CC, C, D)
  const letterMatch = normalized.match(/^(AAA|AA|A|BBB|BB|B|CCC|CC|C|D)/);
  if (letterMatch) {
    return letterMatch[1];
  }
  
  // If no exact match, try to extract only letters and find pattern
  const lettersOnly = normalized.replace(/[^A-Z]/g, '');
  const patternMatch = lettersOnly.match(/^(AAA|AA|A|BBB|BB|B|CCC|CC|C|D)/);
  if (patternMatch) {
    return patternMatch[1];
  }
  
  return '';
};

/**
 * Get rating index in the rating scale (lower index = better rating)
 */
const getRatingIndex = (rating: string): number => {
  const normalized = normalizeRating(rating);
  if (!normalized) {
    return RATING_SCALE.length; // Worst possible (not found)
  }
  
  // Try exact match first
  const exactIndex = RATING_SCALE.findIndex(r => r === normalized);
  if (exactIndex !== -1) {
    return exactIndex;
  }
  
  // Try to find base match (e.g., "AA" matches "AA+", "AA", "AA-")
  const baseMatch = RATING_SCALE.findIndex(r => {
    const base = normalizeRating(r);
    return base === normalized;
  });
  
  if (baseMatch !== -1) {
    return baseMatch;
  }
  
  return RATING_SCALE.length; // Worst possible (not found)
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
  return rating.rating_level_name_short_ru || null;
};

/**
 * Get rating agency string from rating object
 */
export const getRatingAgency = (rating: Rating | null): string | null => {
  if (!rating) return null;
  return rating.agency_name_short_ru || null;
};


