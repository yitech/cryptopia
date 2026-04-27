<script lang="ts">
	// Generic non-widget output renderer. Accepts the Jupyter-shaped records
	// used internally by CodeCell.svelte (stream / display_data / error).
	interface Output {
		output_type: string;
		text?: string | string[];
		data?: Record<string, string | string[]>;
		ename?: string;
		evalue?: string;
		traceback?: string[];
		execution_count?: number;
	}

	let { outputs }: { outputs: Output[] } = $props();

	function getText(val: string | string[] | undefined): string {
		if (!val) return '';
		if (Array.isArray(val)) return val.join('');
		return val;
	}

	function getHtml(output: Output): string | null {
		if (output.data?.['text/html']) {
			return getText(output.data['text/html']);
		}
		return null;
	}

	function getImage(output: Output): string | null {
		if (output.data?.['image/png']) {
			return `data:image/png;base64,${output.data['image/png']}`;
		}
		return null;
	}

	function getSvg(output: Output): string | null {
		if (output.data?.['image/svg+xml']) {
			return getText(output.data['image/svg+xml']);
		}
		return null;
	}

	function getPlainText(output: Output): string {
		if (output.output_type === 'stream') return getText(output.text);
		if (output.data?.['text/plain']) return getText(output.data['text/plain']);
		return '';
	}
</script>

<div class="space-y-1">
	{#each outputs as output}
		{#if output.output_type === 'error'}
			<div class="bg-red-950/40 border border-red-800/50 rounded-lg p-3 font-mono text-xs">
				<p class="text-red-400 font-semibold">{output.ename}: {output.evalue}</p>
				{#if output.traceback}
					<pre
						class="text-red-300/70 mt-1 overflow-x-auto whitespace-pre-wrap">{output.traceback
							.join('\n')
							.replace(/\x1b\[[0-9;]*m/g, '')}</pre>
				{/if}
			</div>
		{:else if getHtml(output)}
			<div class="bg-slate-900/50 border border-slate-700/30 rounded-lg p-3 overflow-x-auto">
				{@html getHtml(output)}
			</div>
		{:else if getImage(output)}
			<div class="bg-slate-900/50 border border-slate-700/30 rounded-lg p-3">
				<img src={getImage(output)} alt="Output" class="max-w-full rounded" />
			</div>
		{:else if getSvg(output)}
			<div class="bg-slate-900/50 border border-slate-700/30 rounded-lg p-3 overflow-x-auto">
				{@html getSvg(output)}
			</div>
		{:else if getPlainText(output)}
			<pre
				class="bg-slate-900/50 border border-slate-700/30 rounded-lg p-3 text-slate-300 text-xs font-mono overflow-x-auto whitespace-pre-wrap">{getPlainText(
					output
				)}</pre>
		{/if}
	{/each}
</div>
