import { error, redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

// Internal URL — used for server-side fetches (resolves the Docker hostname).
const API_BASE = process.env.API_URL ?? 'http://localhost:8000';
// Public URL — kept for any widget that still consults `apiBase`. Runtime
// calls go through the SvelteKit proxy at /api/...
const PUBLIC_API_BASE = process.env.PUBLIC_API_URL ?? 'http://localhost:8000';

export const load: PageServerLoad = async ({ params, locals, cookies }) => {
	if (!locals.user) throw redirect(303, '/login');

	const token = cookies.get('access_token');
	const res = await fetch(`${API_BASE}/api/pages/id/${params.id}`, {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (res.status === 404) throw error(404, 'Page not found');
	if (res.status === 403) throw error(403, 'You are not the author of this page');
	if (!res.ok) throw error(500, 'Failed to load page');

	const page = await res.json();
	return { page, apiBase: PUBLIC_API_BASE, user: locals.user };
};
