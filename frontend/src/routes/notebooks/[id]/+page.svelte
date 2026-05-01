<script lang="ts">
  import { api, ApiError } from '$lib/api';
  import VisibilityBadge from '$lib/components/VisibilityBadge.svelte';
  import type { NotebookDetail, NotebookVersionInfo, Visibility } from '$lib/types';
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { auth } from '$lib/stores/auth.svelte';

  let notebook = $state<NotebookDetail | null>(null);
  let versions = $state<NotebookVersionInfo[] | null>(null);
  let error = $state<string | null>(null);
  let actionState = $state<'idle' | 'publishing' | 'unpublishing' | 'saving' | 'deleting'>('idle');

  const id = $derived(page.params.id ?? '');

  let title = $state('');
  let description = $state('');
  let visibility = $state<Visibility>('team');
  let allowedGroupsInput = $state('');
  let dirty = $state(false);

  async function load() {
    try {
      notebook = await api.getNotebook(id);
      title = notebook.title;
      description = notebook.description;
      visibility = notebook.visibility;
      allowedGroupsInput = notebook.allowed_groups.join(', ');
      dirty = false;
      if (notebook.can_edit) {
        try {
          versions = await api.listVersions(id);
        } catch {
          versions = [];
        }
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 401 && !auth.me?.authenticated) {
        // Layout will offer the sign-in CTA when we render <AuthGate>; the
        // detail page is gated by per-row visibility, so a 401 just means
        // "log in and we'll re-evaluate".
        error = 'Sign in to view this notebook.';
        return;
      }
      error = e instanceof Error ? e.message : 'Failed to load notebook';
    }
  }

  $effect(() => {
    if (id) void load();
  });

  function markDirty() {
    if (!notebook) return;
    dirty =
      title !== notebook.title ||
      description !== notebook.description ||
      visibility !== notebook.visibility ||
      allowedGroupsInput !== notebook.allowed_groups.join(', ');
  }

  async function saveMetadata() {
    if (!notebook || !dirty) return;
    actionState = 'saving';
    try {
      const groups = allowedGroupsInput
        .split(',')
        .map((g) => g.trim())
        .filter(Boolean);
      notebook = await api.updateNotebook(id, {
        title,
        description,
        visibility,
        allowed_groups: visibility === 'team' ? groups : []
      });
      dirty = false;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to save';
    } finally {
      actionState = 'idle';
    }
  }

  async function publish() {
    if (!notebook) return;
    actionState = 'publishing';
    try {
      await api.publishNotebook(id);
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to publish';
    } finally {
      actionState = 'idle';
    }
  }

  async function unpublish() {
    if (!notebook) return;
    actionState = 'unpublishing';
    try {
      await api.unpublishNotebook(id);
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to unpublish';
    } finally {
      actionState = 'idle';
    }
  }

  async function deleteNotebook() {
    if (!notebook) return;
    if (!confirm(`Delete "${notebook.title}"? This cannot be undone.`)) return;
    actionState = 'deleting';
    try {
      await api.deleteNotebook(id);
      await goto('/notebooks');
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to delete';
      actionState = 'idle';
    }
  }
</script>

<section class="mx-auto max-w-6xl px-6 py-10">
  {#if error}
    <div class="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>
  {:else if notebook === null}
    <div class="cryptopia-card h-40 animate-pulse rounded-xl"></div>
  {:else}
    <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
      <div class="min-w-0">
        <a href="/notebooks" class="text-xs text-slate-500 hover:text-slate-300">← Back to notebooks</a>
        <h1 class="mt-2 text-3xl font-bold tracking-tight text-slate-100 md:text-4xl">{notebook.title}</h1>
        <p class="mt-2 max-w-2xl text-slate-400">{notebook.description || 'No description.'}</p>
        <div class="mt-3 flex flex-wrap items-center gap-3 text-sm">
          <VisibilityBadge visibility={notebook.visibility} published={notebook.is_published} />
          <span class="text-slate-500">
            by <span class="text-slate-300">{notebook.owner.display_name || notebook.owner.username}</span>
          </span>
          {#if notebook.is_published && notebook.published_at}
            <span class="text-slate-500">·</span>
            <span class="text-slate-500"
              >Published v{notebook.published_version} ·
              {new Date(notebook.published_at).toLocaleString()}</span
            >
          {/if}
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        {#if notebook.can_edit}
          <a
            href={`/notebooks/${id}/edit`}
            class="inline-flex items-center gap-1 rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-slate-100 ring-1 ring-slate-700 transition hover:bg-slate-700"
          >
            <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path d="M2.695 14.763l-1.262 3.154a.5.5 0 00.65.65l3.155-1.262a4 4 0 001.343-.885L17.5 5.5a2.121 2.121 0 00-3-3L3.58 13.42a4 4 0 00-.885 1.343z" />
            </svg>
            Edit
          </a>
        {/if}
        {#if notebook.can_run}
          <a
            href={`/notebooks/${id}/run`}
            class="inline-flex items-center gap-1 rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 shadow shadow-sky-500/30 transition hover:bg-sky-400"
          >
            <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path d="M6.3 2.84A1 1 0 005 3.732v12.536a1 1 0 001.3.892l11-6.268a1 1 0 000-1.784l-11-6.268z" />
            </svg>
            Open dashboard
          </a>
        {:else if notebook.is_published && notebook.visibility === 'public'}
          <a
            href={`/p/${id}/`}
            target="_blank"
            rel="noreferrer"
            class="inline-flex items-center gap-1 rounded-lg border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-sky-400 hover:text-sky-300"
          >
            View static
            <svg class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" />
              <path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 100-2H5z" />
            </svg>
          </a>
        {/if}
      </div>
    </div>

    {#if notebook.can_edit}
      <div class="mt-10 grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div class="cryptopia-card rounded-xl p-6">
          <h2 class="text-lg font-semibold text-slate-100">Settings</h2>
          <p class="mt-1 text-sm text-slate-400">Visibility changes apply on the next publish.</p>

          <div class="mt-6 space-y-5">
            <div>
              <label for="title" class="block text-sm font-medium text-slate-300">Title</label>
              <input
                id="title"
                bind:value={title}
                oninput={markDirty}
                class="mt-1 w-full rounded-lg border border-slate-700/80 bg-slate-900/60 px-3 py-2 text-slate-100 outline-none transition focus:border-sky-400/60 focus:ring-2 focus:ring-sky-500/20"
              />
            </div>
            <div>
              <label for="desc" class="block text-sm font-medium text-slate-300">Description</label>
              <textarea
                id="desc"
                rows="3"
                bind:value={description}
                oninput={markDirty}
                class="mt-1 w-full resize-none rounded-lg border border-slate-700/80 bg-slate-900/60 px-3 py-2 text-slate-100 outline-none transition focus:border-sky-400/60 focus:ring-2 focus:ring-sky-500/20"
              ></textarea>
            </div>
            <fieldset>
              <legend class="text-sm font-medium text-slate-300">Visibility</legend>
              <div class="mt-2 flex gap-2">
                <label
                  class="flex flex-1 cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm transition {visibility === 'team'
                    ? 'border-sky-400/60 bg-sky-500/5'
                    : 'border-slate-700/80'}"
                >
                  <input type="radio" bind:group={visibility} value="team" onchange={markDirty} />
                  Team only
                </label>
                <label
                  class="flex flex-1 cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm transition {visibility === 'public'
                    ? 'border-emerald-400/60 bg-emerald-500/5'
                    : 'border-slate-700/80'}"
                >
                  <input type="radio" bind:group={visibility} value="public" onchange={markDirty} />
                  Public
                </label>
              </div>
            </fieldset>
            {#if visibility === 'team'}
              <div>
                <label for="groups" class="block text-sm font-medium text-slate-300">Allowed groups</label>
                <input
                  id="groups"
                  bind:value={allowedGroupsInput}
                  oninput={markDirty}
                  placeholder="researchers, quants"
                  class="mt-1 w-full rounded-lg border border-slate-700/80 bg-slate-900/60 px-3 py-2 text-slate-100 outline-none transition focus:border-sky-400/60 focus:ring-2 focus:ring-sky-500/20"
                />
                <p class="mt-1 text-xs text-slate-500">Comma-separated Authelia group names.</p>
              </div>
            {/if}
            <div class="flex items-center justify-end gap-3">
              <button
                onclick={saveMetadata}
                disabled={!dirty || actionState !== 'idle'}
                class="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-slate-100 transition hover:bg-slate-700 disabled:opacity-40"
              >
                {actionState === 'saving' ? 'Saving…' : dirty ? 'Save changes' : 'Saved'}
              </button>
            </div>
          </div>
        </div>

        <div class="space-y-6">
          <div class="cryptopia-card rounded-xl p-6">
            <h2 class="text-lg font-semibold text-slate-100">Publishing</h2>
            <p class="mt-1 text-sm text-slate-400">
              Snapshots the current draft so others can run it.
            </p>
            <div class="mt-4 flex flex-col gap-2">
              <button
                onclick={publish}
                disabled={actionState !== 'idle'}
                class="inline-flex items-center justify-center gap-1 rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 shadow shadow-sky-500/30 transition hover:bg-sky-400 disabled:opacity-50"
              >
                {actionState === 'publishing'
                  ? 'Publishing…'
                  : notebook.is_published
                    ? 'Re-publish snapshot'
                    : 'Publish'}
              </button>
              {#if notebook.is_published}
                <button
                  onclick={unpublish}
                  disabled={actionState !== 'idle'}
                  class="rounded-lg border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-amber-400 hover:text-amber-300 disabled:opacity-50"
                >
                  Unpublish
                </button>
              {/if}
            </div>
          </div>

          {#if versions && versions.length > 0}
            <div class="cryptopia-card rounded-xl p-6">
              <h2 class="text-lg font-semibold text-slate-100">Versions</h2>
              <ul class="mt-3 max-h-60 space-y-2 overflow-y-auto pr-2 scrollbar-thin">
                {#each versions as v (v.version)}
                  <li class="flex items-center justify-between rounded-md px-2 py-1.5 text-sm hover:bg-slate-800/60">
                    <span class="font-mono text-cyan-300">v{v.version}</span>
                    <span class="text-xs text-slate-500">
                      {new Date(v.published_at).toLocaleString()}
                    </span>
                  </li>
                {/each}
              </ul>
            </div>
          {/if}

          <div class="cryptopia-card rounded-xl p-6">
            <h2 class="text-lg font-semibold text-red-300">Danger zone</h2>
            <button
              onclick={deleteNotebook}
              disabled={actionState !== 'idle'}
              class="mt-3 w-full rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm font-medium text-red-300 transition hover:bg-red-500/20 disabled:opacity-50"
            >
              {actionState === 'deleting' ? 'Deleting…' : 'Delete notebook'}
            </button>
          </div>
        </div>
      </div>
    {/if}
  {/if}
</section>
