<script lang="ts">
	import { codeToHtml } from 'shiki';

	let {
		source,
		lang = ''
	}: {
		source: string;
		lang?: string;
	} = $props();

	let highlighted = $state('');

	$effect(() => {
		const src = source;
		const language = lang || 'text';
		codeToHtml(src, { lang: language, theme: 'one-dark-pro' })
			.then((h) => {
				highlighted = h;
			})
			.catch(() => {
				highlighted = `<pre class="bg-slate-900 p-4 text-slate-300"><code>${src
					.replace(/</g, '&lt;')
					.replace(/>/g, '&gt;')}</code></pre>`;
			});
	});
</script>

<div class="rounded-lg overflow-hidden border border-slate-700/50 font-mono text-sm">
	{#if highlighted}
		{@html highlighted}
	{:else}
		<pre class="bg-slate-900 p-4 text-slate-300"><code>{source}</code></pre>
	{/if}
</div>
