import { useMemo, useState } from 'react';

import type { DatabaseSchemaResponse } from '../api/types';

interface SchemaExplorerProps {
  schema: DatabaseSchemaResponse | null;
  isLoading: boolean;
  errorMessage?: string;
}

export function SchemaExplorer({ schema, isLoading, errorMessage }: SchemaExplorerProps) {
  const [search, setSearch] = useState('');
  const normalizedSearch = search.trim().toLowerCase();
  const tables = useMemo(
    () =>
      schema?.tables.filter(
        (table) =>
          table.name.toLowerCase().includes(normalizedSearch) ||
          table.columns.some((column) => column.name.toLowerCase().includes(normalizedSearch)),
      ) ?? [],
    [normalizedSearch, schema],
  );

  return (
    <aside className="schema-card" aria-labelledby="schema-title">
      <div className="schema-header">
        <div>
          <span className="step-label">Live context</span>
          <h2 id="schema-title">Database schema</h2>
        </div>
        {schema && <span className="table-count">{schema.tables.length} tables</span>}
      </div>

      <label className="schema-search">
        <span className="sr-only">Search tables and columns</span>
        <svg viewBox="0 0 20 20" aria-hidden="true">
          <circle cx="8.5" cy="8.5" r="5.5" />
          <path d="m13 13 4 4" />
        </svg>
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search schema"
        />
      </label>

      <div className="schema-list">
        {isLoading && Array.from({ length: 3 }, (_, index) => (
          <div className="schema-skeleton" key={index} aria-hidden="true">
            <span /><span />
          </div>
        ))}

        {errorMessage && <p className="schema-message">{errorMessage}</p>}

        {!isLoading && !errorMessage && tables.map((table, index) => (
          <details className="schema-table" key={table.name} open={index === 0 && !normalizedSearch}>
            <summary>
              <span className="table-icon" aria-hidden="true">
                <svg viewBox="0 0 20 20"><ellipse cx="10" cy="5" rx="6" ry="2.5" /><path d="M4 5v5c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5V5M4 10v5c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5v-5" /></svg>
              </span>
              <span className="table-name">{table.name}</span>
              <span className="column-count">{table.columns.length}</span>
              <svg className="chevron" viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg>
            </summary>
            <ul className="column-list">
              {table.columns.map((column) => (
                <li key={column.name}>
                  <span className="column-name">
                    {column.name}
                    {column.primary_key && <span className="key-badge" title="Primary key">PK</span>}
                  </span>
                  <span className="column-type">{column.data_type}</span>
                </li>
              ))}
            </ul>
            {table.foreign_keys.length > 0 && (
              <div className="foreign-keys">
                {table.foreign_keys.map((key) => (
                  <span key={`${key.columns.join(',')}-${key.referred_table}`}>
                    {key.columns.join(', ')} → {key.referred_table}.{key.referred_columns.join(', ')}
                  </span>
                ))}
              </div>
            )}
          </details>
        ))}

        {!isLoading && !errorMessage && schema && tables.length === 0 && (
          <p className="schema-message">No tables or columns match “{search}”.</p>
        )}
      </div>

      <div className="schema-footer">
        <span className="read-only-icon" aria-hidden="true">✓</span>
        Only allowlisted metadata is shared with the model
      </div>
    </aside>
  );
}
