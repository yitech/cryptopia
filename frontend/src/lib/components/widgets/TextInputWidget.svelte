<script lang="ts">
	let {
		label,
		value = $bindable(),
		placeholder = '',
		onsubmit
	}: {
		label: string;
		value: string;
		placeholder?: string;
		onsubmit?: (v: string) => void;
	} = $props();
</script>

<div class="widget-container">
	<label for="textinput-{label}" class="block text-slate-300 text-sm font-medium mb-2">{label}</label>
	<input
		id="textinput-{label}"
		type="text"
		bind:value
		{placeholder}
		onkeydown={(e) => e.key === 'Enter' && onsubmit?.(value)}
		class="w-full bg-slate-800 border border-slate-600 text-white placeholder-slate-500 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500"
	/>
</div>
