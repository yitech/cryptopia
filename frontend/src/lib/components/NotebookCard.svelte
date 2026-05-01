<script lang="ts">
  import type { NotebookSummary } from '$lib/types';
  import VisibilityBadge from './VisibilityBadge.svelte';

  interface Props {
    notebook: NotebookSummary;
  }

  let { notebook }: Props = $props();

  const updated = $derived(new Date(notebook.updated_at));
  const isPublished = $derived(notebook.published_version !== null);
</script>

<a
  href={`/notebooks/${notebook.id}`}
  class="cryptopia-card group block rounded-xl p-5 transition-all hover:-translate-y-0.5 hover:shadow-xl hover:shadow-cyan-500/10"
>
  <div class="flex items-start justify-between gap-3">
    <div class="min-w-0">
      <h3 class="truncate font-semibold text-slate-100 group-hover:text-sky-300">
        {notebook.title}
      </h3>
      <p class="mt-1 line-clamp-2 text-sm text-slate-400">
        {notebook.description || 'No description yet.'}
      </p>
    </div>
    <VisibilityBadge visibility={notebook.visibility} published={isPublished} />
  </div>

  <div class="mt-4 flex items-center gap-3 text-xs text-slate-500">
    <span class="inline-flex items-center gap-1">
      <span class="inline-flex h-5 w-5 items-center justify-center rounded-full bg-slate-700/60 text-[10px] uppercase">
        {notebook.owner.display_name?.[0] ?? notebook.owner.username[0]}
      </span>
      <span>{notebook.owner.display_name || notebook.owner.username}</span>
    </span>
    <span class="text-slate-600">·</span>
    <time datetime={notebook.updated_at}>
      Updated {updated.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
    </time>
    {#if isPublished}
      <span class="text-slate-600">·</span>
      <span class="text-cyan-400/80">v{notebook.published_version}</span>
    {/if}
  </div>
</a>
