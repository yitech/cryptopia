<script lang="ts">
	import type { PageData } from './$types';
	let { data }: { data: PageData } = $props();

	const features = [
		{
			icon: '📓',
			title: 'Jupyter Notebooks',
			desc: 'Push your .ipynb files and they render beautifully with code, outputs, and prose.'
		},
		{
			icon: '∑',
			title: 'Math Rendering',
			desc: 'Inline and block LaTeX renders via KaTeX. Write equations naturally in markdown cells.'
		},
		{
			icon: '🎛️',
			title: 'Interactive Widgets',
			desc: 'Sliders, dropdowns, charts and more. Readers adjust parameters and see live results.'
		},
		{
			icon: '▶️',
			title: 'Live Code Execution',
			desc: 'Server-side Python execution with a kernel pool. Code runs, outputs stream back.'
		},
		{
			icon: '🔀',
			title: 'Git Publishing',
			desc: 'git push to publish. Version your research the same way you version your code.'
		},
		{
			icon: '📊',
			title: 'Rich Visualizations',
			desc: 'ECharts and Plotly integration. Beautiful interactive charts out of the box.'
		}
	];
</script>

<svelte:head>
	<title>Cryptopia — Interactive Research Platform</title>
</svelte:head>

<!-- Hero -->
<section class="relative overflow-hidden bg-slate-950">
	<div class="absolute inset-0 bg-gradient-to-br from-primary-900/20 via-slate-950 to-slate-950 pointer-events-none"></div>
	<div class="absolute top-1/4 left-1/4 w-96 h-96 bg-primary-600/10 rounded-full blur-3xl pointer-events-none"></div>
	<div class="absolute bottom-1/4 right-1/4 w-64 h-64 bg-violet-600/10 rounded-full blur-3xl pointer-events-none"></div>

	<div class="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 lg:py-36">
		<div class="max-w-3xl">
			<div class="inline-flex items-center gap-2 bg-primary-900/40 text-primary-300 text-xs font-medium px-3 py-1.5 rounded-full border border-primary-700/50 mb-6">
				<span class="w-1.5 h-1.5 rounded-full bg-primary-400"></span>
				Interactive research publishing
			</div>
			<h1 class="text-5xl lg:text-7xl font-bold text-white leading-tight tracking-tight mb-6">
				Research that
				<span class="bg-gradient-to-r from-primary-400 to-violet-400 bg-clip-text text-transparent"> lives and breathes</span>
			</h1>
			<p class="text-xl text-slate-400 leading-relaxed mb-10 max-w-2xl">
				Publish Jupyter notebooks as interactive research papers. Readers explore your findings
				with live widgets, runnable code, and beautiful math rendering — not static PDFs.
			</p>
			<div class="flex flex-col sm:flex-row gap-4">
				{#if data.user}
					<a href="/publish" class="inline-flex items-center justify-center gap-2 bg-primary-600 hover:bg-primary-500 text-white font-semibold px-8 py-3.5 rounded-xl transition-all duration-200 hover:shadow-lg hover:shadow-primary-500/25">
						Publish research
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
						</svg>
					</a>
				{:else}
					<a href="/register" class="inline-flex items-center justify-center gap-2 bg-primary-600 hover:bg-primary-500 text-white font-semibold px-8 py-3.5 rounded-xl transition-all duration-200 hover:shadow-lg hover:shadow-primary-500/25">
						Start publishing
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
						</svg>
					</a>
				{/if}
				<a href="/research" class="inline-flex items-center justify-center gap-2 text-slate-300 hover:text-white border border-slate-700 hover:border-slate-600 font-medium px-8 py-3.5 rounded-xl transition-all duration-200">
					Explore research
				</a>
			</div>
		</div>
	</div>
</section>

<!-- Features -->
<section class="py-24 bg-slate-900">
	<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
		<div class="text-center mb-16">
			<h2 class="text-3xl font-bold text-white mb-4">Everything a researcher needs</h2>
			<p class="text-slate-400 max-w-xl mx-auto">From writing to publishing to reader interaction — all in one platform.</p>
		</div>
		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
			{#each features as feature}
				<div class="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6 hover:border-slate-600/50 transition-colors">
					<div class="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-600/30 to-primary-700/30 border border-primary-600/30 flex items-center justify-center mb-4 text-xl">
						{feature.icon}
					</div>
					<h3 class="text-white font-semibold mb-2">{feature.title}</h3>
					<p class="text-slate-400 text-sm leading-relaxed">{feature.desc}</p>
				</div>
			{/each}
		</div>
	</div>
</section>

<!-- CTA -->
<section class="py-24 bg-slate-950">
	<div class="max-w-3xl mx-auto px-4 text-center">
		<h2 class="text-4xl font-bold text-white mb-4">Ready to publish your research?</h2>
		<p class="text-slate-400 mb-8">Push a git repo with your notebooks. We handle the rest.</p>
		{#if !data.user}
			<a href="/register" class="inline-flex items-center gap-2 bg-primary-600 hover:bg-primary-500 text-white font-semibold px-8 py-4 rounded-xl transition-all duration-200 text-lg">
				Create free account
			</a>
		{:else}
			<a href="/publish" class="inline-flex items-center gap-2 bg-primary-600 hover:bg-primary-500 text-white font-semibold px-8 py-4 rounded-xl transition-all duration-200 text-lg">
				Go to dashboard
			</a>
		{/if}
	</div>
</section>
