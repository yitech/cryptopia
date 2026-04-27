<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	function formatDate(iso: string) {
		return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
	}
</script>

<svelte:head>
	<title>Explore Research — Cryptopia</title>
</svelte:head>

<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
	<div class="mb-10">
		<h1 class="text-3xl font-bold text-white mb-2">Explore Research</h1>
		<p class="text-slate-400">Interactive papers from researchers around the world.</p>
	</div>

	<!-- Search -->
	<form method="GET" class="mb-10">
		<div class="flex gap-3 max-w-xl">
			<input
				name="q"
				type="search"
				value={data.q}
				placeholder="Search research…"
				class="flex-1 bg-slate-800 border border-slate-700 text-white placeholder-slate-500 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500"
			/>
			<button type="submit" class="bg-primary-600 hover:bg-primary-500 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors">
				Search
			</button>
		</div>
	</form>

	{#if data.pages.length === 0}
		<div class="text-center py-24 text-slate-500">
			<p class="text-lg mb-2">No pages found.</p>
			{#if data.q}
				<p class="text-sm">Try a different search term or <a href="/research" class="text-primary-400 hover:text-primary-300">browse all</a>.</p>
			{:else}
				<p class="text-sm">Be the first to <a href="/publish" class="text-primary-400 hover:text-primary-300">publish a page</a>.</p>
			{/if}
		</div>
	{:else}
		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
			{#each data.pages as item}
				<a href="/research/{item.author_username}/{item.slug}" class="group block bg-slate-900 border border-slate-800 rounded-2xl p-6 hover:border-slate-700 transition-all duration-200 hover:-translate-y-0.5">
					<div class="flex items-center gap-2 mb-3">
						<div class="w-7 h-7 rounded-full bg-gradient-to-br from-primary-600 to-violet-600 flex items-center justify-center text-white text-xs font-bold">
							{item.author_username[0].toUpperCase()}
						</div>
						<span class="text-slate-400 text-xs">{item.author_username}</span>
						<span class="text-slate-600 text-xs ml-auto">{formatDate(item.published_at)}</span>
					</div>
					<h2 class="text-white font-semibold text-lg mb-2 group-hover:text-primary-300 transition-colors line-clamp-2">{item.title}</h2>
					{#if item.description}
						<p class="text-slate-400 text-sm leading-relaxed line-clamp-3">{item.description}</p>
					{/if}
					{#if item.tags?.length}
						<div class="flex flex-wrap gap-1.5 mt-4">
							{#each item.tags.slice(0, 4) as tag}
								<span class="text-xs bg-slate-800 text-slate-400 border border-slate-700 px-2 py-0.5 rounded-md">{tag}</span>
							{/each}
						</div>
					{/if}
				</a>
			{/each}
		</div>

		<!-- Pagination -->
		{#if data.total > 12}
			<div class="flex items-center justify-center gap-3 mt-12">
				{#if data.page > 1}
					<a href="?page={data.page - 1}{data.q ? `&q=${data.q}` : ''}" class="px-4 py-2 bg-slate-800 text-slate-300 rounded-lg text-sm hover:bg-slate-700 transition-colors">
						← Previous
					</a>
				{/if}
				<span class="text-slate-500 text-sm">Page {data.page} of {Math.ceil(data.total / 12)}</span>
				{#if data.page * 12 < data.total}
					<a href="?page={data.page + 1}{data.q ? `&q=${data.q}` : ''}" class="px-4 py-2 bg-slate-800 text-slate-300 rounded-lg text-sm hover:bg-slate-700 transition-colors">
						Next →
					</a>
				{/if}
			</div>
		{/if}
	{/if}
</div>
