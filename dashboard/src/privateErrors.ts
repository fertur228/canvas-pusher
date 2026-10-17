/** Safe diagnostics only: never expose PostgREST messages, details, URLs or tokens. */
export type PrivateScope = 'Accounts' | 'Health' | 'Delivery history' | 'Experiments' | 'Trigger' | 'Telemetry';
export class PrivateRequestError extends Error {
  constructor(readonly scope: PrivateScope, readonly status: number, readonly code?: string) {
    const safeCode = typeof code === 'string' && /^(?:[0-9A-Z]{5}|PGRST[0-9]{3})$/.test(code) ? code : undefined;
    const diagnostic = `HTTP ${status || 'unavailable'}${safeCode ? ` / ${safeCode}` : ''}`;
    let reason: string;
    if (status === 401 || safeCode === 'PGRST301' || safeCode === 'PGRST303') reason = 'Authentication expired or invalid. Sign out and sign in again.';
    else if (status === 403 || safeCode === '42501') reason = 'Access denied. Verify owner authorization and RLS.';
    else if (['42703', '42P01', 'PGRST200', 'PGRST202', 'PGRST204'].includes(safeCode || '')) reason = 'Database schema/query mismatch. Contact the maintainer; signing in again will not fix this query.';
    else if (status >= 500) reason = 'Database service unavailable. Retry later.';
    else if (!status) reason = 'Network request failed. Check your connection and retry.';
    else reason = 'Database request failed. Contact the maintainer with this diagnostic.';
    super(`${scope}: ${reason} (${diagnostic})`);
    this.name = 'PrivateRequestError';
    this.code = safeCode;
  }
}

export function privateErrorMessage(error: unknown, fallback = 'Private data could not be loaded. Retry or contact the maintainer.') {
  return error instanceof PrivateRequestError ? error.message : fallback;
}

export async function responseError(scope: PrivateScope, response: Response) {
  let code: string | undefined;
  try { const body = await response.json(); if (typeof body?.code === 'string') code = body.code; } catch { /* HTTP status remains useful. */ }
  return new PrivateRequestError(scope, response.status, code);
}
