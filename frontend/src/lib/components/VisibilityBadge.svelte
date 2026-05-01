<script lang="ts">
  import type { Visibility } from '$lib/types';

  interface Props {
    visibility: Visibility;
    published?: boolean;
  }

  let { visibility, published = false }: Props = $props();
</script>

<span
  class="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium {visibility ===
  'public'
    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
    : 'border-violet-500/30 bg-violet-500/10 text-violet-300'}"
>
  {#if visibility === 'public'}
    <svg class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
      <path
        fill-rule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm.75-13.25a.75.75 0 00-1.5 0v4.5l-3.072-3.072a.75.75 0 00-1.06 1.06L8.94 10.5l-3.823 3.262a.75.75 0 101.061 1.06L10 11.06v3.69a.75.75 0 001.5 0v-3.69l3.823 3.262a.75.75 0 101.061-1.06L11.06 10.5l3.822-3.262a.75.75 0 10-1.06-1.06L10.75 9.25v-4.5z"
        clip-rule="evenodd"
      />
    </svg>
    Public
  {:else}
    <svg class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
      <path
        d="M9 4.5a.75.75 0 01.75.75v2h.5a.75.75 0 010 1.5h-.5v6h.5a.75.75 0 010 1.5h-2.5a.75.75 0 010-1.5h.5v-6h-.5a.75.75 0 010-1.5h.5v-2A.75.75 0 019 4.5zM6.5 4.5a.75.75 0 01.75.75v2h-.5a.75.75 0 000 1.5h.5v6h-.5a.75.75 0 000 1.5h.5a.75.75 0 010 1.5H4.75A.75.75 0 014 15.75v-9.5A.75.75 0 014.75 5.5h1z"
      />
    </svg>
    Team
  {/if}
  {#if !published}
    <span class="ml-1 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">Draft</span>
  {/if}
</span>
