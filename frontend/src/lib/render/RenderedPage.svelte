<script lang="ts">
	import type { Block } from '$lib/md/extended';
	import Block_ from './Block.svelte';

	let {
		blocks,
		pageId,
		apiBase,
		hideInputWidgets = false,
		showSources = false
	}: {
		blocks: Block[];
		pageId: number;
		apiBase: string;
		hideInputWidgets?: boolean;
		showSources?: boolean;
	} = $props();

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
</script>

<div class="space-y-6">
	{#each blocks as block, i}
		<Block_
			{block}
			{pageId}
			{apiBase}
			executionCount={execCounts[i]}
			{hideInputWidgets}
			{showSources}
		/>
	{/each}
</div>
