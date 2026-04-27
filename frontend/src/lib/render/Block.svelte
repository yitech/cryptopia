<script lang="ts">
	import type { Block } from '$lib/md/extended';
	import Markdown from './Markdown.svelte';
	import CodeBlock from './CodeBlock.svelte';
	import CodeCell from './CodeCell.svelte';
	import WidgetRenderer from '$lib/components/widgets/WidgetRenderer.svelte';

	let {
		block,
		pageId,
		apiBase,
		executionCount = null,
		hideInputWidgets = false,
		showSources = false
	}: {
		block: Block;
		pageId: number;
		apiBase: string;
		executionCount?: number | null;
		hideInputWidgets?: boolean;
		showSources?: boolean;
	} = $props();

	function blockToMarkdown(b: Block): string {
		switch (b.kind) {
			case 'paragraph':
			case 'list':
			case 'quote':
			case 'table':
			case 'raw':
				return b.raw;
			case 'heading':
				return `${'#'.repeat(b.level)} ${b.text}`;
			case 'math':
				return `$$\n${b.tex}\n$$`;
			default:
				return '';
		}
	}
</script>

{#if block.kind === 'code-cell'}
	<CodeCell
		cell={block}
		{pageId}
		{apiBase}
		{executionCount}
		{hideInputWidgets}
		showSource={showSources}
	/>
{:else if block.kind === 'code-block'}
	<div class="px-2">
		<CodeBlock source={block.source} lang={block.lang} />
	</div>
{:else if block.kind === 'widget'}
	<div class="px-2">
		<WidgetRenderer spec={block.spec} researchId={pageId} {apiBase} />
	</div>
{:else if block.kind === 'divider'}
	<hr class="border-slate-800" />
{:else}
	<div class="px-2 py-1">
		<Markdown source={blockToMarkdown(block)} />
	</div>
{/if}
