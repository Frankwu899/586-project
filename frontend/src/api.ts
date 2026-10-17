export class ApiError extends Error {
  constructor(message: string, public readonly status: number, public readonly code?: string) {
    super(message);
  }
}

export async function request<T>(path: string, body?: unknown): Promise<T> {
  const isFile = body instanceof FormData;
  const response = await fetch(`/api${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined || isFile ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : isFile ? body : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail ?? data.error ?? data;
    const message = typeof detail === 'string' ? detail : Array.isArray(detail)
      ? detail.map((item: { msg?: string }) => item.msg ?? 'Invalid input').join('; ')
      : detail.message ?? 'The operation could not be completed.';
    throw new ApiError(message, response.status, typeof detail === 'object' && !Array.isArray(detail) ? detail.code : undefined);
  }
  return data as T;
}
