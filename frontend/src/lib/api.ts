import type {
  Me,
  NotebookCreate,
  NotebookDetail,
  NotebookSummary,
  NotebookUpdate,
  NotebookVersionInfo,
  PublishResponse
} from './types';

class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...init,
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers
    }
  });
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      /* ignore */
    }
    const detailObj = detail as { detail?: string } | null;
    const message =
      (detailObj && typeof detailObj.detail === 'string' && detailObj.detail) ||
      `${res.status} ${res.statusText}`;
    throw new ApiError(res.status, message, detail);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export const api = {
  me: () => request<Me>('/api/me'),

  listNotebooks: (params: { mine?: boolean } = {}) => {
    const qs = new URLSearchParams();
    if (params.mine) qs.set('mine', 'true');
    const q = qs.toString();
    return request<NotebookSummary[]>(`/api/notebooks${q ? `?${q}` : ''}`);
  },
  getNotebook: (id: string) => request<NotebookDetail>(`/api/notebooks/${id}`),
  createNotebook: (payload: NotebookCreate) =>
    request<NotebookDetail>('/api/notebooks', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  updateNotebook: (id: string, payload: NotebookUpdate) =>
    request<NotebookDetail>(`/api/notebooks/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    }),
  deleteNotebook: (id: string) =>
    request<void>(`/api/notebooks/${id}`, { method: 'DELETE' }),
  publishNotebook: (id: string) =>
    request<PublishResponse>(`/api/notebooks/${id}/publish`, { method: 'POST' }),
  unpublishNotebook: (id: string) =>
    request<void>(`/api/notebooks/${id}/unpublish`, { method: 'POST' }),
  listVersions: (id: string) =>
    request<NotebookVersionInfo[]>(`/api/notebooks/${id}/versions`)
};

export { ApiError };
