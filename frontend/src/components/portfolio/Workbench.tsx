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
type WorkbenchProps = {
  selectedModule?: WorkbenchModule;
  onSelectedModuleChange?: (module: WorkbenchModule) => void;
};

export const Workbench: React.FC<WorkbenchProps> = ({ selectedModule: controlledModule, onSelectedModuleChange }) => {
  const [internalSelectedModule, setInternalSelectedModule] = useState<WorkbenchModule>('HUB');
  const selectedModule = controlledModule ?? internalSelectedModule;

  const updateSelectedModule = (module: WorkbenchModule) => {
    if (controlledModule === undefined) {
      setInternalSelectedModule(module);
    }
    onSelectedModuleChange?.(module);
  };

  const handleModuleSelect = (module: WorkbenchModule) => {
    updateSelectedModule(module);
  };

  // Render HUB view when no module is selected
  if (selectedModule === 'HUB') {
    return <Hub onModuleSelect={handleModuleSelect} />;
  }

  // Render selected module with back button
  return (
    <Box sx={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {selectedModule === 'PORTFOLIO' && (
        <PortfolioModule />
      )}
      {selectedModule === 'CALENDAR' && (
        <CalendarModule />
      )}
      {selectedModule === 'ANALYTICS' && (
        <AnalyticsModule />
      )}
    </Box>
  );
};




