<script lang="ts">
	import type { Block, OutputRecord } from '$lib/md/extended';
	import Markdown from '$lib/render/Markdown.svelte';
	import Output from '$lib/render/Output.svelte';
	import WidgetRenderer from '../widgets/WidgetRenderer.svelte';
	import type { WidgetSpec } from '$lib/stores/execution';

	let {
		block,
		index,
		total,
		pageId,
		apiBase,
		onChange,
		onMove,
		onDelete,
		onInsertAfter,
		onRun,
		running = false
	}: {
		block: Block;
		index: number;
		total: number;
		pageId: number;
		apiBase: string;
		onChange: (index: number, block: Block) => void;
		onMove: (index: number, dir: -1 | 1) => void;
		onDelete: (index: number) => void;
		onInsertAfter: (index: number) => void;
		onRun: (index: number) => void;
		running?: boolean;
	} = $props();

	let showMenu = $state(false);
	let preview = $state(false);

	function blockText(b: Block): string {
		switch (b.kind) {
			case 'paragraph':
			case 'list':
			case 'quote':
			case 'table':
			case 'raw':
				return b.raw;
			case 'heading':
				return b.text;
			case 'math':
				return b.tex;
			case 'code-block':
			case 'code-cell':
				return b.source;
			case 'widget':
				return JSON.stringify(b.spec, null, 2);
			default:
				return '';
		}
	}

	function widgetSpecs(records: OutputRecord[] | null) {
		if (!records) return [];
		return records.filter((r) => 'type' in r && r.type === 'widget').map((r) => (r as { spec: WidgetSpec }).spec);
	}

	function nonWidgetOutputs(records: OutputRecord[] | null) {
		if (!records) return [];
		const out: Array<{
			output_type: string;
			data?: Record<string, string>;
			text?: string;
			ename?: string;
			evalue?: string;
			traceback?: string[];
		}> = [];
		for (const r of records) {
			if ('type' in r && r.type === 'widget') continue;
			if ('type' in r && r.type === 'error') {
				out.push({
					output_type: 'error',
					ename: r.ename,
					evalue: r.evalue,
					traceback: r.traceback
				});
				continue;
			}
			const mime = (r as { mime: string }).mime;
			const data = (r as { data: string }).data;
			if (mime === 'text/plain') out.push({ output_type: 'stream', text: data });
			else out.push({ output_type: 'display_data', data: { [mime]: data } });
		}
		return out;
	}

	function setText(value: string) {
		const b = block;
		switch (b.kind) {
			case 'paragraph':
			case 'list':
			case 'quote':
			case 'table':
			case 'raw':
				onChange(index, { ...b, raw: value });
				break;
			case 'heading':
				onChange(index, { ...b, text: value });
				break;
			case 'math':
				onChange(index, { ...b, tex: value });
				break;
			case 'code-block':
			case 'code-cell':
				onChange(index, { ...b, source: value });
				break;
			case 'widget':
				try {
					const spec = JSON.parse(value);
					onChange(index, { ...b, spec });
				} catch {
					/* ignore parse error while typing */
				}
				break;
		}
	}

	function setHeadingLevel(level: number) {
		if (block.kind !== 'heading') return;
		onChange(index, { ...block, level: level as 1 | 2 | 3 | 4 | 5 | 6 });
	}

	function changeBlockKind(kind: Block['kind']) {
		const text = blockText(block);
		switch (kind) {
			case 'paragraph':
				onChange(index, { kind: 'paragraph', raw: text });
				break;
			case 'heading':
				onChange(index, { kind: 'heading', level: 2, text });
				break;
			case 'list':
				onChange(index, { kind: 'list', raw: text || '- ' });
				break;
			case 'quote':
				onChange(index, { kind: 'quote', raw: text || '> ' });
				break;
			case 'math':
				onChange(index, { kind: 'math', tex: text });
				break;
			case 'divider':
				onChange(index, { kind: 'divider' });
				break;
			case 'code-block':
				onChange(index, { kind: 'code-block', lang: 'python', source: text });
				break;
			case 'code-cell':
				onChange(index, {
					kind: 'code-cell',
					lang: 'python',
					source: text,
					id: null,
					auto: true,
					output: null
				});
				break;
			case 'widget':
				onChange(index, {
					kind: 'widget',
					spec: { type: 'text', id: 'w', content: text || 'Hello', format: 'markdown' }
				});
				break;
			case 'raw':
				onChange(index, { kind: 'raw', raw: text });
				break;
			case 'table':
				onChange(index, { kind: 'table', raw: text || '| col |\n| --- |\n|     |' });
				break;
		}
		showMenu = false;
	}

	function setCodeLang(value: string) {
		if (block.kind !== 'code-block' && block.kind !== 'code-cell') return;
		onChange(index, { ...block, lang: value });
	}

	function setCodeId(value: string) {
		if (block.kind !== 'code-cell') return;
		onChange(index, { ...block, id: value || null });
	}

	function setCodeAuto(checked: boolean) {
		if (block.kind !== 'code-cell') return;
		onChange(index, { ...block, auto: checked });
	}

	const blockKindLabels: Array<{ kind: Block['kind']; label: string; hint: string }> = [
		{ kind: 'paragraph', label: 'Text', hint: 'Plain markdown paragraph' },
		{ kind: 'heading', label: 'Heading', hint: '# / ## / ### …' },
		{ kind: 'list', label: 'List', hint: '- / 1. items' },
		{ kind: 'quote', label: 'Quote', hint: '> blockquote' },
		{ kind: 'table', label: 'Table', hint: 'GFM | col |' },
		{ kind: 'math', label: 'Math', hint: '$$ display math $$' },
		{ kind: 'divider', label: 'Divider', hint: '---' },
		{ kind: 'code-block', label: 'Code block', hint: 'Display-only fenced code' },
		{ kind: 'code-cell', label: 'Code cell', hint: 'Runnable cell — outputs widgets' },
		{ kind: 'widget', label: 'Widget', hint: 'cx-widget JSON' },
		{ kind: 'raw', label: 'Raw', hint: 'Verbatim markdown' }
	];
</script>

<div class="group relative bg-slate-900 border border-slate-800 rounded-xl p-4 hover:border-slate-700 transition-colors">
	<div class="absolute -left-10 top-3 hidden group-hover:flex flex-col items-center gap-1 text-slate-600">
		<button
			onclick={() => onMove(index, -1)}
			disabled={index === 0}
			class="hover:text-slate-300 disabled:opacity-30 text-xs"
			aria-label="Move up"
			title="Move up"
		>↑</button>
		<button
			onclick={() => onMove(index, 1)}
			disabled={index >= total - 1}
			class="hover:text-slate-300 disabled:opacity-30 text-xs"
			aria-label="Move down"
			title="Move down"
		>↓</button>
	</div>

	<div class="flex items-center gap-2 mb-2 text-xs">
		<div class="relative">
			<button
				onclick={() => (showMenu = !showMenu)}
				class="text-slate-500 hover:text-slate-300 font-mono uppercase tracking-wide"
			>
				{block.kind}
				<span class="ml-1 text-slate-600">▾</span>
			</button>
			{#if showMenu}
				<div class="absolute z-10 left-0 top-6 bg-slate-950 border border-slate-700 rounded-lg shadow-xl py-1 w-56">
					{#each blockKindLabels as opt}
						<button
							onclick={() => changeBlockKind(opt.kind)}
							class="w-full text-left px-3 py-2 hover:bg-slate-800 flex flex-col"
						>
							<span class="text-slate-200 text-sm">{opt.label}</span>
							<span class="text-slate-500 text-xs">{opt.hint}</span>
						</button>
					{/each}
				</div>
			{/if}
		</div>

		{#if block.kind === 'heading'}
			<select
				value={block.level}
				onchange={(e) => setHeadingLevel(Number((e.target as HTMLSelectElement).value))}
				class="bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 text-slate-300 text-xs"
			>
				{#each [1, 2, 3, 4, 5, 6] as l}
					<option value={l}>H{l}</option>
				{/each}
			</select>
		{/if}

		{#if block.kind === 'code-block' || block.kind === 'code-cell'}
			<input
				type="text"
				value={block.lang}
				oninput={(e) => setCodeLang((e.target as HTMLInputElement).value)}
				placeholder="python"
				class="bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 text-slate-300 text-xs w-24"
			/>
		{/if}
		{#if block.kind === 'code-cell'}
			<input
				type="text"
				value={block.id ?? ''}
				oninput={(e) => setCodeId((e.target as HTMLInputElement).value)}
				placeholder="cell-id"
				class="bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 text-slate-300 text-xs w-28"
			/>
			<label class="flex items-center gap-1 text-slate-500">
				<input
					type="checkbox"
					checked={block.auto}
					onchange={(e) => setCodeAuto((e.target as HTMLInputElement).checked)}
					class="accent-primary-500"
				/>
				auto
			</label>
			<button
				onclick={() => onRun(index)}
				disabled={running}
				class="ml-auto bg-primary-600 hover:bg-primary-500 disabled:opacity-40 text-white text-xs font-medium px-3 py-1 rounded transition-colors"
			>
				{running ? 'Running…' : 'Run'}
			</button>
		{/if}

		{#if block.kind !== 'code-block' && block.kind !== 'code-cell'}
			<button
				onclick={() => (preview = !preview)}
				class="ml-auto text-slate-500 hover:text-slate-300"
			>{preview ? 'Edit' : 'Preview'}</button>
		{/if}

		<button
			onclick={() => onInsertAfter(index)}
			class="text-slate-500 hover:text-slate-300"
			aria-label="Insert below"
			title="Insert below"
		>+</button>
		<button
			onclick={() => onDelete(index)}
			class="text-slate-500 hover:text-red-400"
			aria-label="Delete block"
			title="Delete"
		>×</button>
	</div>

	{#if block.kind === 'divider'}
		<hr class="border-slate-700" />
	{:else if block.kind === 'code-block' || block.kind === 'code-cell'}
		<textarea
			value={block.source}
			oninput={(e) => setText((e.target as HTMLTextAreaElement).value)}
			rows={Math.max(3, block.source.split('\n').length)}
			class="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 font-mono text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-primary-500/40"
			spellcheck="false"
		></textarea>
		{#if block.kind === 'code-cell' && block.output && block.output.length > 0}
			{@const widgets = widgetSpecs(block.output)}
			{@const others = nonWidgetOutputs(block.output)}
			<div class="mt-3 space-y-3">
				{#each widgets as spec}
					<WidgetRenderer {spec} researchId={pageId} {apiBase} />
				{/each}
				{#if others.length > 0}
					<Output outputs={others} />
				{/if}
			</div>
		{/if}
	{:else if preview}
		{#if block.kind === 'widget'}
			<WidgetRenderer spec={block.spec} researchId={pageId} {apiBase} />
		{:else if block.kind === 'math'}
			<Markdown source={`$$\n${block.tex}\n$$`} />
		{:else if block.kind === 'heading'}
			<Markdown source={`${'#'.repeat(block.level)} ${block.text}`} />
		{:else}
			<Markdown source={blockText(block)} />
		{/if}
	{:else}
		<textarea
			value={blockText(block)}
			oninput={(e) => setText((e.target as HTMLTextAreaElement).value)}
			rows={Math.max(2, blockText(block).split('\n').length)}
			class="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-primary-500/40 {block.kind === 'widget' ? 'font-mono' : ''}"
			spellcheck={block.kind !== 'widget'}
		></textarea>
	{/if}
</div>
