<script lang="ts">
	const EMOJIS = ['👍', '❤️', '🔥', '🎉', '🤔', '💡'];

	let {
		pageId,
		initialCounts,
		initialMyReaction,
		user
	}: {
		pageId: number;
		initialCounts: Record<string, number>;
		initialMyReaction: string | null;
		user: App.Locals['user'];
	} = $props();

	let counts = $state<Record<string, number>>({ ...initialCounts });
	let myReaction = $state<string | null>(initialMyReaction);
	let loading = $state(false);

	async function react(emoji: string) {
		if (!user || loading) return;
		loading = true;

		const prev = myReaction;
		const prevCounts = { ...counts };

		// Optimistic update
		if (myReaction === emoji) {
			myReaction = null;
			counts = { ...counts, [emoji]: Math.max(0, (counts[emoji] ?? 1) - 1) };
		} else {
			if (myReaction) {
				counts = { ...counts, [myReaction]: Math.max(0, (counts[myReaction] ?? 1) - 1) };
			}
			myReaction = emoji;
			counts = { ...counts, [emoji]: (counts[emoji] ?? 0) + 1 };
		}

		try {
			const res = await fetch(`/api/social/pages/${pageId}/reactions?emoji=${encodeURIComponent(emoji)}`, {
				method: 'POST'
			});
			if (!res.ok) {
				myReaction = prev;
				counts = prevCounts;
			}
		} catch {
			myReaction = prev;
			counts = prevCounts;
		} finally {
			loading = false;
		}
	}

	function total() {
		return Object.values(counts).reduce((a, b) => a + b, 0);
	}
</script>

<div class="flex items-center gap-2 flex-wrap">
	{#each EMOJIS as emoji}
		{@const count = counts[emoji] ?? 0}
		{@const active = myReaction === emoji}
		{#if count > 0 || user}
			<button
				onclick={() => react(emoji)}
				disabled={!user || loading}
				class="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-full border transition-all duration-150
					{active
						? 'bg-primary-900/50 border-primary-600/60 text-primary-300'
						: 'bg-slate-800/50 border-slate-700/50 text-slate-400 hover:border-slate-600 hover:text-slate-300'}
					disabled:cursor-default"
				title={user ? (active ? `Remove ${emoji}` : `React with ${emoji}`) : 'Sign in to react'}
			>
				<span>{emoji}</span>
				{#if count > 0}
					<span class="text-xs font-medium tabular-nums">{count}</span>
				{/if}
			</button>
		{/if}
	{/each}
	{#if total() === 0 && !user}
		<p class="text-slate-600 text-xs">No reactions yet.</p>
	{/if}
</div>
