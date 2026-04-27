<script lang="ts">
	let {
		columns,
		data,
		title = ''
	}: {
		columns: string[];
		data: unknown[][];
		title?: string;
	} = $props();

	let pageSize = 20;
	let page = $state(0);
	let pageData = $derived(data.slice(page * pageSize, (page + 1) * pageSize));
	let totalPages = $derived(Math.ceil(data.length / pageSize));
</script>

<div class="widget-container p-0 overflow-hidden">
	{#if title}
		<div class="px-4 py-3 border-b border-slate-700">
			<p class="text-slate-300 text-sm font-medium">{title}</p>
		</div>
	{/if}
	<div class="overflow-x-auto">
		<table class="w-full text-sm">
			<thead>
				<tr class="bg-slate-800/80">
					<th class="text-slate-500 text-xs font-medium px-3 py-2 text-right w-10 border-r border-slate-700">#</th>
					{#each columns as col}
						<th class="text-slate-300 text-xs font-medium px-4 py-2 text-left whitespace-nowrap border-r border-slate-700/50 last:border-0">{col}</th>
					{/each}
				</tr>
			</thead>
			<tbody>
				{#each pageData as row, i}
					<tr class="border-t border-slate-800/50 hover:bg-slate-800/30 transition-colors">
						<td class="text-slate-600 text-xs px-3 py-2 text-right border-r border-slate-700/50">{page * pageSize + i}</td>
						{#each row as cell}
							<td class="text-slate-300 text-xs px-4 py-2 font-mono border-r border-slate-800/50 last:border-0 max-w-[200px] truncate">{String(cell)}</td>
						{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	{#if totalPages > 1}
		<div class="flex items-center justify-between px-4 py-3 border-t border-slate-700 bg-slate-800/30">
			<span class="text-slate-500 text-xs">{data.length} rows</span>
			<div class="flex items-center gap-2">
				<button
					onclick={() => page = Math.max(0, page - 1)}
					disabled={page === 0}
					class="text-xs text-slate-400 hover:text-white disabled:opacity-30 px-2 py-1 rounded hover:bg-slate-700 transition-colors"
				>← Prev</button>
				<span class="text-slate-500 text-xs">{page + 1} / {totalPages}</span>
				<button
					onclick={() => page = Math.min(totalPages - 1, page + 1)}
					disabled={page === totalPages - 1}
					class="text-xs text-slate-400 hover:text-white disabled:opacity-30 px-2 py-1 rounded hover:bg-slate-700 transition-colors"
				>Next →</button>
			</div>
		</div>
	{/if}
</div>
