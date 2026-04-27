import { fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';

const API_BASE = process.env.API_URL ?? 'http://localhost:8000';

export const load: PageServerLoad = ({ locals }) => {
	if (locals.user) throw redirect(303, '/');
	return {};
};

export const actions: Actions = {
	default: async ({ request, cookies }) => {
		const data = await request.formData();
		const username = data.get('username')?.toString();
		const password = data.get('password')?.toString();

		if (!username || !password) {
			return fail(400, { error: 'Username and password are required.' });
		}

		const body = new URLSearchParams({ username, password });
		let res: Response;
		try {
			res = await fetch(`${API_BASE}/api/auth/token`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
				body: body.toString()
			});
		} catch {
			return fail(503, { error: 'Cannot reach the server. Please try again.' });
		}

		if (!res.ok) {
			const json = await res.json().catch(() => ({}));
			return fail(res.status, { error: json.detail ?? 'Invalid credentials.' });
		}

		const { access_token } = await res.json();
		cookies.set('access_token', access_token, {
			path: '/',
			httpOnly: true,
			sameSite: 'lax',
			maxAge: 60 * 60 * 24 * 7
		});

		throw redirect(303, '/');
	}
};
