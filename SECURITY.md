# Security policy

Please report suspected vulnerabilities privately to the project maintainers rather than opening a public issue.

The API treats language-model output as untrusted input. Generated SQL is parsed before execution, constrained to one
read-only `SELECT`, checked against the introspected table allowlist, denied access to qualified external schemas, and
given a server-controlled row limit. Deployments should additionally use a database account with `SELECT` privileges
only, set `API_KEY`, terminate TLS at the ingress, restrict network access, and keep query execution disabled unless it
is required.

Never place database credentials, model API tokens, production schemas, query contents, or customer data in issues,
logs, fixtures, model training examples, or committed `.env` files.
