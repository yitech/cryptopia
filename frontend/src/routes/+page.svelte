<script lang="ts">
  import { api } from '$lib/api';
  import NotebookCard from '$lib/components/NotebookCard.svelte';
  import type { NotebookSummary } from '$lib/types';
  import { auth } from '$lib/stores/auth.svelte';

  let notebooks = $state<NotebookSummary[] | null>(null);
  let error = $state<string | null>(null);

  async function load() {
    try {
      notebooks = await api.listNotebooks();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load notebooks';
    }
  }

  $effect(() => {
    void load();
  });

  const me = $derived(auth.me);
</script>

<section class="mx-auto max-w-7xl px-6 py-12">
  <div class="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
    <div>
      <p class="text-sm font-medium uppercase tracking-widest text-sky-400/80">Dashboards</p>
      <h1 class="mt-2 text-3xl font-bold tracking-tight text-slate-100 md:text-4xl">
        {#if me?.authenticated}
          Welcome back, {me.name ?? me.username}
        {:else}
          Notebooks visible to you
        {/if}
      </h1>
      <p class="mt-3 max-w-xl text-slate-400">
        Live, reactive marimo notebooks with team-aware access control. Browse what's shared,
        or
        {#if me?.authenticated}
          <a href="/notebooks/new" class="text-sky-300 hover:text-sky-200">create your own dashboard</a>.
        {:else}
          sign in to start authoring.
        {/if}
      </p>
    </div>
    {#if me?.authenticated}
      <a
        href="/notebooks/new"
        class="inline-flex items-center justify-center gap-2 rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 shadow shadow-sky-500/30 transition hover:bg-sky-400"
      >
        New notebook
      </a>
    {/if}
  </div>

  <div class="mt-10">
    {#if error}
      <div class="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
        {error}
      </div>
    {:else if notebooks === null}
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {#each Array(6) as _}
          <div class="cryptopia-card h-32 animate-pulse rounded-xl"></div>
        {/each}
      </div>
    {:else if notebooks.length === 0}
      <div class="cryptopia-card rounded-xl px-6 py-12 text-center text-slate-400">
        <p>No notebooks visible yet.</p>
        {#if me?.authenticated}
          <a class="mt-3 inline-block text-sky-300 hover:text-sky-200" href="/notebooks/new">Create the first one →</a>
        {/if}
      </div>
    {:else}
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {#each notebooks as nb (nb.id)}
          <NotebookCard notebook={nb} />
        {/each}
      </div>
    {/if}
  </div>
</section>
