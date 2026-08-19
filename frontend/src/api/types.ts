export type Dialect = 'sqlite' | 'postgres' | 'mysql' | 'tsql' | 'oracle';
export type CellValue = string | number | boolean | null;

export interface HealthResponse {
  status: 'ok' | 'degraded';
  version: string;
  checks: Record<string, boolean>;
}

export interface CapabilitiesResponse {
  dialect: Dialect;
  model: string;
  execution_enabled: boolean;
  default_max_rows: number;
  max_rows_cap: number;
  max_question_length: number;
}

export interface ColumnSchema {
  name: string;
  data_type: string;
  nullable: boolean;
  primary_key: boolean;
}

export interface ForeignKeySchema {
  columns: string[];
  referred_table: string;
  referred_columns: string[];
}

export interface TableSchema {
  name: string;
  kind: string;
  columns: ColumnSchema[];
  foreign_keys: ForeignKeySchema[];
}

export interface DatabaseSchemaResponse {
  dialect: Dialect;
  tables: TableSchema[];
}

export interface GenerateQueryRequest {
  question: string;
  max_rows: number;
  execute: boolean;
}

export interface ValidationInfo {
  read_only: boolean;
  tables: string[];
  applied_row_limit: number;
}

export interface QueryExecution {
  columns: string[];
  rows: Array<Record<string, CellValue>>;
  row_count: number;
  elapsed_ms: number;
}

export interface QueryResponse {
  request_id: string;
  question: string | null;
  sql: string;
  dialect: Dialect;
  model: string;
  validation: ValidationInfo;
  execution: QueryExecution | null;
  generation_ms: number;
}

export interface ApiErrorPayload {
  error: {
    code: string;
    message: string;
    request_id: string;
    details: Record<string, unknown>;
  };
}
