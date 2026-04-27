/**
 * Transparent proxy: all /api/* requests are forwarded to the FastAPI backend.
 * This handles both the Vite dev server proxy and production deployment.
 */
import type { RequestHandler } from './$types';

const API_BASE = process.env.API_URL ?? 'http://localhost:8000';

async function proxy(event: Parameters<RequestHandler>[0]): Promise<Response> {
	const { request, params, cookies } = event;
	const path = params.path;
	const url = new URL(request.url);
	const targetUrl = `${API_BASE}/api/${path}${url.search}`;

	const token = cookies.get('access_token');
	const headers = new Headers(request.headers);
	headers.delete('host');
	if (token) headers.set('Authorization', `Bearer ${token}`);

	const body = ['GET', 'HEAD'].includes(request.method) ? null : await request.arrayBuffer();

	const res = await fetch(targetUrl, {
		method: request.method,
		headers,
		body
	});

	return new Response(res.body, {
		status: res.status,
		headers: res.headers
	});
}

export const GET: RequestHandler = (e) => proxy(e);
export const POST: RequestHandler = (e) => proxy(e);
export const PUT: RequestHandler = (e) => proxy(e);
export const PATCH: RequestHandler = (e) => proxy(e);
export const DELETE: RequestHandler = (e) => proxy(e);
