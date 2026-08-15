# ADR: Content Security Policy for the Next.js console

Status: temporary Phase 1 compatibility decision.

## Problem

Nginx originally sent `script-src 'self'`. The Next.js 15 App Router response includes inline React Server Component bootstrap scripts (`self.__next_f`), so browsers refused to execute hydration data. Static assets and server-rendered HTML returned HTTP 200, but client authentication handling never ran and the page remained on its dark loading shell.

## Phase 1 decision

Allow inline scripts with `script-src 'self' 'unsafe-inline'`. Script files must remain same-origin. `unsafe-eval` and external script origins are not allowed, and the remaining default, image, connection, frame, base, and form restrictions stay in place. This is a development compatibility concession, not the production target.

## Production recommendation

Before production, generate a cryptographically random nonce per response, attach it to every permitted Next.js bootstrap/script element, and emit it in `script-src`. Validate against production builds and streamed App Router responses, then remove `unsafe-inline`. Hashes are less suitable because bootstrap payloads vary by response.
