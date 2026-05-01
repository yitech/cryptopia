<script lang="ts">
  import { api, ApiError } from '$lib/api';
  import AuthGate from '$lib/components/AuthGate.svelte';
  import { goto } from '$app/navigation';
  import { auth } from '$lib/stores/auth.svelte';
  import type { Visibility } from '$lib/types';

  let title = $state('');
  let description = $state('');
  let visibility = $state<Visibility>('team');
  let allowedGroupsInput = $state('');
  let submitting = $state(false);
  let error = $state<string | null>(null);

  $effect(() => {
    // Pre-populate allowed groups with the user's first group as a sensible
    // default — a researcher creating a team-only notebook almost always
    // wants their own team.
    if (visibility === 'team' && !allowedGroupsInput && auth.me?.groups.length) {
      allowedGroupsInput = auth.me.groups[0];
    }
  });

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (!title.trim()) {
      error = 'Title is required';
      return;
    }
    submitting = true;
    error = null;
    try {
      const groups = allowedGroupsInput
        .split(',')
        .map((g) => g.trim())
        .filter(Boolean);
      const nb = await api.createNotebook({
        title: title.trim(),
        description: description.trim(),
        visibility,
        allowed_groups: visibility === 'team' ? groups : []
      });
      await goto(`/notebooks/${nb.id}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : 'Failed to create notebook';
    } finally {
      submitting = false;
    }
  }
</script>

<section class="mx-auto max-w-2xl px-6 py-12">
  <AuthGate title="Sign in to create a notebook" description="Authoring requires a signed-in identity so we can attach ownership and permissions.">
    <p class="text-sm font-medium uppercase tracking-widest text-sky-400/80">Create</p>
    <h1 class="mt-2 text-3xl font-bold tracking-tight text-slate-100">New notebook</h1>
    <p class="mt-2 text-slate-400">
      Cryptopia will seed a marimo notebook for you. You can edit it in the browser and publish
      whenever it's ready.
    </p>

    <form onsubmit={submit} class="mt-8 space-y-6">
      <div>
        <label for="title" class="block text-sm font-medium text-slate-300">Title</label>
        <input
          id="title"
          type="text"
          required
          maxlength="255"
          bind:value={title}
          placeholder="e.g. BTC vs ETH realised volatility"
          class="mt-1 w-full rounded-lg border border-slate-700/80 bg-slate-900/60 px-3 py-2 text-slate-100 outline-none ring-sky-500/0 transition focus:border-sky-400/60 focus:ring-2"
        />
      </div>

      <div>
        <label for="description" class="block text-sm font-medium text-slate-300">Description</label>
        <textarea
          id="description"
          rows="3"
          bind:value={description}
          placeholder="What's this dashboard about?"
          class="mt-1 w-full resize-none rounded-lg border border-slate-700/80 bg-slate-900/60 px-3 py-2 text-slate-100 outline-none ring-sky-500/0 transition focus:border-sky-400/60 focus:ring-2"
        ></textarea>
      </div>

      <fieldset>
        <legend class="text-sm font-medium text-slate-300">Visibility</legend>
        <div class="mt-2 grid gap-3 sm:grid-cols-2">
          <label
            class="flex cursor-pointer items-start gap-3 rounded-lg border px-4 py-3 transition {visibility === 'team'
              ? 'border-sky-400/60 bg-sky-500/5'
              : 'border-slate-700/80 hover:border-slate-600'}"
          >
            <input type="radio" bind:group={visibility} value="team" class="mt-1" />
            <span>
              <span class="block font-medium text-slate-100">Team only</span>
              <span class="mt-1 block text-xs text-slate-400"
                >Only members of the listed Authelia groups can see or run this notebook.</span
              >
            </span>
          </label>
          <label
            class="flex cursor-pointer items-start gap-3 rounded-lg border px-4 py-3 transition {visibility === 'public'
              ? 'border-emerald-400/60 bg-emerald-500/5'
              : 'border-slate-700/80 hover:border-slate-600'}"
          >
            <input type="radio" bind:group={visibility} value="public" class="mt-1" />
            <span>
              <span class="block font-medium text-slate-100">Public</span>
              <span class="mt-1 block text-xs text-slate-400">
                Anyone can view a static WASM render. Backend-powered interactions still require sign-in.
              </span>
            </span>
          </label>
        </div>
      </fieldset>

      {#if visibility === 'team'}
        <div>
          <label for="groups" class="block text-sm font-medium text-slate-300">Allowed groups</label>
          <input
            id="groups"
            type="text"
            bind:value={allowedGroupsInput}
            placeholder="researchers, quants"
            class="mt-1 w-full rounded-lg border border-slate-700/80 bg-slate-900/60 px-3 py-2 text-slate-100 outline-none ring-sky-500/0 transition focus:border-sky-400/60 focus:ring-2"
          />
          <p class="mt-1 text-xs text-slate-500">
            Comma-separated. Must match Authelia group names. Your groups: {auth.me?.groups.join(', ') ||
              '(none)'}
          </p>
        </div>
      {/if}

      {#if error}
        <div class="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>
      {/if}

      <div class="flex items-center justify-end gap-3">
        <a href="/notebooks" class="text-sm text-slate-400 hover:text-slate-200">Cancel</a>
        <button
          type="submit"
          disabled={submitting}
          class="inline-flex items-center justify-center gap-2 rounded-lg bg-sky-500 px-5 py-2 text-sm font-semibold text-slate-950 shadow shadow-sky-500/30 transition hover:bg-sky-400 disabled:opacity-50"
        >
          {submitting ? 'Creating…' : 'Create notebook'}
        </button>
      </div>
    </form>
  </AuthGate>
</section>
