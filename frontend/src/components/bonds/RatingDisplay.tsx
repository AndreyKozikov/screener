import React, { useState, useEffect, useMemo } from 'react';
import { Box } from '@mui/material';
import type { BondListItem } from '../../types/bond';
import { getWorstRating, getRatingLevel, type Rating } from '../../utils/ratings';
import { getEmitentBySecid } from '../../api/emitent';
import { getRatingColor } from './BondsTable';

interface RatingDisplayProps {
  bond: BondListItem;
  size?: 'small' | 'medium' | 'large';
}

/**
 * RatingDisplay Component
 * 
 * Displays the worst rating for a bond, or emitent rating if bond rating is not available.
 * Excludes "Отозван" ratings if other ratings exist.
 */
export const RatingDisplay: React.FC<RatingDisplayProps> = ({ bond, size = 'medium' }) => {
  const [emitentRatings, setEmitentRatings] = useState<Rating[] | null>(null);
  const [isLoadingEmitent, setIsLoadingEmitent] = useState(false);

  // Get bond ratings
  const bondRatings = useMemo(() => {
    if (bond.RATINGS && Array.isArray(bond.RATINGS) && bond.RATINGS.length > 0) {
      return bond.RATINGS;
    }
    // Fallback: if RATING_LEVEL exists but RATINGS doesn't, create a rating object
    if (bond.RATING_LEVEL && bond.RATING_AGENCY) {
      return [{
        rating_level_name_short_ru: bond.RATING_LEVEL,
        agency_name_short_ru: bond.RATING_AGENCY,
      }];
    }
    return null;
  }, [bond.RATINGS, bond.RATING_LEVEL, bond.RATING_AGENCY]);

  // Get worst rating from bond ratings
  const worstBondRating = useMemo(() => {
    if (!bondRatings) return null;
    return getWorstRating(bondRatings);
  }, [bondRatings]);

  // Fetch emitent ratings if bond rating is not available
  useEffect(() => {
    if (!worstBondRating && !isLoadingEmitent && !emitentRatings) {
      setIsLoadingEmitent(true);
      getEmitentBySecid(bond.SECID)
        .then((emitentInfo) => {
          if (emitentInfo.cci_rating_companies && Array.isArray(emitentInfo.cci_rating_companies)) {
            setEmitentRatings(emitentInfo.cci_rating_companies);
          }
        })
        .catch(() => {
          // Silently fail - emitent rating is optional
        })
        .finally(() => {
          setIsLoadingEmitent(false);
        });
    }
  }, [bond.SECID, worstBondRating, isLoadingEmitent, emitentRatings]);

  // Get worst rating from emitent ratings
  const worstEmitentRating = useMemo(() => {
    if (!emitentRatings || emitentRatings.length === 0) return null;
    return getWorstRating(emitentRatings);
  }, [emitentRatings]);

  // Select final rating: bond rating first, then emitent rating
  const finalRating = worstBondRating || worstEmitentRating;
  const ratingLevel = getRatingLevel(finalRating);

  // Size styles
  const sizeStyles = {
    small: { px: 0.75, py: 0.25, fontSize: '11px', minWidth: '45px' },
    medium: { px: 1, py: 0.5, fontSize: '12px', minWidth: '50px' },
    large: { px: 1.5, py: 0.75, fontSize: '14px', minWidth: '60px' },
  };

  if (!ratingLevel) {
    return <Box component="span">—</Box>;
  }

  const { bg, color } = getRatingColor(ratingLevel);

  return (
    <Box
      component="span"
      sx={{
        ...sizeStyles[size],
        borderRadius: '6px',
        backgroundColor: bg,
        color: color,
        fontWeight: 600,
        display: 'inline-block',
        textAlign: 'center',
      }}
    >
      {ratingLevel}
    </Box>
  );
};

