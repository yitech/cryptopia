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
		const email = data.get('email')?.toString();
		const password = data.get('password')?.toString();
		const full_name = data.get('full_name')?.toString() || null;

		if (!username || !email || !password) {
			return fail(400, { error: 'All fields are required.' });
		}
		if (password.length < 8) {
			return fail(400, { error: 'Password must be at least 8 characters.' });
		}

		let res: Response;
		try {
			res = await fetch(`${API_BASE}/api/auth/register`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username, email, password, full_name })
			});
		} catch {
			return fail(503, { error: 'Cannot reach the server. Please try again.' });
		}

		if (!res.ok) {
			const json = await res.json().catch(() => ({}));
			return fail(res.status, { error: json.detail ?? 'Registration failed.' });
		}

		// Auto-login after registration
		const body = new URLSearchParams({ username, password });
		const tokenRes = await fetch(`${API_BASE}/api/auth/token`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
			body: body.toString()
		});

		if (tokenRes.ok) {
			const { access_token } = await tokenRes.json();
			cookies.set('access_token', access_token, {
				path: '/',
				httpOnly: true,
				sameSite: 'lax',
				maxAge: 60 * 60 * 24 * 7
			});
		}

		throw redirect(303, '/publish');
	}
};
