import React from 'react';
import {
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Button,
  List,
  ListItem,
  ListItemText,
  Typography,
} from '@mui/material';
import type { ImportedPortfolioSummary } from '../../api/portfolioReportImport';

interface ImportedPortfolioListDialogProps {
  open: boolean;
  portfolios: ImportedPortfolioSummary[];
  onClose: () => void;
}

export const ImportedPortfolioListDialog: React.FC<ImportedPortfolioListDialogProps> = ({
  open,
  portfolios,
  onClose,
}) => (
  <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
    <DialogTitle>Портфели из брокерских отчётов</DialogTitle>
    <DialogContent dividers>
      {portfolios.length === 0 ? (
        <Typography color="text.secondary">Импортированных портфелей пока нет.</Typography>
      ) : (
        <List disablePadding>
          {portfolios.map((portfolio) => {
            const summary = portfolio.records_summary;
            const period = portfolio.report_period_start && portfolio.report_period_end
              ? `${portfolio.report_period_start} — ${portfolio.report_period_end}`
              : 'Период не определён';
            const counts = `бумаг ${summary.securities ?? 0} · сделок ${summary.trades ?? 0} · денежных операций ${summary.cash_operations ?? 0} · выплат ${summary.income_payments ?? 0}`;
            return (
              <ListItem key={portfolio.portfolio_id} divider alignItems="flex-start">
                <ListItemText
                  primary={portfolio.portfolio_name}
                  secondary={(
                    <>
                      <Typography component="span" variant="body2" color="text.secondary" display="block">
                        {period} · {portfolio.source_file_name}
                      </Typography>
                      <Typography component="span" variant="body2" color="text.secondary" display="block">
                        {counts}
                      </Typography>
                    </>
                  )}
                />
              </ListItem>
            );
          })}
        </List>
      )}
    </DialogContent>
    <DialogActions>
      <Button onClick={onClose}>Закрыть</Button>
    </DialogActions>
  </Dialog>
);
