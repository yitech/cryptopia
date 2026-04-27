<script lang="ts">
	import '../app.css';
	import type { LayoutData } from './$types';

	let { data, children }: { data: LayoutData; children: import('svelte').Snippet } = $props();
	let user = $derived(data.user);

	let mobileMenuOpen = $state(false);
</script>

<div class="min-h-screen flex flex-col bg-slate-950">
	<nav class="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
		<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
			<div class="flex items-center justify-between h-16">
				<div class="flex items-center gap-8">
					<a href="/" class="flex items-center gap-2 group">
						<div class="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center text-white font-bold text-sm">C</div>
						<span class="text-white font-semibold text-lg tracking-tight">Cryptopia</span>
					</a>
					<div class="hidden md:flex items-center gap-6">
						<a href="/research" class="text-slate-400 hover:text-white transition-colors text-sm font-medium">Explore</a>
						{#if user}
							<a href="/publish" class="text-slate-400 hover:text-white transition-colors text-sm font-medium">Publish</a>
							<a href="/profile/{user.username}" class="text-slate-400 hover:text-white transition-colors text-sm font-medium">Profile</a>
						{/if}
					</div>
				</div>
				<div class="hidden md:flex items-center gap-3">
					{#if user}
						<span class="text-slate-400 text-sm">{user.username}</span>
						<form method="POST" action="/logout">
							<button type="submit" class="text-sm text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-md border border-slate-700 hover:border-slate-600">
								Sign out
							</button>
						</form>
					{:else}
						<a href="/login" class="text-sm text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-md">Sign in</a>
						<a href="/register" class="text-sm bg-primary-600 hover:bg-primary-500 text-white px-4 py-1.5 rounded-md transition-colors font-medium">Get started</a>
					{/if}
				</div>
				<button
					class="md:hidden text-slate-400 hover:text-white"
					onclick={() => (mobileMenuOpen = !mobileMenuOpen)}
					aria-label="Toggle menu"
				>
					<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						{#if mobileMenuOpen}
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
						{:else}
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
						{/if}
					</svg>
				</button>
			</div>
		</div>
		{#if mobileMenuOpen}
			<div class="md:hidden border-t border-slate-800 px-4 py-3 space-y-2 bg-slate-900">
				<a href="/research" class="block text-slate-400 hover:text-white text-sm py-2">Explore</a>
				{#if user}
					<a href="/publish" class="block text-slate-400 hover:text-white text-sm py-2">Publish</a>
					<a href="/profile/{user.username}" class="block text-slate-400 hover:text-white text-sm py-2">Profile</a>
					<form method="POST" action="/logout">
						<button type="submit" class="block text-slate-400 hover:text-white text-sm py-2 w-full text-left">Sign out</button>
					</form>
				{:else}
					<a href="/login" class="block text-slate-400 hover:text-white text-sm py-2">Sign in</a>
					<a href="/register" class="block text-primary-400 hover:text-primary-300 text-sm py-2 font-medium">Get started</a>
				{/if}
			</div>
		{/if}
	</nav>

	<main class="flex-1">
		{@render children()}
	</main>

	<footer class="border-t border-slate-800 bg-slate-900 py-8">
		<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between gap-4">
			<p class="text-slate-500 text-sm">© 2026 Cryptopia. Interactive research publishing.</p>
			<div class="flex items-center gap-6">
				<a href="/research" class="text-slate-500 hover:text-slate-400 text-sm">Explore</a>
				<a href="/publish" class="text-slate-500 hover:text-slate-400 text-sm">Publish</a>
			</div>
		</div>
	</footer>
</div>
