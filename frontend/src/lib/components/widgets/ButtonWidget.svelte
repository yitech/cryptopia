<script lang="ts">
	let {
		label,
		onclick
	}: {
		label: string;
		onclick?: () => void;
	} = $props();
</script>

<div class="widget-container">
	<button
		type="button"
		onclick={() => onclick?.()}
		class="w-full bg-primary-600 hover:bg-primary-500 text-white font-medium py-2 px-4 rounded-lg text-sm transition-colors"
	>
		{label}
	</button>
</div>
