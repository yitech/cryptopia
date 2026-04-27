import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

const API_BASE = process.env.API_URL ?? 'http://localhost:8000';

export const load: PageServerLoad = async ({ params }) => {
	const res = await fetch(`${API_BASE}/api/auth/profile/${params.username}`);
	if (res.status === 404) throw error(404, 'User not found');
	if (!res.ok) throw error(500, 'Failed to load profile');

	const profile = await res.json();
	return { profile };
};
