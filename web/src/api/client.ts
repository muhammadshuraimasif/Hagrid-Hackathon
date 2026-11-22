/**
 * Typed API Client for Project Amaanat.
 * 
 * Features:
 * - Automatically attaches Bearer token from localStorage
 * - Seamless automatic token refresh on HTTP 401
 * - Uniform error envelope extraction { code, message, request_id }
 * - Fail-closed error handling
 */

export interface ApiErrorEnvelope {
  code: string;
  message: string;
  request_id?: string;
  details?: any;
}

export class ApiError extends Error {
  code: string;
  requestId?: string;
  status: number;
  details?: any;

  constructor(status: number, envelope: ApiErrorEnvelope) {
    super(envelope.message || 'API request failed');
    this.name = 'ApiError';
    this.status = status;
    this.code = envelope.code || 'UNKNOWN_ERROR';
    this.requestId = envelope.request_id;
    this.details = envelope.details;
  }
}

const envApiUrl = typeof import.meta !== 'undefined' && import.meta.env ? import.meta.env.VITE_API_URL : undefined;
// In production builds the API is served from the same origin (Vercel routes /api/* to FastAPI).
const defaultApiUrl = import.meta.env && import.meta.env.PROD ? '' : 'http://127.0.0.1:8000';
const rawBaseUrl = (envApiUrl ?? defaultApiUrl).replace(/\/+$/, '');
const API_BASE_URL = rawBaseUrl.endsWith('/api/v1') ? rawBaseUrl : `${rawBaseUrl}/api/v1`;

export const getApiBaseUrl = (): string => API_BASE_URL;
export const getApiRootUrl = (): string => rawBaseUrl;

class ApiClient {
  private baseUrl: string = API_BASE_URL;

  getAccessToken(): string | null {
    return localStorage.getItem('access_token');
  }

  getRefreshToken(): string | null {
    return localStorage.getItem('refresh_token');
  }

  setTokens(access: string, refresh: string) {
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
  }

  clearTokens() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_role');
    localStorage.removeItem('user_email');
    localStorage.removeItem('tenant_id');
  }

  async refreshAuth(): Promise<boolean> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) return false;

    try {
      const res = await fetch(`${this.baseUrl}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!res.ok) {
        this.clearTokens();
        return false;
      }

      const data = await res.json();
      if (data.access_token && data.refresh_token) {
        this.setTokens(data.access_token, data.refresh_token);
        return true;
      }
      return false;
    } catch {
      this.clearTokens();
      return false;
    }
  }

  async request<T = any>(
    path: string,
    options: RequestInit = {},
    retryOn401: boolean = true
  ): Promise<T> {
    const url = path.startsWith('http') ? path : `${this.baseUrl}${path.startsWith('/') ? path : `/${path}`}`;
    const headers = new Headers(options.headers || {});

    const token = this.getAccessToken();
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`);
    }

    if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
    }

    let response: Response;
    try {
      response = await fetch(url, { ...options, headers });
    } catch (err: any) {
      throw new ApiError(0, {
        code: 'NETWORK_ERROR',
        message: 'Could not connect to Amaanat server. Please check your network connection.',
      });
    }

    // Handle 401 Token Expiration with 1 refresh retry
    if (response.status === 401 && retryOn401) {
      const refreshed = await this.refreshAuth();
      if (refreshed) {
        return this.request<T>(path, options, false);
      }
    }

    if (!response.ok) {
      let envelope: ApiErrorEnvelope = {
        code: `HTTP_${response.status}`,
        message: response.statusText || 'Request failed',
      };
      try {
        const body = await response.json();
        if (body.code || body.message) {
          envelope = body;
        } else if (body.detail) {
          envelope.message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
        }
      } catch {
        // Response was not JSON
      }
      throw new ApiError(response.status, envelope);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  // Common Convenience Methods
  get<T = any>(path: string, options?: RequestInit): Promise<T> {
    return this.request<T>(path, { ...options, method: 'GET' });
  }

  post<T = any>(path: string, body?: any, options?: RequestInit): Promise<T> {
    return this.request<T>(path, {
      ...options,
      method: 'POST',
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
  }

  put<T = any>(path: string, body?: any, options?: RequestInit): Promise<T> {
    return this.request<T>(path, {
      ...options,
      method: 'PUT',
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
  }

  delete<T = any>(path: string, options?: RequestInit): Promise<T> {
    return this.request<T>(path, { ...options, method: 'DELETE' });
  }
}

export const api = new ApiClient();
