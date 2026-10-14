export async function verifyBytes(bytes: ArrayBuffer, expected: string) {
  const hash = await crypto.subtle.digest('SHA-256', bytes);
  const actual = Array.from(new Uint8Array(hash), b => b.toString(16).padStart(2, '0')).join('');
  if (actual !== expected) throw new Error('Telemetry checksum mismatch; refusing stale or modified data');
}
