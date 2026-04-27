<script lang="ts">
	import { codeToHtml } from 'shiki';
	import type { CodeCell, OutputRecord } from '$lib/md/extended';
	import {
		executionStore,
		isInputWidget,
		type WidgetSpec,
		type LiveOutputRecord
	} from '$lib/stores/execution';
	import WidgetRenderer from '$lib/components/widgets/WidgetRenderer.svelte';
	import Output from './Output.svelte';

	let {
		cell,
		pageId,
		apiBase,
		executionCount = null,
		hideInputWidgets = false,
		showSource = false
	}: {
		cell: CodeCell;
		pageId: number;
		apiBase: string;
		executionCount?: number | null;
		/** Skip input widgets (sliders/buttons/...) — used when the page-level
		 * viewer routes them to a sidebar. */
		hideInputWidgets?: boolean;
		/** Page-level default for whether the source is expanded. Each cell
		 * still has its own toggle; flipping this resets the per-cell override. */
		showSource?: boolean;
	} = $props();

	let localOverride = $state<boolean | null>(null);
	$effect(() => {
		void showSource;
		localOverride = null;
	});
	let sourceOpen = $derived(localOverride ?? showSource);

	let highlighted = $state('');
	let lineCount = $derived(cell.source ? cell.source.split('\n').length : 0);
	$effect(() => {
		if (!sourceOpen) return;
		const src = cell.source;
		const lang = cell.lang || 'python';
		codeToHtml(src, { lang, theme: 'one-dark-pro' })
			.then((h) => {
				highlighted = h;
			})
			.catch(() => {
				highlighted = `<pre class="bg-slate-900 p-4 text-slate-300"><code>${src
					.replace(/</g, '&lt;')
					.replace(/>/g, '&gt;')}</code></pre>`;
			});
	});

	let exec = $derived($executionStore);
	let cellState = $derived(cell.id ? exec.cells[cell.id] : null);

	// Live outputs from the kernel take precedence over cached ones.
	let activeOutputs = $derived.by((): OutputRecord[] | LiveOutputRecord[] => {
		if (cellState && cellState.outputs.length > 0) return cellState.outputs;
		return cell.output ?? [];
	});

	let isLive = $derived(!!cellState && cellState.outputs.length > 0);
	let isRunning = $derived(cellState?.status === 'running');

	function widgetSpecs(records: OutputRecord[] | LiveOutputRecord[]): WidgetSpec[] {
		const out: WidgetSpec[] = [];
		for (const r of records) {
			if ('type' in r && r.type === 'widget') {
				if (hideInputWidgets && isInputWidget(r.spec)) continue;
				out.push(r.spec);
			}
		}
		return out;
	}

	function nonWidgetOutputs(records: OutputRecord[] | LiveOutputRecord[]) {
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
			if (mime === 'text/plain') {
				out.push({ output_type: 'stream', text: data });
			} else {
				out.push({ output_type: 'display_data', data: { [mime]: data } });
			}
		}
		return out;
	}

	function run() {
		if (!cell.id || isRunning) return;
		void executionStore.runCell(pageId, apiBase, cell.id);
	}
</script>

<div class="space-y-1">
	<div class="font-mono text-sm">
		<div class="flex items-start gap-2">
			<span class="text-slate-600 text-xs pt-3 min-w-[3rem] text-right select-none">
				{#if isRunning}
					[*]
				{:else if executionCount !== null}
					[{executionCount}]
				{:else}
					[ ]
				{/if}
			</span>
			<div class="flex-1 rounded-lg overflow-hidden border border-slate-700/50">
				<div
					class="w-full flex items-center gap-2 px-3 py-1.5 bg-slate-900/70 text-xs text-slate-400 {sourceOpen
						? 'border-b border-slate-700/50'
						: ''}"
				>
					<button
						type="button"
						onclick={() => (localOverride = !sourceOpen)}
						aria-expanded={sourceOpen}
						class="flex items-center gap-2 hover:text-slate-200 transition-colors"
					>
						<svg
							class="w-3 h-3 transition-transform {sourceOpen ? 'rotate-90' : ''}"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M9 5l7 7-7 7"
							/>
						</svg>
						<span>{cell.lang || 'python'}</span>
						<span class="text-slate-600">·</span>
						<span>{lineCount} {lineCount === 1 ? 'line' : 'lines'}</span>
						{#if cell.id}
							<span class="text-slate-600">·</span>
							<span class="text-slate-500">#{cell.id}</span>
						{/if}
					</button>
					<button
						type="button"
						onclick={run}
						disabled={isRunning || !cell.id}
						class="ml-auto text-primary-400 hover:text-primary-300 disabled:text-slate-600 disabled:cursor-not-allowed text-xs"
					>
						{isRunning ? 'Running…' : 'Run'}
					</button>
				</div>
				{#if sourceOpen}
					{#if highlighted}
						{@html highlighted}
					{:else}
						<pre class="bg-slate-900 p-4 text-slate-300"><code>{cell.source}</code></pre>
					{/if}
				{/if}
			</div>
		</div>
	</div>

	{#if activeOutputs.length > 0}
		{@const widgets = widgetSpecs(activeOutputs)}
		{@const others = nonWidgetOutputs(activeOutputs)}
		{#if widgets.length > 0 || others.length > 0}
			<div class="pl-14 space-y-3">
				{#if isLive}
					<div class="flex items-center gap-1.5 text-xs text-green-400/80">
						<div class="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse"></div>
						<span>Live output</span>
					</div>
				{/if}
				{#each widgets as spec (spec.id)}
					<WidgetRenderer {spec} researchId={pageId} {apiBase} />
				{/each}
				{#if others.length > 0}
					<Output outputs={others} />
				{/if}
			</div>
		{/if}
	{/if}

	{#if cellState?.error}
		<div class="pl-14">
			<p class="text-red-400 text-xs bg-red-950/40 border border-red-800/50 rounded-md px-2 py-1.5">
				{cellState.error}
			</p>
		</div>
	{/if}
</div>
