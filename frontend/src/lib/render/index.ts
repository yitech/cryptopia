/**
 * Render engine — turns a parsed Extended Markdown `Block[]` into DOM.
 *
 * Public boundary for rendering. Authors of new "extended" features (e.g.
 * a new widget kind, a new fenced extension) plug in here rather than
 * editing routes.
 *
 * The dispatcher (`Block.svelte`) routes each block to a renderer:
 *   - `paragraph` / `heading` / `list` / `quote` / `table` / `math` / `raw`
 *       → Markdown (CommonMark + GFM + KaTeX via `marked`)
 *   - `code-block`  → CodeBlock (display-only Shiki highlight)
 *   - `code-cell`   → CodeCell  (runtime cell, source default-collapsed)
 *   - `widget`      → WidgetRenderer (lib/components/widgets/)
 *   - `divider`     → <hr>
 */
export { default as RenderedPage } from './RenderedPage.svelte';
export { default as Block } from './Block.svelte';
export { default as Markdown } from './Markdown.svelte';
export { default as CodeBlock } from './CodeBlock.svelte';
export { default as CodeCell } from './CodeCell.svelte';
export { default as Output } from './Output.svelte';
