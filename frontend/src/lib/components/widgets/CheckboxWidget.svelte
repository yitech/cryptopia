<script lang="ts">
	let {
		label,
		value = $bindable(),
		onchange
	}: {
		label: string;
		value: boolean;
		onchange?: (v: boolean) => void;
	} = $props();
</script>

<div class="widget-container">
	<label class="flex items-center gap-3 cursor-pointer">
		<input
			type="checkbox"
			bind:checked={value}
			onchange={() => onchange?.(value)}
			class="w-4 h-4 rounded accent-primary-500 cursor-pointer"
		/>
		<span class="text-slate-300 text-sm font-medium">{label}</span>
	</label>
</div>
