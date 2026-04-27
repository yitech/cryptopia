import type { PageServerLoad } from './$types';

const API_BASE = process.env.API_URL ?? 'http://localhost:8000';

export const load: PageServerLoad = async ({ url }) => {
	const page = Number(url.searchParams.get('page') ?? '1');
	const q = url.searchParams.get('q') ?? '';

	const params = new URLSearchParams({ page: String(page), per_page: '12' });
	if (q) params.set('q', q);

	const res = await fetch(`${API_BASE}/api/pages?${params}`);
	if (!res.ok) return { pages: [], total: 0, page, q };

	const data = await res.json();
	return { pages: data.items, total: data.total, page, q };
};
