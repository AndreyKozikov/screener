import React from 'react';

export type HubCardIllustrationVariant = 'market' | 'portfolio' | 'forecast' | 'comparison' | 'blog';

type HubCardIllustrationProps = {
  variant: HubCardIllustrationVariant;
  color: string;
};

/** Small, decorative vector illustrations for the home-page feature cards. */
export const HubCardIllustration: React.FC<HubCardIllustrationProps> = ({ variant, color }) => {
  if (variant === 'portfolio') {
    return (
      <svg viewBox="0 0 280 150" role="presentation" aria-hidden="true" focusable="false">
        <defs>
          <linearGradient id="portfolioRing" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#77e7c4" />
            <stop offset="100%" stopColor={color} />
          </linearGradient>
        </defs>
        <circle cx="72" cy="80" r="51" fill="none" stroke="#b8f2df" strokeWidth="22" opacity="0.62" />
        <circle cx="72" cy="80" r="51" fill="none" stroke="url(#portfolioRing)" strokeWidth="22" strokeDasharray="107 214" transform="rotate(-90 72 80)" />
        <circle cx="72" cy="80" r="51" fill="none" stroke="#21c894" strokeWidth="22" strokeDasharray="73 248" strokeDashoffset="-113" transform="rotate(-90 72 80)" />
        <circle cx="72" cy="80" r="51" fill="none" stroke="#80e6c4" strokeWidth="22" strokeDasharray="52 269" strokeDashoffset="-193" transform="rotate(-90 72 80)" />
        <circle cx="72" cy="80" r="37" fill="#f5fffb" opacity="0.9" />
        {[0, 1, 2, 3].map((item) => (
          <g key={item} transform={`translate(156 ${38 + item * 27})`}>
            <circle cx="5" cy="4" r="5" fill={item % 2 ? '#75dec0' : color} opacity="0.88" />
            <rect x="19" y="0" width={item === 0 ? 82 : 69 + (item % 2) * 10} height="9" rx="4.5" fill="#78ddc2" opacity={item === 0 ? 0.5 : 0.34} />
          </g>
        ))}
      </svg>
    );
  }

  if (variant === 'forecast') {
    return (
      <svg viewBox="0 0 280 150" role="presentation" aria-hidden="true" focusable="false">
        <defs>
          <linearGradient id="forecastBars" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.36" />
            <stop offset="100%" stopColor={color} stopOpacity="0.03" />
          </linearGradient>
          <linearGradient id="forecastArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.19" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        {[18, 59, 100, 141, 182, 223].map((x, index) => {
          const height = [39, 57, 48, 76, 91, 119][index];
          return <rect key={x} x={x} y={139 - height} width="23" height={height} rx="6" fill="url(#forecastBars)" />;
        })}
        <path d="M8 130 C34 122 42 95 70 96 C95 97 101 80 122 84 C151 89 159 58 184 57 C211 56 221 45 246 18 L271 4 L271 143 L8 143Z" fill="url(#forecastArea)" />
        <path d="M8 130 C34 122 42 95 70 96 C95 97 101 80 122 84 C151 89 159 58 184 57 C211 56 221 45 246 18 L271 4" fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="271" cy="4" r="5" fill={color} />
        <circle cx="246" cy="18" r="3.5" fill="#fff" stroke={color} strokeWidth="2" />
      </svg>
    );
  }

  if (variant === 'comparison') {
    return (
      <svg viewBox="0 0 280 150" role="presentation" aria-hidden="true" focusable="false">
        <defs>
          <linearGradient id="comparisonFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.18" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d="M8 116 C34 116 44 91 67 91 C89 91 98 111 121 101 C148 89 147 53 178 51 C201 49 213 69 232 59 C250 50 255 24 274 11 L274 145 L8 145Z" fill="url(#comparisonFill)" />
        <path d="M8 116 C34 116 44 91 67 91 C89 91 98 111 121 101 C148 89 147 53 178 51 C201 49 213 69 232 59 C250 50 255 24 274 11" fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" />
        <path d="M8 132 C35 124 45 125 67 121 C89 117 100 137 123 128 C148 118 155 101 178 102 C202 103 214 118 235 108 C251 100 261 82 274 75" fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeDasharray="5 5" opacity="0.44" />
        <circle cx="178" cy="51" r="4" fill="#fff" stroke={color} strokeWidth="2" />
      </svg>
    );
  }

  if (variant === 'blog') {
    return (
      <svg viewBox="0 0 280 150" role="presentation" aria-hidden="true" focusable="false">
        <rect x="10" y="23" width="126" height="82" rx="9" fill="#9ce7ef" opacity="0.84" />
        <path d="M18 94 52 58l19 21 18-27 39 42Z" fill="#44c6d7" opacity="0.92" />
        <path d="M18 94 49 68l17 19 17-13 35 29Z" fill="#20b5c8" opacity="0.78" />
        <circle cx="111" cy="44" r="8" fill="#e5fbff" opacity="0.92" />
        <rect x="155" y="28" width="111" height="10" rx="5" fill="#8de2eb" opacity="0.64" />
        <rect x="155" y="48" width="96" height="9" rx="4.5" fill="#8de2eb" opacity="0.42" />
        <rect x="155" y="65" width="105" height="9" rx="4.5" fill="#8de2eb" opacity="0.34" />
        <rect x="10" y="119" width="102" height="9" rx="4.5" fill="#84dfe9" opacity="0.38" />
        <rect x="10" y="137" width="146" height="8" rx="4" fill="#84dfe9" opacity="0.24" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 280 150" role="presentation" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="marketBars" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.58" />
          <stop offset="100%" stopColor={color} stopOpacity="0.08" />
        </linearGradient>
        <linearGradient id="marketArea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.2" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {[12, 48, 84, 120, 156, 192, 228, 256].map((x, index) => {
        const height = [37, 54, 43, 76, 96, 65, 112, 129][index];
        return <rect key={x} x={x} y={142 - height} width="19" height={height} rx="5" fill="url(#marketBars)" opacity={index < 2 ? 0.62 : 0.78} />;
      })}
      <path d="M6 101 C28 105 32 127 53 123 C73 119 79 90 100 94 C121 98 123 111 144 104 C167 96 177 111 194 104 C214 96 223 66 242 57 C255 50 260 40 274 25 L274 145 L6 145Z" fill="url(#marketArea)" />
      <path d="M6 101 C28 105 32 127 53 123 C73 119 79 90 100 94 C121 98 123 111 144 104 C167 96 177 111 194 104 C214 96 223 66 242 57 C255 50 260 40 274 25" fill="none" stroke={color} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" opacity="0.78" />
      <circle cx="274" cy="25" r="4" fill={color} opacity="0.78" />
    </svg>
  );
};
