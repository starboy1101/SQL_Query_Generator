import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import App from './App';

const health = {
  status: 'ok',
  version: '1.0.0',
  checks: { database: true, schema: true, model_configured: true },
};

const capabilities = {
  dialect: 'sqlite',
  model: 'heuristic-development-backend',
  execution_enabled: true,
  default_max_rows: 50,
  max_rows_cap: 100,
  max_question_length: 2000,
};

const schema = {
  dialect: 'sqlite',
  tables: [
    {
      name: 'customers',
      kind: 'table',
      columns: [
        { name: 'id', data_type: 'INTEGER', nullable: false, primary_key: true },
        { name: 'name', data_type: 'TEXT', nullable: false, primary_key: false },
      ],
      foreign_keys: [],
    },
  ],
};

const queryResult = {
  request_id: 'request-123',
  question: 'How many customers are there?',
  sql: 'SELECT COUNT(*) AS count FROM "customers" LIMIT 50',
  dialect: 'sqlite',
  model: 'heuristic-development-backend',
  validation: { read_only: true, tables: ['customers'], applied_row_limit: 50 },
  execution: { columns: ['count'], rows: [{ count: 2 }], row_count: 1, elapsed_ms: 0.75 },
  generation_ms: 12.5,
};

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('SQL Pilot application', () => {
  it('loads the schema and completes a natural-language query', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path.endsWith('/health/ready')) return jsonResponse(health);
      if (path.endsWith('/api/v1/capabilities')) return jsonResponse(capabilities);
      if (path.endsWith('/api/v1/schema')) return jsonResponse(schema);
      if (path.endsWith('/api/v1/queries/generate')) return jsonResponse(queryResult);
      throw new Error(`Unexpected request: ${path} ${init?.method ?? 'GET'}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    expect(await screen.findByText('customers')).toBeInTheDocument();
    expect(screen.getByText('API ready')).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'How many customers are there?' }));
    await user.click(screen.getByRole('button', { name: /Generate SQL/i }));

    expect(await screen.findByText('Validated query')).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: '2' })).toBeInTheDocument();
    expect(screen.getByText('request-123')).toBeInTheDocument();

    const generationCall = fetchMock.mock.calls.find(([input]) =>
      String(input).endsWith('/api/v1/queries/generate'),
    );
    expect(generationCall).toBeDefined();
    expect(JSON.parse(String(generationCall?.[1]?.body))).toEqual({
      question: 'How many customers are there?',
      max_rows: 50,
      execute: true,
    });
  });

  it('shows a stable API error and request identifier', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith('/health/ready')) return jsonResponse(health);
      if (path.endsWith('/api/v1/capabilities')) return jsonResponse(capabilities);
      if (path.endsWith('/api/v1/schema')) return jsonResponse(schema);
      return jsonResponse(
        {
          error: {
            code: 'rate_limit_exceeded',
            message: 'Too many requests. Please wait before trying again.',
            request_id: 'rate-limit-request',
            details: { retry_after_seconds: 30 },
          },
        },
        429,
      );
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    const user = userEvent.setup();
    const input = await screen.findByLabelText('Database question in plain English');
    await user.type(input, 'List all products');
    await user.click(screen.getByRole('button', { name: /Generate SQL/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Too many requests');
    expect(screen.getByRole('alert')).toHaveTextContent('rate-limit-request');
  });

  it('validates an empty question without sending a request', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith('/health/ready')) return jsonResponse(health);
      if (path.endsWith('/api/v1/capabilities')) return jsonResponse(capabilities);
      return jsonResponse(schema);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByText('customers')).toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: /Generate SQL/i }));

    expect(screen.getByText('Enter a question with at least 3 characters.')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
