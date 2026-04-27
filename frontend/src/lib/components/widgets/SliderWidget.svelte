<script lang="ts">
	let {
		label,
		value = $bindable(),
		min = 0,
		max = 100,
		step = 1,
		onchange
	}: {
		label: string;
		value: number;
		min?: number;
		max?: number;
		step?: number;
		onchange?: (v: number) => void;
	} = $props();
</script>

<div class="widget-container">
	<div class="flex items-center justify-between mb-2">
		<label for="slider-{label}" class="text-slate-300 text-sm font-medium">{label}</label>
		<span class="text-primary-400 text-sm font-mono font-semibold">{value}</span>
	</div>
	<input
		id="slider-{label}"
		type="range"
		bind:value
		{min}
		{max}
		{step}
		onchange={() => onchange?.(value)}
		class="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-primary-500"
	/>
	<div class="flex justify-between text-slate-600 text-xs mt-1">
		<span>{min}</span>
		<span>{max}</span>
	</div>
</div>
