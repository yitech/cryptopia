<script lang="ts">
  import { page } from '$app/state';

  const id = $derived(page.params.id ?? '');
  const runUrl = $derived(`/run/${id}/`);
</script>

<div class="flex h-[calc(100vh-3.5rem)] flex-col">
  <div class="flex items-center justify-between border-b border-slate-800 bg-slate-950 px-4 py-2 text-sm">
    <a href={`/notebooks/${id}`} class="inline-flex items-center gap-1 text-slate-400 hover:text-slate-100">
      <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
        <path
          fill-rule="evenodd"
          d="M9.707 14.707a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 1.414L7.414 9H17a1 1 0 110 2H7.414l2.293 2.293a1 1 0 010 1.414z"
          clip-rule="evenodd"
        />
      </svg>
      Back to notebook
    </a>
    <span class="font-mono text-xs text-slate-500">marimo run · {id}</span>
    <span></span>
  </div>
  <iframe
    title="marimo dashboard"
    src={runUrl}
    class="flex-1 border-0 bg-slate-950"
    allow="clipboard-read; clipboard-write"
  ></iframe>
</div>
