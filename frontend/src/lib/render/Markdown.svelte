<script lang="ts">
	import { marked } from 'marked';
	import markedKatex from 'marked-katex-extension';

	let { source }: { source: string } = $props();

	let html = $state('');

	marked.use(markedKatex({ throwOnError: false, output: 'html' }));

	$effect(() => {
		html = marked.parse(source) as string;
	});
</script>

<div class="prose prose-invert prose-slate max-w-none prose-headings:font-semibold prose-code:text-primary-300 prose-code:bg-slate-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none prose-pre:bg-slate-900 prose-pre:border prose-pre:border-slate-700">
	{@html html}
</div>
