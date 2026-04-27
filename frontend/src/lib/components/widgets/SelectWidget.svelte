<script lang="ts">
	let {
		label,
		value = $bindable(),
		options,
		onchange
	}: {
		label: string;
		value: string;
		options: string[];
		onchange?: (v: string) => void;
	} = $props();
</script>

<div class="widget-container">
	<label for="select-{label}" class="block text-slate-300 text-sm font-medium mb-2">{label}</label>
	<select
		id="select-{label}"
		bind:value
		onchange={() => onchange?.(value)}
		class="w-full bg-slate-800 border border-slate-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500"
	>
		{#each options as opt}
			<option value={opt}>{opt}</option>
		{/each}
	</select>
</div>
