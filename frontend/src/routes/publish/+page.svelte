<script lang="ts">
	import type { PageData } from './$types';
	import { goto } from '$app/navigation';

	interface PageSummary {
		id: number;
		slug: string;
		title: string;
		description: string | null;
		author_username: string;
		is_interactive: boolean;
		is_draft: boolean;
		published_at: string;
		updated_at: string;
		tags: string[];
	}

	let { data }: { data: PageData } = $props();
	let user = $derived(data.user);
	let myPages = $state<PageSummary[]>(data.myPages as PageSummary[]);

	let importing = $state(false);
	let importError = $state('');
	let creating = $state(false);

	function formatDate(iso: string) {
		return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
	}

	async function createBlank() {
		if (creating) return;
		creating = true;
		try {
			const res = await fetch('/api/pages', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ source_md: '' })
			});
			if (!res.ok) {
				importError = 'Could not create a new page.';
				return;
			}
			const page = await res.json();
			await goto(`/edit/${page.id}`);
		} finally {
			creating = false;
		}
	}

	async function onUpload(ev: Event) {
		const target = ev.target as HTMLInputElement;
		const file = target.files?.[0];
		if (!file) return;
		importing = true;
		importError = '';
		try {
			const fd = new FormData();
			fd.append('file', file);
			const res = await fetch('/api/pages/import', { method: 'POST', body: fd });
			if (!res.ok) {
				const j = await res.json().catch(() => ({}));
				importError = j.detail ?? 'Import failed.';
				return;
			}
			const page = await res.json();
			await goto(`/edit/${page.id}`);
		} catch {
			importError = 'Network error during import.';
		} finally {
			importing = false;
			target.value = '';
		}
	}

	async function deletePage(id: number) {
		if (!confirm('Delete this page? This cannot be undone.')) return;
		const res = await fetch(`/api/pages/id/${id}`, { method: 'DELETE' });
		if (res.ok) {
			myPages = myPages.filter((p) => p.id !== id);
		}
	}

	async function togglePublish(id: number, isDraft: boolean) {
		const res = await fetch(`/api/pages/id/${id}`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ is_draft: !isDraft })
		});
		if (res.ok) {
			const updated = await res.json();
			myPages = myPages.map((p) => (p.id === id ? { ...p, ...updated } : p));
		}
	}
</script>

<svelte:head>
	<title>Publish — Cryptopia</title>
</svelte:head>

<div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
	<div class="mb-10">
		<h1 class="text-3xl font-bold text-white mb-2">Publish</h1>
		<p class="text-slate-400">Create a new page in the block editor or import an existing markdown file.</p>
	</div>

	<div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
		<div class="lg:col-span-2 space-y-6">
			<div class="bg-slate-900 border border-slate-800 rounded-2xl p-6">
				<h2 class="text-white font-semibold text-lg mb-4">Start a new page</h2>
				<p class="text-slate-400 text-sm mb-5">Open a fresh page in the block editor. Add prose, math, code that runs against a live kernel, and interactive widgets.</p>
				<button
					onclick={createBlank}
					disabled={creating}
					class="bg-primary-600 hover:bg-primary-500 disabled:opacity-40 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors"
				>
					{creating ? 'Creating…' : 'New page'}
				</button>
			</div>

			<div class="bg-slate-900 border border-slate-800 rounded-2xl p-6">
				<h2 class="text-white font-semibold text-lg mb-4">Import an existing file</h2>
				<p class="text-slate-400 text-sm mb-5">Upload a Cryptopia Extended Markdown <code class="font-mono text-xs bg-slate-800 px-1.5 py-0.5 rounded text-slate-300">.md</code> file or a Jupyter <code class="font-mono text-xs bg-slate-800 px-1.5 py-0.5 rounded text-slate-300">.ipynb</code>. Notebooks are converted to markdown on import.</p>
				<label class="inline-flex items-center gap-3 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium px-5 py-2.5 rounded-lg transition-colors cursor-pointer">
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0l-4 4m4-4v12"/></svg>
					{importing ? 'Importing…' : 'Choose file'}
					<input type="file" accept=".md,.ipynb,text/markdown,application/x-ipynb+json" class="hidden" onchange={onUpload} disabled={importing} />
				</label>
				{#if importError}
					<p class="text-red-400 text-xs mt-3">{importError}</p>
				{/if}
				<p class="text-slate-600 text-xs mt-3">
					See the <a href="https://github.com/cryptopia/cryptopia/blob/main/docs/extended-markdown.md" class="text-primary-400 hover:text-primary-300">extended markdown spec</a> for syntax reference.
				</p>
			</div>
		</div>

		<div>
			<div class="bg-slate-900 border border-slate-800 rounded-2xl p-6">
				<h2 class="text-white font-semibold mb-4">My pages</h2>
				{#if myPages.length === 0}
					<p class="text-slate-500 text-sm">No pages yet. Create one to get started.</p>
				{:else}
					<div class="space-y-4">
						{#each myPages as item}
							<div class="border-b border-slate-800 last:border-b-0 pb-3 last:pb-0">
								<div class="flex items-start gap-2">
									<div class="flex-1 min-w-0">
										<a href={item.is_draft ? `/edit/${item.id}` : `/research/${user.username}/${item.slug}`} class="block group">
											<p class="text-slate-300 text-sm font-medium group-hover:text-white transition-colors line-clamp-1">{item.title}</p>
										</a>
										<div class="flex items-center gap-2 mt-1">
											<span class="text-slate-600 text-xs">{formatDate(item.updated_at)}</span>
											{#if item.is_draft}
												<span class="text-xs bg-amber-900/30 text-amber-400 border border-amber-800/40 px-1.5 py-0.5 rounded">Draft</span>
											{:else}
												<span class="text-xs bg-emerald-900/30 text-emerald-400 border border-emerald-800/40 px-1.5 py-0.5 rounded">Published</span>
											{/if}
										</div>
									</div>
								</div>
								<div class="flex items-center gap-3 mt-2 text-xs">
									<a href="/edit/{item.id}" class="text-slate-500 hover:text-slate-300">Edit</a>
									<button onclick={() => togglePublish(item.id, item.is_draft)} class="text-slate-500 hover:text-slate-300">
										{item.is_draft ? 'Publish' : 'Unpublish'}
									</button>
									<button onclick={() => deletePage(item.id)} class="text-slate-500 hover:text-red-400">Delete</button>
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		</div>
	</div>
</div>
