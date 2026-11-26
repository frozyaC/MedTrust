export class ApiError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message);
    this.name = 'ApiError';
  }
}

export function apiBaseUrl(): string {
  return (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/+$/, '');
}

export async function apiFetch(
  input: string,
  init: RequestInit = {},
  handleAccess = true,
): Promise<Response> {
  const response = await fetch(input, { ...init, credentials: 'include' });
  if (handleAccess && (response.status === 401 || response.status === 403)) {
    window.dispatchEvent(new Event(response.status === 401 ? 'medtrust:unauthorized' : 'medtrust:forbidden'));
    throw new ApiError(
      response.status === 401 ? 'Сессия истекла. Войдите снова' : 'Доступ запрещён',
      response.status,
    );
  }
  return response;
}

export async function responseError(response: Response): Promise<ApiError> {
  const data = await response.json().catch(() => null);
  const detail = data?.detail;
  const message = typeof detail === 'string' ? detail
    : Array.isArray(detail) ? detail.map((item: { msg?: string }) => item.msg ?? 'Некорректные данные').join('; ')
    : `Ошибка запроса: ${response.status}`;
  return new ApiError(message, response.status);
}
