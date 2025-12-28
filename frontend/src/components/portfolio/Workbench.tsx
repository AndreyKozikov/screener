import React, { useState } from 'react';
import { Box } from '@mui/material';
import { Hub } from './Hub';
import { PortfolioModule } from './PortfolioModule';
import { CalendarModule } from './CalendarModule';
import { AnalyticsModule } from './AnalyticsModule';

export type WorkbenchModule = 'HUB' | 'PORTFOLIO' | 'CALENDAR' | 'ANALYTICS';

/**
 * Workbench Component
 * 
 * Main component managing the Portfolio Workbench state
 * Controls which module is currently displayed
 */
export const Workbench: React.FC = () => {
  const [selectedModule, setSelectedModule] = useState<WorkbenchModule>('HUB');

  const handleModuleSelect = (module: WorkbenchModule) => {
    setSelectedModule(module);
  };

  const handleBackToHub = () => {
    setSelectedModule('HUB');
  };

  // Render HUB view when no module is selected
  if (selectedModule === 'HUB') {
    return <Hub onModuleSelect={handleModuleSelect} />;
  }

  // Render selected module with back button
  return (
    <Box sx={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {selectedModule === 'PORTFOLIO' && (
        <PortfolioModule onBack={handleBackToHub} />
      )}
      {selectedModule === 'CALENDAR' && (
        <CalendarModule onBack={handleBackToHub} />
      )}
      {selectedModule === 'ANALYTICS' && (
        <AnalyticsModule onBack={handleBackToHub} />
      )}
    </Box>
  );
};

