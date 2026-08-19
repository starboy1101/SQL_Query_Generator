import type {
  ApiErrorPayload,
  CapabilitiesResponse,
  DatabaseSchemaResponse,
  GenerateQueryRequest,
  HealthResponse,
  QueryResponse,
} from './types';

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() ?? '';
const API_BASE_URL = configuredBaseUrl.replace(/\/$/, '');

export class ApiClientError extends Error {
  readonly code: string;
  readonly requestId?: string;
  readonly status: number;

  constructor(message: string, code: string, status: number, requestId?: string) {
    super(message);
    this.name = 'ApiClientError';
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set('Accept', 'application/json');
  if (init?.body) {
    headers.set('Content-Type', 'application/json');
  }
  if (globalThis.crypto?.randomUUID) {
    headers.set('X-Request-ID', globalThis.crypto.randomUUID());
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiClientError('The request was cancelled.', 'request_cancelled', 0);
    }
    throw new ApiClientError(
      'The API is unreachable. Confirm that the FastAPI server is running.',
      'network_error',
      0,
    );
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const apiError = payload as ApiErrorPayload | null;
    throw new ApiClientError(
      apiError?.error?.message ?? `Request failed with status ${response.status}.`,
      apiError?.error?.code ?? 'unknown_error',
      response.status,
      apiError?.error?.request_id,
    );
  }
  return payload as T;
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>('/health/ready', { signal });
}

export function getCapabilities(signal?: AbortSignal): Promise<CapabilitiesResponse> {
  return request<CapabilitiesResponse>('/api/v1/capabilities', { signal });
}

export function getSchema(signal?: AbortSignal): Promise<DatabaseSchemaResponse> {
  return request<DatabaseSchemaResponse>('/api/v1/schema', { signal });
}

export function generateQuery(
  payload: GenerateQueryRequest,
  signal?: AbortSignal,
): Promise<QueryResponse> {
  return request<QueryResponse>('/api/v1/queries/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
    signal,
  });
}
