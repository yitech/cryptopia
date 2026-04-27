import type { Handle } from '@sveltejs/kit';

const API_BASE = process.env.API_URL ?? 'http://localhost:8000';

export const handle: Handle = async ({ event, resolve }) => {
	const token = event.cookies.get('access_token');

	if (token) {
		try {
			const res = await fetch(`${API_BASE}/api/auth/me`, {
				headers: { Authorization: `Bearer ${token}` }
			});
			if (res.ok) {
				event.locals.user = await res.json();
			} else {
				event.cookies.delete('access_token', { path: '/' });
				event.locals.user = null;
			}
		} catch {
			event.locals.user = null;
		}
	} else {
		event.locals.user = null;
	}

	return resolve(event);
};
