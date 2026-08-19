import { useEffect, useRef, useState } from 'react';

import { ApiClientError } from '../api/client';
import type { CellValue, QueryResponse } from '../api/types';

interface QueryResultProps {
  result: QueryResponse | null;
  error: ApiClientError | null;
  isLoading: boolean;
}

function formatCell(value: CellValue): string {
  if (value === null) return 'NULL';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  return String(value);
}

export function QueryResult({ result, error, isLoading }: QueryResultProps) {
  const [copied, setCopied] = useState(false);
  const errorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  if (isLoading) {
    return (
      <section className="result-card result-loading" aria-live="polite" aria-busy="true">
        <span className="processing-orbit" aria-hidden="true"><span /></span>
        <div>
          <h2>Turning your question into SQL</h2>
          <p>Generating, validating, and applying safety controls…</p>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="result-card error-card" ref={errorRef} tabIndex={-1} role="alert">
        <span className="error-icon" aria-hidden="true">!</span>
        <div>
          <span className="step-label">Request failed</span>
          <h2>{error.message}</h2>
          <p>
            Error code: <code>{error.code}</code>
            {error.requestId && <> · Request ID: <code>{error.requestId}</code></>}
          </p>
        </div>
      </section>
    );
  }

  if (!result) {
    return (
      <section className="result-card empty-result">
        <div className="empty-visual" aria-hidden="true">
          <span>SELECT</span>
          <span>FROM</span>
          <span>WHERE</span>
        </div>
        <div>
          <span className="step-label">02 / Inspect</span>
          <h2>Your generated query will appear here</h2>
          <p>Every query is parsed and checked before it can touch the database.</p>
        </div>
      </section>
    );
  }

  const execution = result.execution;

  async function copySql() {
    try {
      await navigator.clipboard.writeText(result?.sql ?? '');
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <section className="result-stack" aria-live="polite">
      <div className="result-card sql-card">
        <div className="result-heading">
          <div>
            <span className="step-label">02 / Generated SQL</span>
            <h2>Validated query</h2>
          </div>
          <button className="copy-button" type="button" onClick={copySql}>
            {copied ? 'Copied' : 'Copy SQL'}
          </button>
        </div>
        <pre aria-label="Generated SQL"><code>{result.sql}</code></pre>
        <div className="validation-strip">
          <span><strong>✓</strong> Read only</span>
          <span><strong>✓</strong> {result.validation.tables.join(', ') || 'No table access'}</span>
          <span><strong>≤</strong> {result.validation.applied_row_limit} rows</span>
        </div>
      </div>

      {execution && (
        <div className="result-card data-card">
          <div className="result-heading">
            <div>
              <span className="step-label">03 / Results</span>
              <h2>{execution.row_count.toLocaleString()} {execution.row_count === 1 ? 'row' : 'rows'} returned</h2>
            </div>
            <span className="latency-badge">{execution.elapsed_ms.toFixed(2)} ms DB</span>
          </div>

          {execution.rows.length > 0 ? (
            <div className="table-scroll" tabIndex={0} aria-label="Scrollable query results">
              <table>
                <caption className="sr-only">Results for: {result.question}</caption>
                <thead>
                  <tr>{execution.columns.map((column) => <th scope="col" key={column}>{column}</th>)}</tr>
                </thead>
                <tbody>
                  {execution.rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {execution.columns.map((column) => (
                        <td key={column} className={row[column] === null ? 'null-cell' : ''}>
                          {formatCell(row[column] ?? null)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="no-rows">The query ran successfully but returned no rows.</p>
          )}
        </div>
      )}

      <div className="query-metadata" aria-label="Query metadata">
        <span><small>Model</small>{result.model}</span>
        <span><small>Total latency</small>{result.generation_ms.toFixed(2)} ms</span>
        <span><small>Dialect</small>{result.dialect}</span>
        <span className="request-id"><small>Request ID</small>{result.request_id}</span>
      </div>
    </section>
  );
}
