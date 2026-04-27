<script lang="ts">
	interface Comment {
		id: number;
		content: string;
		author_username: string;
		author_full_name: string | null;
		created_at: string;
	}

	let {
		pageId,
		initialComments,
		user
	}: {
		pageId: number;
		initialComments: Comment[];
		user: App.Locals['user'];
	} = $props();

	let comments = $state<Comment[]>(initialComments);
	let newComment = $state('');
	let submitting = $state(false);
	let error = $state('');

	function formatDate(iso: string) {
		return new Date(iso).toLocaleDateString('en-US', {
			year: 'numeric',
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}

	async function submitComment() {
		if (!newComment.trim() || submitting) return;
		submitting = true;
		error = '';
		try {
			const res = await fetch(`/api/social/pages/${pageId}/comments`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ content: newComment.trim() })
			});
			if (!res.ok) {
				const j = await res.json().catch(() => ({}));
				error = j.detail ?? 'Failed to post comment.';
			} else {
				const comment = await res.json();
				comments = [...comments, comment];
				newComment = '';
			}
		} catch {
			error = 'Network error. Please try again.';
		} finally {
			submitting = false;
		}
	}

	async function deleteComment(id: number) {
		const res = await fetch(`/api/social/comments/${id}`, { method: 'DELETE' });
		if (res.ok) {
			comments = comments.filter((c) => c.id !== id);
		}
	}
</script>

<section class="mt-12 border-t border-slate-800 pt-8">
	<h2 class="text-lg font-semibold text-white mb-6">
		{comments.length} comment{comments.length !== 1 ? 's' : ''}
	</h2>

	{#if user}
		<div class="mb-8">
			<textarea
				bind:value={newComment}
				placeholder="Share your thoughts or questions…"
				rows="3"
				class="w-full bg-slate-800 border border-slate-700 text-white placeholder-slate-500 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 resize-none transition-colors"
			></textarea>
			{#if error}
				<p class="text-red-400 text-xs mt-1">{error}</p>
			{/if}
			<div class="flex justify-end mt-2">
				<button
					onclick={submitComment}
					disabled={!newComment.trim() || submitting}
					class="bg-primary-600 hover:bg-primary-500 disabled:opacity-40 text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors"
				>
					{submitting ? 'Posting…' : 'Post comment'}
				</button>
			</div>
		</div>
	{:else}
		<p class="text-slate-500 text-sm mb-6">
			<a href="/login" class="text-primary-400 hover:text-primary-300">Sign in</a> to leave a comment.
		</p>
	{/if}

	<div class="space-y-6">
		{#each comments as comment (comment.id)}
			<div class="flex gap-3">
				<div class="w-8 h-8 rounded-full bg-gradient-to-br from-slate-600 to-slate-700 flex items-center justify-center text-white text-xs font-bold shrink-0 mt-0.5">
					{comment.author_username[0].toUpperCase()}
				</div>
				<div class="flex-1 min-w-0">
					<div class="flex items-center gap-2 mb-1">
						<a href="/profile/{comment.author_username}" class="text-slate-300 text-sm font-medium hover:text-white transition-colors">
							{comment.author_full_name || comment.author_username}
						</a>
						<span class="text-slate-600 text-xs">{formatDate(comment.created_at)}</span>
						{#if user?.username === comment.author_username}
							<button
								onclick={() => deleteComment(comment.id)}
								class="text-slate-600 hover:text-red-400 text-xs ml-auto transition-colors"
								aria-label="Delete comment"
							>Delete</button>
						{/if}
					</div>
					<p class="text-slate-400 text-sm leading-relaxed whitespace-pre-wrap break-words">{comment.content}</p>
				</div>
			</div>
		{/each}
	</div>
</section>
