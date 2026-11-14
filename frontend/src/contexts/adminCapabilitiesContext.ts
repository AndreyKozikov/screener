import { createContext, useContext } from 'react';
import { NO_ADMIN_CAPABILITIES, type AdminCapabilities } from '../utils/auth';

export const AdminCapabilitiesContext = createContext<AdminCapabilities>(NO_ADMIN_CAPABILITIES);

export const useAdminCapabilities = (): AdminCapabilities => useContext(AdminCapabilitiesContext);
