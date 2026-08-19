import { useEffect, useState } from 'react';

import type { CapabilitiesResponse, GenerateQueryRequest } from '../api/types';

const EXAMPLES = [
  'How many customers are there?',
  'List all products',
  'What is the average total amount in orders?',
  'What is the highest unit price in products?',
];

interface QueryComposerProps {
  capabilities: CapabilitiesResponse | null;
  isSubmitting: boolean;
  onSubmit: (payload: GenerateQueryRequest) => void;
}

export function QueryComposer({ capabilities, isSubmitting, onSubmit }: QueryComposerProps) {
  const [question, setQuestion] = useState('');
  const [maxRows, setMaxRows] = useState(100);
  const [execute, setExecute] = useState(true);
  const [validationMessage, setValidationMessage] = useState('');

  useEffect(() => {
    if (capabilities) {
      setMaxRows(Math.min(capabilities.default_max_rows, capabilities.max_rows_cap));
      setExecute(capabilities.execution_enabled);
    }
  }, [capabilities]);

  const maxQuestionLength = capabilities?.max_question_length ?? 2000;
  const maxRowsCap = capabilities?.max_rows_cap ?? 1000;
  const rowOptions = Array.from(
    new Set([10, 25, 50, 100, capabilities?.default_max_rows ?? 100]),
  )
    .filter((value) => value <= maxRowsCap)
    .sort((left, right) => left - right);

  function submit() {
    const cleanQuestion = question.trim();
    if (cleanQuestion.length < 3) {
      setValidationMessage('Enter a question with at least 3 characters.');
      return;
    }
    setValidationMessage('');
    onSubmit({
      question: cleanQuestion,
      max_rows: Math.min(maxRows, maxRowsCap),
      execute: execute && Boolean(capabilities?.execution_enabled),
    });
  }

  return (
    <section className="composer-card" aria-labelledby="composer-title">
      <div className="section-heading">
        <div>
          <span className="step-label">01 / Ask</span>
          <h2 id="composer-title">What do you want to know?</h2>
        </div>
        <span className="shortcut-hint" aria-hidden="true">
          Ctrl ↵
        </span>
      </div>

      <label className="sr-only" htmlFor="question">
        Database question in plain English
      </label>
      <textarea
        id="question"
        className="question-input"
        value={question}
        onChange={(event) => {
          setQuestion(event.target.value);
          if (validationMessage) setValidationMessage('');
        }}
        onKeyDown={(event) => {
          if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
            event.preventDefault();
            if (!isSubmitting) submit();
          }
        }}
        placeholder="e.g. How many customers are there?"
        maxLength={maxQuestionLength}
        rows={4}
        aria-describedby="question-help question-error"
        aria-invalid={Boolean(validationMessage)}
      />
      <div className="input-meta">
        <span id="question-help">Use table and column names when you know them.</span>
        <span>{question.length.toLocaleString()} / {maxQuestionLength.toLocaleString()}</span>
      </div>
      {validationMessage && (
        <p className="field-error" id="question-error" role="alert">
          {validationMessage}
        </p>
      )}

      <div className="example-list" aria-label="Example questions">
        {EXAMPLES.map((example) => (
          <button key={example} type="button" className="example-chip" onClick={() => setQuestion(example)}>
            {example}
          </button>
        ))}
      </div>

      <div className="composer-actions">
        <div className="query-options">
          <label className="select-label" htmlFor="max-rows">
            Max rows
            <select
              id="max-rows"
              value={maxRows}
              onChange={(event) => setMaxRows(Number(event.target.value))}
            >
              {rowOptions.map((value) => (
                <option value={value} key={value}>{value}</option>
              ))}
            </select>
          </label>

          <label className={`toggle-label ${!capabilities?.execution_enabled ? 'toggle-disabled' : ''}`}>
            <input
              type="checkbox"
              checked={execute}
              disabled={!capabilities?.execution_enabled}
              onChange={(event) => setExecute(event.target.checked)}
            />
            <span className="toggle-track" aria-hidden="true"><span /></span>
            Run safely
          </label>
        </div>

        <button type="button" className="generate-button" disabled={isSubmitting} onClick={submit}>
          {isSubmitting ? (
            <><span className="spinner" aria-hidden="true" /> Generating</>
          ) : (
            <>
              Generate SQL
              <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m7 4 6 6-6 6" /></svg>
            </>
          )}
        </button>
      </div>

      {!capabilities?.execution_enabled && capabilities && (
        <p className="policy-note">Execution is disabled by server policy. SQL will still be generated and validated.</p>
      )}
    </section>
  );
}
