<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
	let profile = $derived(data.profile);

	function formatDate(iso: string) {
		return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
	}
</script>

<svelte:head>
	<title>{profile.full_name || profile.username} — Cryptopia</title>
</svelte:head>

<div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
	<!-- Profile header -->
	<div class="flex items-start gap-6 mb-12">
		<div class="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary-600 to-violet-600 flex items-center justify-center text-white text-3xl font-bold shrink-0">
			{profile.username[0].toUpperCase()}
		</div>
		<div>
			<h1 class="text-2xl font-bold text-white">{profile.full_name || profile.username}</h1>
			<p class="text-slate-400 text-sm mb-1">@{profile.username}</p>
			{#if profile.bio}
				<p class="text-slate-300 mt-3 max-w-xl">{profile.bio}</p>
			{/if}
			<p class="text-slate-600 text-xs mt-3">Joined {formatDate(profile.created_at)}</p>
		</div>
	</div>

	<div>
		<h2 class="text-lg font-semibold text-white mb-6">{profile.pages.length} publication{profile.pages.length !== 1 ? 's' : ''}</h2>
		{#if profile.pages.length === 0}
			<p class="text-slate-500 text-sm">No publications yet.</p>
		{:else}
			<div class="space-y-4">
				{#each profile.pages as item}
					<a href="/research/{profile.username}/{item.slug}" class="group block bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
						<h3 class="text-white font-medium group-hover:text-primary-300 transition-colors mb-1">{item.title}</h3>
						{#if item.description}
							<p class="text-slate-400 text-sm line-clamp-2 mb-3">{item.description}</p>
						{/if}
						<div class="flex items-center gap-3 flex-wrap">
							<span class="text-slate-600 text-xs">{formatDate(item.published_at)}</span>
							{#if item.is_interactive}
								<span class="text-xs bg-primary-900/40 text-primary-400 border border-primary-700/40 px-2 py-0.5 rounded-md">Interactive</span>
							{/if}
							{#if item.tags?.length}
								{#each item.tags.slice(0, 3) as tag}
									<span class="text-xs bg-slate-800 text-slate-500 px-2 py-0.5 rounded-md">{tag}</span>
								{/each}
							{/if}
						</div>
					</a>
				{/each}
			</div>
		{/if}
	</div>
</div>
