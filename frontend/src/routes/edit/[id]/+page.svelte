<script lang="ts">
	import type { PageData } from './$types';
	import { goto } from '$app/navigation';
	import {
		parse,
		serialize,
		ensureCellIds,
		isInteractive,
		deriveTitle,
		deriveDescription,
		type Block,
		type Frontmatter,
		type ParsedDocument,
		type OutputRecord
	} from '$lib/md/extended';
	import BlockEditor from '$lib/components/editor/BlockEditor.svelte';

	let { data }: { data: PageData } = $props();

	let initialDoc: ParsedDocument = parse(data.page.source_md ?? '');
	let frontmatter = $state<Frontmatter>({ ...initialDoc.frontmatter });
	let blocks = $state<Block[]>(ensureCellIds(initialDoc.blocks));

	let title = $state(data.page.title || deriveTitle({ frontmatter, blocks }, 'Untitled'));
	let description = $state<string>(data.page.description ?? deriveDescription({ frontmatter, blocks }) ?? '');
	let tagsInput = $state<string>((data.page.tags ?? []).join(', '));
	let isDraft = $state<boolean>(data.page.is_draft);

	let view = $state<'edit' | 'source'>('edit');
	let sourceText = $state<string>('');

	let saveStatus = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
	let runningIndex = $state<number | null>(null);
	let saveError = $state('');

	let saveTimer: ReturnType<typeof setTimeout> | null = null;

	const apiBase = data.apiBase;
	const pageId = data.page.id;

	function buildSource(): string {
		const tags = tagsInput
			.split(',')
			.map((t) => t.trim())
			.filter(Boolean);
		const fm: Frontmatter = {
			...frontmatter,
			title: title || undefined,
			description: description || undefined,
			tags: tags.length > 0 ? tags : undefined,
			interactive: isInteractive(blocks) || undefined
		};
		for (const k of Object.keys(fm)) {
			if (fm[k] === undefined) delete fm[k];
		}
		return serialize({ frontmatter: fm, blocks });
	}

	$effect(() => {
		void title;
		void description;
		void tagsInput;
		void blocks;
		void frontmatter;
		scheduleSave();
	});

	function scheduleSave() {
		saveStatus = 'saving';
		if (saveTimer) clearTimeout(saveTimer);
		saveTimer = setTimeout(() => {
			void save();
		}, 800);
	}

	async function save() {
		try {
			const source_md = buildSource();
			const tags = tagsInput
				.split(',')
				.map((t) => t.trim())
				.filter(Boolean);
			const res = await fetch(`/api/pages/id/${pageId}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					source_md,
					title: title || undefined,
					description: description || undefined,
					tags
				})
			});
			if (!res.ok) {
				const j = await res.json().catch(() => ({}));
				saveError = j.detail ?? 'Save failed.';
				saveStatus = 'error';
				return;
			}
			saveStatus = 'saved';
			saveError = '';
		} catch {
			saveStatus = 'error';
			saveError = 'Network error while saving.';
		}
	}

	function onBlockChange(i: number, block: Block) {
		const next = blocks.slice();
		next[i] = block;
		blocks = ensureCellIds(next);
	}

	function onMove(i: number, dir: -1 | 1) {
		const j = i + dir;
		if (j < 0 || j >= blocks.length) return;
		const next = blocks.slice();
		[next[i], next[j]] = [next[j], next[i]];
		blocks = next;
	}

	function onDelete(i: number) {
		blocks = blocks.filter((_, idx) => idx !== i);
	}

	function onInsertAfter(i: number) {
		const next = blocks.slice();
		next.splice(i + 1, 0, { kind: 'paragraph', raw: '' });
		blocks = next;
	}

	function appendBlock(kind: Block['kind']) {
		switch (kind) {
			case 'heading':
				blocks = [...blocks, { kind: 'heading', level: 2, text: 'New section' }];
				break;
			case 'code-cell':
				blocks = ensureCellIds([
					...blocks,
					{
						kind: 'code-cell',
						lang: 'python',
						source: '',
						id: null,
						auto: true,
						output: null
					}
				]);
				break;
			case 'code-block':
				blocks = [
					...blocks,
					{ kind: 'code-block', lang: 'python', source: '' }
				];
				break;
			case 'math':
				blocks = [...blocks, { kind: 'math', tex: 'a^2 + b^2 = c^2' }];
				break;
			case 'widget':
				blocks = [
					...blocks,
					{
						kind: 'widget',
						spec: { type: 'text', id: 'w', content: 'Hello', format: 'markdown' }
					}
				];
				break;
			case 'divider':
				blocks = [...blocks, { kind: 'divider' }];
				break;
			default:
				blocks = [...blocks, { kind: 'paragraph', raw: '' }];
		}
	}

	async function onRun(i: number) {
		const block = blocks[i];
		if (block.kind !== 'code-cell' || !block.id) return;
		runningIndex = i;
		try {
			await save();
			const res = await fetch(`/api/pages/id/${pageId}/run-cell`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ cell_id: block.id, widget_values: {} })
			});
			if (!res.ok) {
				const j = await res.json().catch(() => ({}));
				saveError = j.detail ?? 'Run failed.';
				return;
			}
			const result: { outputs: OutputRecord[]; source_md: string } = await res.json();
			const reparsed = parse(result.source_md);
			blocks = ensureCellIds(reparsed.blocks);
			frontmatter = reparsed.frontmatter;
		} finally {
			runningIndex = null;
		}
	}

	async function togglePublish() {
		await save();
		const res = await fetch(`/api/pages/id/${pageId}`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ is_draft: !isDraft })
		});
		if (res.ok) {
			const updated = await res.json();
			isDraft = updated.is_draft;
			if (!isDraft) {
				await goto(`/research/${updated.author_username}/${updated.slug}`);
			}
		}
	}

	function openSource() {
		sourceText = buildSource();
		view = 'source';
	}

	function applySource() {
		const parsed = parse(sourceText);
		frontmatter = parsed.frontmatter;
		blocks = ensureCellIds(parsed.blocks);
		if (parsed.frontmatter.title) title = parsed.frontmatter.title as string;
		if (parsed.frontmatter.description) description = parsed.frontmatter.description as string;
		if (parsed.frontmatter.tags) tagsInput = (parsed.frontmatter.tags as string[]).join(', ');
		view = 'edit';
	}
</script>

<svelte:head>
	<title>{title || 'Untitled'} — Edit · Cryptopia</title>
</svelte:head>

<div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
	<div class="flex items-center justify-between mb-6 sticky top-0 bg-slate-950/90 backdrop-blur z-10 -mx-4 px-4 py-3 border-b border-slate-800">
		<div class="flex items-center gap-3">
			<a href="/publish" class="text-slate-500 hover:text-slate-300 text-sm">← My pages</a>
			<span class="text-slate-700">/</span>
			<span class="text-slate-400 text-sm">Editing</span>
			<span class="text-xs px-2 py-0.5 rounded {isDraft ? 'bg-amber-900/30 text-amber-400 border border-amber-800/40' : 'bg-emerald-900/30 text-emerald-400 border border-emerald-800/40'}">
				{isDraft ? 'Draft' : 'Published'}
			</span>
		</div>
		<div class="flex items-center gap-3 text-sm">
			<span class="text-slate-500 text-xs">
				{#if saveStatus === 'saving'}Saving…{:else if saveStatus === 'saved'}Saved{:else if saveStatus === 'error'}{saveError || 'Error'}{/if}
			</span>
			<div class="flex bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
				<button
					onclick={() => (view = 'edit')}
					class="px-3 py-1 text-xs {view === 'edit' ? 'bg-slate-800 text-white' : 'text-slate-400'}"
				>Edit</button>
				<button
					onclick={openSource}
					class="px-3 py-1 text-xs {view === 'source' ? 'bg-slate-800 text-white' : 'text-slate-400'}"
				>Source</button>
			</div>
			<button
				onclick={togglePublish}
				class="bg-primary-600 hover:bg-primary-500 text-white text-xs font-medium px-3 py-1.5 rounded transition-colors"
			>
				{isDraft ? 'Publish' : 'Unpublish'}
			</button>
		</div>
	</div>

	{#if view === 'edit'}
		<div class="space-y-2 mb-6">
			<input
				type="text"
				bind:value={title}
				placeholder="Page title"
				class="w-full bg-transparent text-3xl font-bold text-white placeholder-slate-600 focus:outline-none"
			/>
			<textarea
				bind:value={description}
				placeholder="Short description (optional)"
				rows="2"
				class="w-full bg-transparent text-lg text-slate-300 placeholder-slate-600 focus:outline-none resize-none"
			></textarea>
			<input
				type="text"
				bind:value={tagsInput}
				placeholder="tags, separated, by, commas"
				class="w-full bg-transparent text-sm text-slate-400 placeholder-slate-600 focus:outline-none"
			/>
		</div>

		<div class="space-y-4 ml-10">
			{#each blocks as block, i (block)}
				<BlockEditor
					{block}
					index={i}
					total={blocks.length}
					{pageId}
					{apiBase}
					onChange={onBlockChange}
					{onMove}
					{onDelete}
					{onInsertAfter}
					{onRun}
					running={runningIndex === i}
				/>
			{/each}
		</div>

		<div class="mt-6 ml-10 flex flex-wrap gap-2">
			<button onclick={() => appendBlock('paragraph')} class="bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs px-3 py-1.5 rounded">+ Text</button>
			<button onclick={() => appendBlock('heading')} class="bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs px-3 py-1.5 rounded">+ Heading</button>
			<button onclick={() => appendBlock('code-cell')} class="bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs px-3 py-1.5 rounded">+ Code cell</button>
			<button onclick={() => appendBlock('code-block')} class="bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs px-3 py-1.5 rounded">+ Code block</button>
			<button onclick={() => appendBlock('math')} class="bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs px-3 py-1.5 rounded">+ Math</button>
			<button onclick={() => appendBlock('widget')} class="bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs px-3 py-1.5 rounded">+ Widget</button>
			<button onclick={() => appendBlock('divider')} class="bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs px-3 py-1.5 rounded">+ Divider</button>
		</div>
	{:else}
		<div class="space-y-3">
			<p class="text-slate-400 text-sm">Edit the raw Cryptopia Extended Markdown source. Click "Apply" to switch back to the block editor.</p>
			<textarea
				bind:value={sourceText}
				class="w-full h-[70vh] bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-primary-500/40"
				spellcheck="false"
			></textarea>
			<div class="flex justify-end gap-2">
				<button onclick={() => (view = 'edit')} class="bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm px-4 py-2 rounded">Cancel</button>
				<button onclick={applySource} class="bg-primary-600 hover:bg-primary-500 text-white text-sm font-medium px-4 py-2 rounded">Apply</button>
			</div>
		</div>
	{/if}
</div>
