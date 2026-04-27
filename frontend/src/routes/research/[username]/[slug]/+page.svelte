<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import type { PageData } from './$types';
	import { Block as BlockView } from '$lib/render';
	import WidgetRenderer from '$lib/components/widgets/WidgetRenderer.svelte';
	import CommentsSection from '$lib/components/CommentsSection.svelte';
	import ReactionsBar from '$lib/components/ReactionsBar.svelte';
	import { executionStore, isInputWidget, type WidgetSpec } from '$lib/stores/execution';
	import type { Block } from '$lib/md/extended';

	let { data }: { data: PageData } = $props();
	let page = $derived(data.page);
	let blocks = $derived(data.blocks as Block[]);
	let apiBase = $derived(data.apiBase);

	let execState = $derived($executionStore);
	let hasInteractive = $derived(data.isInteractive);

	// Code-cell sources default collapsed — researchers care about outputs more
	// than implementation details. The toggle in the header reveals every
	// cell's source if a reader wants to dig in.
	let showSources = $state(false);
	let hasCodeCells = $derived(blocks.some((b) => b.kind === 'code-cell'));

	function formatDate(iso: string) {
		return new Date(iso).toLocaleDateString('en-US', {
			year: 'numeric',
			month: 'long',
			day: 'numeric'
		});
	}

	async function runPage() {
		// Run every auto code-cell in document order against the persistent kernel.
		// The first run is what registers `on_change` callbacks and seeds the
		// initial output cache; afterwards interactivity is purely widget-driven.
		await executionStore.runAll(page.id, apiBase, blocks);
	}

	let pageStatus = $derived.by(() => {
		// Aggregate status across all cells: running > error > done > idle.
		let any = false;
		let running = false;
		let error = false;
		let done = false;
		for (const b of blocks) {
			if (b.kind !== 'code-cell' || !b.id) continue;
			any = true;
			const c = execState.cells[b.id];
			if (!c) continue;
			if (c.status === 'running') running = true;
			else if (c.status === 'error') error = true;
			else if (c.status === 'done') done = true;
		}
		if (!any) return 'idle' as const;
		if (running) return 'running' as const;
		if (error) return 'error' as const;
		if (done) return 'done' as const;
		return 'idle' as const;
	});

	let execCounts = $derived.by(() => {
		const counts: Array<number | null> = [];
		let n = 0;
		for (const b of blocks) {
			if (b.kind === 'code-cell') {
				counts.push(++n);
			} else {
				counts.push(null);
			}
		}
		return counts;
	});

	// Collect input widgets (sliders/selects/...) from every code cell
	// in document order. Live outputs from the kernel take precedence over
	// the cached cx-output blocks in the markdown so the sidebar reflects
	// whatever the latest run produced.
	type InputGroup = { cellId: string; widgets: WidgetSpec[] };
	let inputGroups = $derived.by((): InputGroup[] => {
		const groups: InputGroup[] = [];
		for (const block of blocks) {
			if (block.kind !== 'code-cell' || !block.id) continue;
			const live = execState.cells[block.id]?.outputs;
			const records = live ?? block.output ?? [];
			const inputs: WidgetSpec[] = [];
			for (const r of records) {
				if ('type' in r && r.type === 'widget' && isInputWidget(r.spec)) {
					inputs.push(r.spec);
				}
			}
			if (inputs.length > 0) groups.push({ cellId: block.id, widgets: inputs });
		}
		return groups;
	});

	onMount(() => {
		// Seed the store so cached widget values from cx-output blocks are
		// available the moment the user moves a slider, before any run.
		executionStore.seed(blocks);
	});

	onDestroy(() => executionStore.reset());
</script>

<svelte:head>
	<title>{page.title} — Cryptopia</title>
	<meta name="description" content={page.description ?? page.title} />
</svelte:head>

<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
	<header class="mb-10 max-w-4xl">
		<div class="flex items-center gap-2 mb-4">
			<a href="/research" class="text-slate-500 hover:text-slate-400 text-sm transition-colors">Explore</a>
			<span class="text-slate-700">/</span>
			<a href="/profile/{page.author_username}" class="text-slate-500 hover:text-slate-400 text-sm transition-colors">{page.author_username}</a>
		</div>
		<h1 class="text-4xl font-bold text-white mb-4 leading-tight">{page.title}</h1>
		{#if page.description}
			<p class="text-xl text-slate-400 mb-6 leading-relaxed">{page.description}</p>
		{/if}
		<div class="flex items-center gap-4 flex-wrap">
			<a href="/profile/{page.author_username}" class="flex items-center gap-2 group">
				<div class="w-8 h-8 rounded-full bg-gradient-to-br from-primary-600 to-violet-600 flex items-center justify-center text-white text-xs font-bold">
					{page.author_username[0].toUpperCase()}
				</div>
				<span class="text-slate-300 text-sm group-hover:text-white transition-colors">{page.author_full_name || page.author_username}</span>
			</a>
			<span class="text-slate-600 text-sm">·</span>
			<span class="text-slate-500 text-sm">{formatDate(page.published_at)}</span>
			{#if page.tags?.length}
				<div class="flex flex-wrap gap-1.5">
					{#each page.tags as tag}
						<span class="text-xs bg-slate-800 text-slate-400 border border-slate-700 px-2 py-0.5 rounded-md">{tag}</span>
					{/each}
				</div>
			{/if}
			<div class="ml-auto flex items-center gap-3">
				{#if hasCodeCells}
					<button
						type="button"
						onclick={() => (showSources = !showSources)}
						class="text-slate-400 hover:text-slate-200 text-xs flex items-center gap-1.5 transition-colors"
						title={showSources ? 'Collapse all code sources' : 'Show all code sources'}
					>
						<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
						</svg>
						{showSources ? 'Hide sources' : 'Show sources'}
					</button>
				{/if}
				<a
					href="/api/pages/{page.author_username}/{page.slug}/raw.md"
					class="text-slate-500 hover:text-slate-300 text-xs underline-offset-4 hover:underline"
					download
				>
					Download .md
				</a>
			</div>
		</div>
	</header>

	{#if hasInteractive}
		<div class="lg:grid lg:grid-cols-[minmax(0,1fr)_320px] lg:gap-10">
			<aside class="lg:col-start-2 lg:row-start-1 mb-8 lg:mb-0">
				<div class="lg:sticky lg:top-4 space-y-4">
					<!-- Status + Run controls -->
					<div class="bg-slate-900 border border-primary-800/40 rounded-xl px-4 py-3">
						<div class="flex items-center gap-2 mb-2">
							<div class="w-2 h-2 rounded-full {pageStatus === 'running' ? 'bg-yellow-400 animate-pulse' : pageStatus === 'done' ? 'bg-green-400' : pageStatus === 'error' ? 'bg-red-400' : 'bg-slate-600'}"></div>
							<span class="text-slate-200 text-sm font-medium">Interactive</span>
						</div>
						<p class="text-slate-500 text-xs mb-3">
							{#if pageStatus === 'idle'}Showing cached output. Click Run to start a live session.{:else if pageStatus === 'running'}Running cells…{:else if pageStatus === 'done'}Live — adjust controls to update visualisations.{:else if pageStatus === 'error'}Execution failed{/if}
						</p>
						{#if execState.error}
							<p class="text-red-400 text-xs bg-red-950/40 border border-red-800/50 rounded-md px-2 py-1.5 mb-3">{execState.error}</p>
						{/if}
						{#if pageStatus === 'idle'}
							<button onclick={runPage} class="w-full bg-primary-600 hover:bg-primary-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors flex items-center justify-center gap-1.5">
								<svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20"><path d="M6.3 2.84A1.5 1.5 0 004 4.11v11.78a1.5 1.5 0 002.3 1.27l9.344-5.891a1.5 1.5 0 000-2.538L6.3 2.84z"/></svg>
								Run page
							</button>
						{:else}
							<button onclick={runPage} class="w-full text-slate-300 hover:text-white text-sm font-medium px-3 py-2 rounded-lg border border-slate-700 hover:border-slate-600 transition-colors">
								Re-run page
							</button>
						{/if}
					</div>

					<!-- Live controls — input widgets grouped by their producing cell. -->
					{#if inputGroups.length > 0}
						<div class="bg-slate-950/60 border border-slate-800 rounded-xl px-4 py-4 space-y-5">
							<p class="text-slate-400 text-xs font-medium uppercase tracking-wider">Controls</p>
							{#each inputGroups as group (group.cellId)}
								<div class="space-y-2">
									{#if inputGroups.length > 1}
										<p class="text-slate-500 text-[11px] font-mono">#{group.cellId}</p>
									{/if}
									<div class="space-y-3">
										{#each group.widgets as spec (spec.id)}
											<WidgetRenderer {spec} researchId={page.id} {apiBase} />
										{/each}
									</div>
								</div>
							{/each}
						</div>
					{:else if pageStatus !== 'idle'}
						<div class="bg-slate-950/60 border border-slate-800 rounded-xl px-4 py-3">
							<p class="text-slate-500 text-xs">This page has no interactive controls.</p>
						</div>
					{/if}
				</div>
			</aside>

			<main class="lg:col-start-1 lg:row-start-1 space-y-6 min-w-0">
				{#each blocks as block, i}
					<BlockView
						{block}
						pageId={page.id}
						{apiBase}
						executionCount={execCounts[i]}
						hideInputWidgets
						{showSources}
					/>
				{/each}
			</main>
		</div>
	{:else}
		<div class="max-w-4xl space-y-6">
			{#each blocks as block, i}
				<BlockView
					{block}
					pageId={page.id}
					{apiBase}
					executionCount={execCounts[i]}
					{showSources}
				/>
			{/each}
		</div>
	{/if}

	<div class="max-w-4xl mt-10 pt-6 border-t border-slate-800">
		<p class="text-slate-500 text-xs mb-3">Reactions</p>
		<ReactionsBar
			pageId={page.id}
			initialCounts={data.reactionCounts}
			initialMyReaction={data.myReaction}
			user={data.user}
		/>
	</div>

	<div class="max-w-4xl">
		<CommentsSection
			pageId={page.id}
			initialComments={data.comments}
			user={data.user}
		/>
	</div>

	<footer class="max-w-4xl border-t border-slate-800 mt-12 pt-8">
		<div class="flex items-center justify-between">
			<a href="/profile/{page.author_username}" class="flex items-center gap-3 group">
				<div class="w-10 h-10 rounded-full bg-gradient-to-br from-primary-600 to-violet-600 flex items-center justify-center text-white font-bold">
					{page.author_username[0].toUpperCase()}
				</div>
				<div>
					<p class="text-white text-sm font-medium group-hover:text-primary-300 transition-colors">{page.author_full_name || page.author_username}</p>
					<p class="text-slate-500 text-xs">@{page.author_username}</p>
				</div>
			</a>
			<a href="/research" class="text-slate-500 hover:text-slate-400 text-sm transition-colors">← Back to explore</a>
		</div>
	</footer>
</div>
