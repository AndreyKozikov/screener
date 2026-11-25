import { Box, Typography } from '@mui/material';
import type { EmitentInfo } from '../../api/emitent';
import type { BondDetail } from '../../types/bond';

interface BondIdentityProps {
  secid: string;
  detail: BondDetail | null;
  issuer: EmitentInfo | null;
}

export function BondIdentity({ secid, detail, issuer }: BondIdentityProps) {
  const securities = detail?.securities;
  const rows = [
    ['SECID', secid],
    ['Рег. номер облигации', securities?.REGNUMBER],
    ['Рег. номер выпуска', detail?.bond_description?.regnumber],
    ['', issuer?.emitent_title],
    ['ИНН эмитента', detail?.emitent_inn || issuer?.emitent_inn],
    ['ISIN', securities?.ISIN],
  ] as const;

  return <Box sx={{ my: 1, overflowWrap: 'anywhere' }}>
    {rows.map(([label, value]) => (
      <Typography key={label} component="div" variant="body2" fontWeight={label ? 400 : 600}>
        {label && <Box component="span" color="text.secondary">{label}: </Box>}
        {value == null || value === '' ? '—' : String(value)}
      </Typography>
    ))}
  </Box>;
}
