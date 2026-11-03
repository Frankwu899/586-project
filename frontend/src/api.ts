export class ApiError extends Error {
  constructor(message: string, public readonly status: number, public readonly code?: string) {
    super(message);
  }
}

export function operationErrorMessage(failure: unknown): string {
  const message = failure instanceof Error ? failure.message : 'The operation failed.';
  const versionConflict = failure instanceof ApiError && ['version_conflict', 'm2_draft_conflict', 'editor_draft_conflict', 'structure_version_conflict', 'stale_result'].includes(failure.code ?? '');
  return `${message}${versionConflict ? ' Your draft is retained. Reopen the saved project to review the latest version.' : ''}`;
}

export async function request<T>(path: string, body?: unknown): Promise<T> {
  const match = body !== undefined && !(body instanceof FormData) ? path.match(/^\/tasks\/([^/]+)\/(recognize|directions\/generate|directions\/([^/]+)\/refine|outputs\/generate)$/) : null;
  if (match) {
    const operation = match[2] === 'recognize' ? 'recognize' : match[2] === 'directions/generate' ? 'directions' : match[3] ? 'refine' : 'production';
    type Ticket = { operation_id: string; status: string; result: T | null; error: { code: string; message: string } | null };
    const payload = { ...(body as Record<string, unknown>), ...(match[3] ? { direction_id: match[3] } : {}) };
    let ticket = await request<Ticket>(`/tasks/${match[1]}/operations`, { operation, payload });
    while (ticket.status === 'queued' || ticket.status === 'running') {
      await new Promise((resolve) => setTimeout(resolve, 700));
      ticket = await request<Ticket>(`/tasks/${match[1]}/operations/${ticket.operation_id}`);
    }
    if (ticket.error) throw new ApiError(ticket.error.message, 409, ticket.error.code);
    if (!ticket.result) throw new ApiError('The operation finished without a saved result. Reopen the task.', 502);
    return ticket.result;
  }
  const isFile = body instanceof FormData;
  const response = await fetch(`/api${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'X-Video-Anatomy-Request': '1', ...(body === undefined || isFile ? {} : { 'Content-Type': 'application/json' }) },
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
