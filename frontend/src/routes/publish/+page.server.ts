import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

const API_BASE = process.env.API_URL ?? 'http://localhost:8000';

export const load: PageServerLoad = async ({ locals, cookies }) => {
	if (!locals.user) throw redirect(303, '/login');

	const token = cookies.get('access_token');
	const res = await fetch(`${API_BASE}/api/pages/my`, {
		headers: { Authorization: `Bearer ${token}` }
	});

	const myPages = res.ok ? await res.json() : [];
	return { user: locals.user, myPages };
};
