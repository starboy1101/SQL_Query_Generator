# Security policy

Please report suspected vulnerabilities privately to the project maintainers rather than opening a public issue.

The API treats language-model output as untrusted input. Generated SQL is parsed before execution, constrained to one
read-only `SELECT`, checked against the introspected table allowlist, denied access to qualified external schemas, and
given a server-controlled row limit. Direct SQL execution has a separate policy switch and is disabled by the public
Blueprint. Deployments should additionally use a database account with `SELECT` privileges only, terminate TLS at the
ingress, restrict network access, and keep generated-query execution disabled unless it is required.

For access-controlled deployments, keep `API_KEY` in a server-side proxy or BFF. Never put shared secrets in `VITE_*`
variables because they are bundled into public JavaScript. Anonymous demos should use synthetic data plus gateway-level
bot protection, distributed rate limits, request-size limits, and an inference budget. The included in-process limiter
is an additional single-instance safeguard, not a substitute for an edge abuse boundary.

Never place database credentials, model API tokens, production schemas, query contents, or customer data in issues,
logs, fixtures, model training examples, or committed `.env` files.
