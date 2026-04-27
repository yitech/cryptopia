import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { parse, isInteractive } from '$lib/md/extended';

// Internal URL — used for server-side fetches (resolves the Docker hostname).
const API_BASE = process.env.API_URL ?? 'http://localhost:8000';
// Public URL — kept for now so widgets that still consult `apiBase` keep
// working. Runtime calls go through the SvelteKit proxy at /api/...
const PUBLIC_API_BASE = process.env.PUBLIC_API_URL ?? 'http://localhost:8000';

export const load: PageServerLoad = async ({ params }) => {
	const { username, slug } = params;

	const pageRes = await fetch(`${API_BASE}/api/pages/${username}/${slug}`);
	if (pageRes.status === 404) throw error(404, 'Page not found');
	if (!pageRes.ok) throw error(500, 'Failed to load page');

	const page = await pageRes.json();

	const parsed = parse(page.source_md ?? '');
	const live = isInteractive(parsed.blocks);

	const [commentsRes, reactionsRes] = await Promise.all([
		fetch(`${API_BASE}/api/social/pages/${page.id}/comments`),
		fetch(`${API_BASE}/api/social/pages/${page.id}/reactions`)
	]);

	const comments = commentsRes.ok ? await commentsRes.json() : [];
	const reactions = reactionsRes.ok
		? await reactionsRes.json()
		: { counts: {}, my_reaction: null };

	return {
		page,
		blocks: parsed.blocks,
		frontmatter: parsed.frontmatter,
		isInteractive: live,
		apiBase: PUBLIC_API_BASE,
		comments,
		reactionCounts: reactions.counts,
		myReaction: reactions.my_reaction
	};
};
