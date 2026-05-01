<script lang="ts">
  import '../app.css';
  import { auth, loginUrl } from '$lib/stores/auth.svelte';
  import { page } from '$app/state';

  interface Props {
    children?: import('svelte').Snippet;
  }
  let { children }: Props = $props();

  const me = $derived(auth.me);

  const navItems = [
    { href: '/', label: 'Gallery' },
    { href: '/notebooks', label: 'My notebooks', authRequired: true }
  ];
</script>

<svelte:head>
  <title>Cryptopia — Marimo dashboards</title>
</svelte:head>

<div class="flex min-h-screen flex-col">
  <header class="sticky top-0 z-30 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
    <div class="mx-auto flex h-14 max-w-7xl items-center gap-6 px-6">
      <a href="/" class="flex items-center gap-2 font-semibold tracking-tight">
        <span
          class="inline-flex h-7 w-7 items-center justify-center rounded-md bg-gradient-to-br from-sky-400 to-violet-500 text-slate-950 font-black"
          >C</span
        >
        <span class="text-slate-100">Cryptopia</span>
        <span class="hidden text-xs font-normal text-slate-500 sm:inline">data dashboards</span>
      </a>

      <nav class="flex flex-1 items-center gap-1 text-sm">
        {#each navItems as item}
          {#if !item.authRequired || me?.authenticated}
            <a
              href={item.href}
              class="rounded-md px-3 py-1.5 transition {page.url.pathname === item.href
                ? 'bg-slate-800 text-slate-100'
                : 'text-slate-400 hover:text-slate-100'}"
            >
              {item.label}
            </a>
          {/if}
        {/each}
      </nav>

      {#if auth.loading}
        <div class="h-6 w-20 animate-pulse rounded bg-slate-800"></div>
      {:else if me?.authenticated}
        <a
          href="/notebooks/new"
          class="hidden items-center gap-1 rounded-md bg-sky-500 px-3 py-1.5 text-sm font-semibold text-slate-950 shadow shadow-sky-500/30 transition hover:bg-sky-400 sm:inline-flex"
        >
          <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 5a.75.75 0 01.75.75v3.5h3.5a.75.75 0 010 1.5h-3.5v3.5a.75.75 0 01-1.5 0v-3.5h-3.5a.75.75 0 010-1.5h3.5v-3.5A.75.75 0 0110 5z" />
          </svg>
          New notebook
        </a>
        <div class="flex items-center gap-2">
          <span
            class="inline-flex h-7 w-7 items-center justify-center rounded-full bg-slate-700/80 text-xs font-semibold uppercase text-slate-200"
            title={me.email ?? ''}
          >
            {(me.name ?? me.username ?? '?')[0]}
          </span>
          <span class="hidden text-sm text-slate-300 sm:inline">{me.name ?? me.username}</span>
        </div>
      {:else}
        <a
          href={loginUrl(typeof window === 'undefined' ? '/' : window.location.href)}
          class="inline-flex items-center gap-1 rounded-md border border-slate-700 px-3 py-1.5 text-sm font-medium text-slate-200 transition hover:border-sky-400 hover:text-sky-300"
        >
          Sign in
        </a>
      {/if}
    </div>
  </header>

  <main class="flex-1">
    {#if children}
      {@render children()}
    {/if}
  </main>

  <footer class="border-t border-slate-800/60 py-6 text-center text-xs text-slate-500">
    Cryptopia · powered by
    <a class="text-slate-300 hover:text-sky-300" href="https://marimo.io" target="_blank" rel="noreferrer">marimo</a>
    ·
    auth via
    <a class="text-slate-300 hover:text-sky-300" href={me?.authelia_url ?? '#'} target="_blank" rel="noreferrer">Authelia</a>
  </footer>
</div>
