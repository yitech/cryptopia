<script lang="ts">
	import { enhance } from '$app/forms';
	import type { ActionData } from './$types';

	let { form }: { form: ActionData } = $props();
	let loading = $state(false);
</script>

<svelte:head>
	<title>Create account — Cryptopia</title>
</svelte:head>

<div class="min-h-[80vh] flex items-center justify-center px-4 py-12">
	<div class="w-full max-w-md">
		<div class="text-center mb-8">
			<a href="/" class="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 text-white font-bold text-xl mb-4">C</a>
			<h1 class="text-2xl font-bold text-white">Create your account</h1>
			<p class="text-slate-400 mt-1">Start publishing interactive research</p>
		</div>

		<div class="bg-slate-900 border border-slate-800 rounded-2xl p-8">
			{#if form?.error}
				<div class="bg-red-900/30 border border-red-700/50 text-red-300 text-sm px-4 py-3 rounded-lg mb-6">
					{form.error}
				</div>
			{/if}

			<form
				method="POST"
				use:enhance={() => {
					loading = true;
					return async ({ update }) => {
						loading = false;
						update();
					};
				}}
				class="space-y-5"
			>
				<div>
					<label for="full_name" class="block text-sm font-medium text-slate-300 mb-1.5">Full name <span class="text-slate-500">(optional)</span></label>
					<input
						id="full_name"
						name="full_name"
						type="text"
						autocomplete="name"
						class="w-full bg-slate-800 border border-slate-700 text-white placeholder-slate-500 rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 transition-colors"
						placeholder="Ada Lovelace"
					/>
				</div>
				<div>
					<label for="username" class="block text-sm font-medium text-slate-300 mb-1.5">Username</label>
					<input
						id="username"
						name="username"
						type="text"
						autocomplete="username"
						required
						pattern="[a-zA-Z0-9_\-]+"
						class="w-full bg-slate-800 border border-slate-700 text-white placeholder-slate-500 rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 transition-colors"
						placeholder="ada_lovelace"
					/>
					<p class="text-slate-500 text-xs mt-1">Letters, numbers, underscores and hyphens only.</p>
				</div>
				<div>
					<label for="email" class="block text-sm font-medium text-slate-300 mb-1.5">Email</label>
					<input
						id="email"
						name="email"
						type="email"
						autocomplete="email"
						required
						class="w-full bg-slate-800 border border-slate-700 text-white placeholder-slate-500 rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 transition-colors"
						placeholder="ada@example.com"
					/>
				</div>
				<div>
					<label for="password" class="block text-sm font-medium text-slate-300 mb-1.5">Password</label>
					<input
						id="password"
						name="password"
						type="password"
						autocomplete="new-password"
						required
						minlength="8"
						class="w-full bg-slate-800 border border-slate-700 text-white placeholder-slate-500 rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 transition-colors"
						placeholder="At least 8 characters"
					/>
				</div>
				<button
					type="submit"
					disabled={loading}
					class="w-full bg-primary-600 hover:bg-primary-500 disabled:opacity-60 text-white font-semibold py-2.5 rounded-lg transition-colors text-sm"
				>
					{loading ? 'Creating account…' : 'Create account'}
				</button>
			</form>

			<p class="text-center text-slate-500 text-sm mt-6">
				Already have an account?
				<a href="/login" class="text-primary-400 hover:text-primary-300 font-medium">Sign in</a>
			</p>
		</div>
	</div>
</div>
