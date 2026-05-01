<script lang="ts">
  import { auth, loginUrl } from '$lib/stores/auth.svelte';
  import { page } from '$app/state';

  interface Props {
    children?: import('svelte').Snippet;
    title?: string;
    description?: string;
  }

  let { children, title = 'Sign in to continue', description = 'Cryptopia uses Authelia for single sign-on. You will be redirected to your identity provider.' }: Props = $props();

  const me = $derived(auth.me);
</script>

{#if auth.loading}
  <div class="flex min-h-[40vh] items-center justify-center text-slate-500">
    <div class="animate-pulse">Checking your session…</div>
  </div>
{:else if !me?.authenticated}
  <div class="mx-auto flex max-w-md flex-col items-center px-6 py-24 text-center">
    <div class="rounded-full bg-sky-500/10 p-4 ring-1 ring-sky-400/30">
      <svg class="h-10 w-10 text-sky-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"
        />
      </svg>
    </div>
    <h2 class="mt-4 text-xl font-semibold text-slate-100">{title}</h2>
    <p class="mt-2 text-sm text-slate-400">{description}</p>
    <a
      href={loginUrl(typeof window === 'undefined' ? '/' : window.location.href)}
      class="mt-6 inline-flex items-center justify-center rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-semibold text-slate-950 shadow shadow-sky-500/30 transition hover:bg-sky-400"
    >
      Sign in with Authelia
    </a>
    <p class="mt-3 text-xs text-slate-500">{me?.authelia_url ?? ''}</p>
    {#if page.url.pathname !== '/'}
      <a href="/" class="mt-6 text-xs text-slate-500 hover:text-slate-300">← Back to gallery</a>
    {/if}
  </div>
{:else if children}
  {@render children()}
{/if}
