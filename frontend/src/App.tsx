import { useEffect, useRef, useState } from 'react';

import { ApiClientError, generateQuery, getCapabilities, getHealth, getSchema } from './api/client';
import type {
  CapabilitiesResponse,
  DatabaseSchemaResponse,
  GenerateQueryRequest,
  QueryResponse,
} from './api/types';
import { AppHeader, type ServiceState } from './components/AppHeader';
import { QueryComposer } from './components/QueryComposer';
import { QueryResult } from './components/QueryResult';
import { SchemaExplorer } from './components/SchemaExplorer';

export default function App() {
  const [capabilities, setCapabilities] = useState<CapabilitiesResponse | null>(null);
  const [schema, setSchema] = useState<DatabaseSchemaResponse | null>(null);
  const [schemaError, setSchemaError] = useState('');
  const [serviceState, setServiceState] = useState<ServiceState>('checking');
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [queryError, setQueryError] = useState<ApiClientError | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const activeRequest = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    getHealth(controller.signal)
      .then((health) => setServiceState(health.status === 'ok' ? 'ready' : 'degraded'))
      .catch(() => setServiceState('offline'));

    Promise.all([getCapabilities(controller.signal), getSchema(controller.signal)])
      .then(([capabilityResponse, schemaResponse]) => {
        setCapabilities(capabilityResponse);
        setSchema(schemaResponse);
      })
      .catch((error: unknown) => {
        if (error instanceof ApiClientError && error.code !== 'request_cancelled') {
          setSchemaError(error.message);
        }
      });

    return () => controller.abort();
  }, []);

  async function submitQuery(payload: GenerateQueryRequest) {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setIsSubmitting(true);
    setQueryError(null);
    setResult(null);

    try {
      const response = await generateQuery(payload, controller.signal);
      setResult(response);
      setServiceState('ready');
    } catch (error) {
      if (error instanceof ApiClientError && error.code !== 'request_cancelled') {
        setQueryError(error);
        if (error.code === 'network_error') setServiceState('offline');
      }
    } finally {
      if (activeRequest.current === controller) {
        setIsSubmitting(false);
        activeRequest.current = null;
      }
    }
  }

  return (
    <div id="top" className="app-shell">
      <AppHeader capabilities={capabilities} serviceState={serviceState} />

      <main>
        <section className="hero" aria-labelledby="page-title">
          <div className="hero-copy">
            <span className="eyebrow"><span /> Schema-aware AI workspace</span>
            <h1 id="page-title">Ask your database.<br /><em>Get safe SQL.</em></h1>
            <p>
              Turn plain English into validated, read-only queries—grounded in the schema that is actually available.
            </p>
          </div>
          <div className="safety-summary" aria-label="Safety controls">
            <span><strong>01</strong> Schema grounded</span>
            <span><strong>02</strong> AST validated</span>
            <span><strong>03</strong> Read only</span>
          </div>
        </section>

        <div className="workspace-grid">
          <div className="main-workspace">
            <QueryComposer
              capabilities={capabilities}
              isSubmitting={isSubmitting}
              onSubmit={submitQuery}
            />
            <QueryResult result={result} error={queryError} isLoading={isSubmitting} />
          </div>
          <SchemaExplorer
            schema={schema}
            isLoading={!schema && !schemaError}
            errorMessage={schemaError || undefined}
          />
        </div>
      </main>

      <footer>
        <span>SQL Pilot</span>
        <p>Model output is untrusted until it passes the SQL safety boundary.</p>
        <a href="/openapi.json">OpenAPI</a>
      </footer>
    </div>
  );
}
