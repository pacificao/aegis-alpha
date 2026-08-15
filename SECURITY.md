# Security policy

Do not report vulnerabilities, credentials, personal data, or infrastructure details in a public issue or discussion.

Report security concerns privately through GitHub's **Report a vulnerability** feature for this repository. Include reproduction steps and impact, but never include a real password, brokerage credential, session cookie, private key, or production token.

This repository must contain only templates and non-secret source. Deployment secrets, OAuth material, database contents, backups, certificates, host identifiers, and operator-specific configuration belong outside Git in access-controlled deployment storage. A leaked credential is treated as compromised and must be revoked or rotated; deleting a file or commit is not sufficient.

Only maintained revisions on `main` are eligible for security fixes. No public disclosure timeline or bounty is promised unless separately agreed in writing.
