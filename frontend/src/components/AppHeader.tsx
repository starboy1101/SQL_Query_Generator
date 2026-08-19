import type { CapabilitiesResponse } from '../api/types';

export type ServiceState = 'checking' | 'ready' | 'degraded' | 'offline';

interface AppHeaderProps {
  capabilities: CapabilitiesResponse | null;
  serviceState: ServiceState;
}

const statusText: Record<ServiceState, string> = {
  checking: 'Checking API',
  ready: 'API ready',
  degraded: 'API degraded',
  offline: 'API offline',
};

export function AppHeader({ capabilities, serviceState }: AppHeaderProps) {
  return (
    <header className="app-header">
      <a className="brand" href="#top" aria-label="SQL Pilot home">
        <span className="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 32 32" focusable="false">
            <ellipse cx="16" cy="8" rx="9" ry="4" />
            <path d="M7 8v8c0 2.2 4 4 9 4s9-1.8 9-4V8M7 16v8c0 2.2 4 4 9 4s9-1.8 9-4v-8" />
          </svg>
        </span>
        <span>SQL Pilot</span>
      </a>

      <div className="header-context" aria-label="Service information">
        {capabilities && (
          <span className="context-pill">
            <span className="context-label">Dialect</span>
            {capabilities.dialect}
          </span>
        )}
        <span className={`status-pill status-${serviceState}`}>
          <span className="status-dot" aria-hidden="true" />
          {statusText[serviceState]}
        </span>
      </div>
    </header>
  );
}
