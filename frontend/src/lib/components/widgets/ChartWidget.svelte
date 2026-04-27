<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import type { ECharts } from 'echarts';

	let {
		option,
		height = 400
	}: {
		option: Record<string, unknown>;
		height?: number;
	} = $props();

	let container: HTMLDivElement;
	let chart: ECharts | undefined = $state(undefined);

	onMount(() => {
		let resizeObserver: ResizeObserver | undefined;
		import('echarts').then((echarts) => {
			chart = echarts.init(container, 'dark');
			resizeObserver = new ResizeObserver(() => chart?.resize());
			resizeObserver.observe(container);
		});
		return () => resizeObserver?.disconnect();
	});

	// Re-apply the option whenever it changes OR the chart instance becomes
	// available. Two subtleties matter here:
	//  1. `chart` is `$state` so the effect re-runs once echarts finishes
	//     loading asynchronously (otherwise the first option set inside the
	//     import callback would be the only one that ever lands when the
	//     import beats the first effect run, and nothing would land when it
	//     loses that race).
	//  2. We read both signals unconditionally before the early-return. With a
	//     short-circuited `if (!chart || !option) return` the effect only
	//     tracks `chart` on its first run (when chart is undefined), and would
	//     never re-fire when `option` changes later.
	$effect(() => {
		const c = chart;
		const opt = option;
		if (!c || !opt) return;
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		c.setOption(opt as any, true);
	});

	onDestroy(() => chart?.dispose());
</script>

<div class="widget-container p-0 overflow-hidden">
	<div bind:this={container} style="height: {height}px; width: 100%;"></div>
</div>
