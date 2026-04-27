/**
 * Cryptopia Extended Markdown — parser and serializer.
 *
 * Spec: docs/extended-markdown.md
 *
 * The same block model is used by:
 *   - the SSR viewer (frontend/src/routes/research/[u]/[s])
 *   - the block editor (frontend/src/routes/edit/[id])
 *   - the .md import / export endpoints
 *
 * We avoid third-party Markdown parsers here so the same module loads cheaply
 * in both Node (SSR) and the browser (editor). Block-level CommonMark/GFM is
 * sufficient for our segmentation; inline rendering is delegated to `marked`
 * inside MarkdownCell.svelte at view time.
 */

import type { WidgetSpec } from '$lib/stores/execution';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type OutputRecord =
	| { mime: 'text/plain' | 'text/html' | 'image/png' | 'image/svg+xml' | 'application/json'; data: string }
	| { type: 'widget'; spec: WidgetSpec }
	| { type: 'error'; ename: string; evalue: string; traceback: string[] };

/**
 * Display-only code block. The Markdown primitive: a fenced block with no
 * `.run` class. Renders as syntax-highlighted source. No execution, no
 * output, no id.
 */
export type CodeBlock = {
	kind: 'code-block';
	lang: string;
	source: string;
};

/**
 * Runtime code cell. The interactive primitive: a fenced block carrying the
 * `.run` class. The cell's source is "infrastructure" (default collapsed in
 * the renderer) — what matters is the outputs and widgets it produces.
 */
export type CodeCell = {
	kind: 'code-cell';
	lang: string;
	source: string;
	id: string | null;
	auto: boolean;
	output: OutputRecord[] | null;
};

export type Block =
	| { kind: 'paragraph'; raw: string }
	| { kind: 'heading'; level: 1 | 2 | 3 | 4 | 5 | 6; text: string }
	| { kind: 'list'; raw: string }
	| { kind: 'quote'; raw: string }
	| { kind: 'table'; raw: string }
	| { kind: 'math'; tex: string }
	| { kind: 'divider' }
	| CodeBlock
	| CodeCell
	| { kind: 'widget'; spec: WidgetSpec }
	| { kind: 'raw'; raw: string };

export interface Frontmatter {
	title?: string;
	description?: string;
	tags?: string[];
	interactive?: boolean;
	slug?: string;
	[k: string]: unknown;
}

export interface ParsedDocument {
	frontmatter: Frontmatter;
	blocks: Block[];
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function parse(source: string): ParsedDocument {
	const text = source.replace(/\r\n?/g, '\n');
	const { frontmatter, body } = stripFrontmatter(text);
	const blocks = parseBlocks(body);
	return { frontmatter, blocks: attachOutputs(blocks) };
}

export function serialize(doc: ParsedDocument): string {
	const fm = serializeFrontmatter(doc.frontmatter);
	const body = doc.blocks.map(serializeBlock).filter((s) => s.length > 0).join('\n\n');
	const trimmed = body.replace(/\n+$/, '');
	const result = (fm ? fm + '\n\n' : '') + trimmed;
	return result.length > 0 ? result + '\n' : '';
}

/**
 * Walk the block list and assign `cell-N` ids to code cells that don't have
 * an explicit `#id`. Returns a new array (does not mutate the input).
 * Numbering is by position among code cells.
 */
export function ensureCellIds(blocks: Block[]): Block[] {
	const used = new Set<string>();
	for (const b of blocks) {
		if (b.kind === 'code-cell' && b.id) used.add(b.id);
	}
	let counter = 1;
	const next = () => {
		while (used.has(`cell-${counter}`)) counter++;
		const id = `cell-${counter}`;
		used.add(id);
		counter++;
		return id;
	};
	return blocks.map((b) => {
		if (b.kind === 'code-cell' && !b.id) {
			return { ...b, id: next() };
		}
		return b;
	});
}

/** A page is interactive when it contains at least one code cell. */
export function isInteractive(blocks: Block[]): boolean {
	return blocks.some((b) => b.kind === 'code-cell');
}

/** Look up a code cell by id. */
export function findCodeCellById(blocks: Block[], id: string): CodeCell | null {
	for (const b of blocks) {
		if (b.kind === 'code-cell' && b.id === id) return b;
	}
	return null;
}

/** Return the title to display for a parsed document. */
export function deriveTitle(doc: ParsedDocument, fallback = 'Untitled'): string {
	if (doc.frontmatter.title) return doc.frontmatter.title;
	for (const b of doc.blocks) {
		if (b.kind === 'heading' && b.level === 1) return b.text;
	}
	return fallback;
}

/** Return the description (first non-heading paragraph) for a parsed document. */
export function deriveDescription(doc: ParsedDocument): string | null {
	if (doc.frontmatter.description) return doc.frontmatter.description;
	for (const b of doc.blocks) {
		if (b.kind === 'paragraph') {
			const trimmed = b.raw.trim();
			if (trimmed.length > 0) return trimmed.slice(0, 300);
		}
	}
	return null;
}

// ---------------------------------------------------------------------------
// Frontmatter
// ---------------------------------------------------------------------------

function stripFrontmatter(text: string): { frontmatter: Frontmatter; body: string } {
	if (!text.startsWith('---\n') && text !== '---') {
		return { frontmatter: {}, body: text };
	}
	const end = text.indexOf('\n---', 4);
	if (end < 0) return { frontmatter: {}, body: text };
	const yaml = text.slice(4, end);
	const after = text.slice(end + 4);
	const body = after.startsWith('\n') ? after.slice(1) : after;
	return { frontmatter: parseFrontmatter(yaml), body };
}

function parseFrontmatter(yaml: string): Frontmatter {
	const fm: Frontmatter = {};
	for (const line of yaml.split('\n')) {
		if (!line.trim() || line.startsWith('#')) continue;
		const m = line.match(/^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$/);
		if (!m) continue;
		const key = m[1];
		const rawValue = m[2].trim();
		fm[key] = parseScalar(rawValue);
	}
	return fm;
}

function parseScalar(raw: string): unknown {
	if (raw === '' || raw === '~' || raw === 'null') return null;
	if (raw === 'true') return true;
	if (raw === 'false') return false;
	if (/^-?\d+$/.test(raw)) return Number.parseInt(raw, 10);
	if (/^-?\d+\.\d+$/.test(raw)) return Number.parseFloat(raw);
	if (raw.startsWith('[') && raw.endsWith(']')) {
		const inner = raw.slice(1, -1).trim();
		if (!inner) return [];
		return splitYamlList(inner).map((s) => parseScalar(s));
	}
	if ((raw.startsWith('"') && raw.endsWith('"')) || (raw.startsWith("'") && raw.endsWith("'"))) {
		return raw.slice(1, -1);
	}
	return raw;
}

function splitYamlList(inner: string): string[] {
	const parts: string[] = [];
	let depth = 0;
	let buf = '';
	let inStr: string | null = null;
	for (const ch of inner) {
		if (inStr) {
			buf += ch;
			if (ch === inStr) inStr = null;
			continue;
		}
		if (ch === '"' || ch === "'") {
			inStr = ch;
			buf += ch;
			continue;
		}
		if (ch === '[') depth++;
		if (ch === ']') depth--;
		if (ch === ',' && depth === 0) {
			parts.push(buf.trim());
			buf = '';
		} else {
			buf += ch;
		}
	}
	if (buf.trim()) parts.push(buf.trim());
	return parts;
}

function serializeFrontmatter(fm: Frontmatter): string {
	const keys = Object.keys(fm);
	if (keys.length === 0) return '';
	const ordered = ['title', 'description', 'tags', 'interactive', 'slug'];
	const seen = new Set<string>();
	const lines = ['---'];
	for (const k of ordered) {
		if (k in fm) {
			lines.push(`${k}: ${stringifyScalar(fm[k])}`);
			seen.add(k);
		}
	}
	for (const k of keys) {
		if (seen.has(k)) continue;
		lines.push(`${k}: ${stringifyScalar(fm[k])}`);
	}
	lines.push('---');
	return lines.join('\n');
}

function stringifyScalar(value: unknown): string {
	if (value === null || value === undefined) return '';
	if (typeof value === 'boolean') return value ? 'true' : 'false';
	if (typeof value === 'number') return String(value);
	if (Array.isArray(value)) return '[' + value.map(stringifyScalar).join(', ') + ']';
	const s = String(value);
	if (s === '' || /[:#\[\]{},&*!|>'"%@`]/.test(s) || /^\s|\s$/.test(s)) {
		return JSON.stringify(s);
	}
	return s;
}

// ---------------------------------------------------------------------------
// Block parser
// ---------------------------------------------------------------------------

const FENCE_RE = /^(```+|~~~+)(.*)$/;

function parseBlocks(body: string): Block[] {
	const lines = body.split('\n');
	const blocks: Block[] = [];
	let i = 0;

	while (i < lines.length) {
		// Skip leading blank lines.
		while (i < lines.length && lines[i].trim() === '') i++;
		if (i >= lines.length) break;

		const line = lines[i];

		// Fenced code block
		const fence = line.match(FENCE_RE);
		if (fence) {
			const marker = fence[1];
			const info = fence[2];
			const start = i + 1;
			let end = start;
			while (end < lines.length && !lines[end].startsWith(marker)) end++;
			const source = lines.slice(start, end).join('\n');
			i = end < lines.length ? end + 1 : end;
			blocks.push(buildFencedBlock(info.trim(), source));
			continue;
		}

		// Display math `$$ ... $$` block
		if (line.trim() === '$$') {
			const start = i + 1;
			let end = start;
			while (end < lines.length && lines[end].trim() !== '$$') end++;
			const tex = lines.slice(start, end).join('\n');
			i = end < lines.length ? end + 1 : end;
			blocks.push({ kind: 'math', tex });
			continue;
		}

		// Thematic break
		if (/^(\*\s*\*\s*\*[\s*]*|-\s*-\s*-[\s-]*|_\s*_\s*_[\s_]*)$/.test(line.trim())) {
			blocks.push({ kind: 'divider' });
			i++;
			continue;
		}

		// Heading (ATX)
		const heading = line.match(/^(#{1,6})\s+(.+?)\s*#*\s*$/);
		if (heading) {
			blocks.push({
				kind: 'heading',
				level: heading[1].length as 1 | 2 | 3 | 4 | 5 | 6,
				text: heading[2]
			});
			i++;
			continue;
		}

		// Otherwise, gather lines until a blank line or block-starting line.
		const startProse = i;
		while (i < lines.length) {
			const l = lines[i];
			if (l.trim() === '') break;
			if (l.match(FENCE_RE)) break;
			if (l.trim() === '$$') break;
			i++;
		}
		const raw = lines.slice(startProse, i).join('\n');
		blocks.push(classifyProse(raw));
	}

	return blocks;
}

function classifyProse(raw: string): Block {
	const first = raw.split('\n', 1)[0].trimStart();
	if (first.startsWith('>')) return { kind: 'quote', raw };
	if (first.startsWith('|')) return { kind: 'table', raw };
	if (/^[-*+]\s/.test(first) || /^\d+[.)]\s/.test(first)) return { kind: 'list', raw };
	return { kind: 'paragraph', raw };
}

function buildFencedBlock(info: string, source: string): Block {
	const { lang, classes, id, attrs } = parseInfoString(info);

	if (lang === 'cx-output') {
		// Held as a tagged paragraph so attachOutputs can pick it up; rendered
		// as a plain code block if no owning cell exists.
		return {
			kind: 'raw',
			raw: encodeOutputBlock(attrs.for ?? null, source)
		};
	}

	if (lang === 'cx-widget') {
		try {
			const spec = JSON.parse(source.trim()) as WidgetSpec;
			return { kind: 'widget', spec };
		} catch {
			return { kind: 'raw', raw: '```cx-widget\n' + source + '\n```' };
		}
	}

	if (classes.includes('run')) {
		return {
			kind: 'code-cell',
			lang: lang || 'python',
			source,
			id: id ?? null,
			auto: attrs.auto !== 'false',
			output: null
		};
	}

	return {
		kind: 'code-block',
		lang,
		source
	};
}

interface InfoString {
	lang: string;
	classes: string[];
	id: string | null;
	attrs: Record<string, string>;
}

function parseInfoString(info: string): InfoString {
	const result: InfoString = { lang: '', classes: [], id: null, attrs: {} };
	if (!info) return result;

	const braceMatch = info.match(/^([^\s{]*)\s*\{([^}]*)\}\s*$/);
	if (braceMatch) {
		result.lang = braceMatch[1];
		const inner = braceMatch[2].trim();
		const tokens = tokenizeAttrs(inner);
		for (const tok of tokens) {
			if (tok.startsWith('.')) result.classes.push(tok.slice(1));
			else if (tok.startsWith('#')) result.id = tok.slice(1);
			else {
				const eq = tok.indexOf('=');
				if (eq >= 0) {
					const k = tok.slice(0, eq);
					let v = tok.slice(eq + 1);
					if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
						v = v.slice(1, -1);
					}
					result.attrs[k] = v;
				}
			}
		}
		return result;
	}

	// No brace section — info is just `lang [meta...]`. We only care about lang.
	const parts = info.split(/\s+/);
	result.lang = parts[0] ?? '';
	return result;
}

function tokenizeAttrs(inner: string): string[] {
	const tokens: string[] = [];
	let buf = '';
	let inStr: string | null = null;
	for (const ch of inner) {
		if (inStr) {
			buf += ch;
			if (ch === inStr) inStr = null;
			continue;
		}
		if (ch === '"' || ch === "'") {
			inStr = ch;
			buf += ch;
			continue;
		}
		if (/\s/.test(ch)) {
			if (buf) tokens.push(buf);
			buf = '';
		} else {
			buf += ch;
		}
	}
	if (buf) tokens.push(buf);
	return tokens;
}

// ---------------------------------------------------------------------------
// Output attach / detach
// ---------------------------------------------------------------------------

const OUTPUT_TAG = '\u0000__cx_output__\u0000';

function encodeOutputBlock(forId: string | null, body: string): string {
	return OUTPUT_TAG + (forId ?? '') + '\n' + body;
}

function decodeOutputBlock(raw: string): { forId: string | null; body: string } | null {
	if (!raw.startsWith(OUTPUT_TAG)) return null;
	const nl = raw.indexOf('\n');
	const forId = raw.slice(OUTPUT_TAG.length, nl) || null;
	const body = raw.slice(nl + 1);
	return { forId, body };
}

function attachOutputs(blocks: Block[]): Block[] {
	const result: Block[] = [];
	for (const block of blocks) {
		if (block.kind === 'raw') {
			const decoded = decodeOutputBlock(block.raw);
			if (decoded) {
				const records = parseOutputRecords(decoded.body);
				const targetId = decoded.forId;
				const target = targetId
					? findLastCodeCell(result, (c) => c.id === targetId)
					: findLastCodeCell(result, () => true);
				if (target) {
					target.output = records;
					continue;
				}
				// No matching cell — keep as a plain code block so the file remains
				// readable on a non-Cryptopia renderer.
				const labelled = targetId ? `cx-output {for=${targetId}}` : 'cx-output';
				result.push({ kind: 'raw', raw: '```' + labelled + '\n' + decoded.body + '\n```' });
				continue;
			}
		}
		result.push(block);
	}
	return result;
}

function findLastCodeCell(blocks: Block[], pred: (c: CodeCell) => boolean): CodeCell | null {
	for (let i = blocks.length - 1; i >= 0; i--) {
		const b = blocks[i];
		if (b.kind === 'code-cell' && pred(b)) return b;
	}
	return null;
}

function parseOutputRecords(body: string): OutputRecord[] {
	const records: OutputRecord[] = [];
	for (const line of body.split('\n')) {
		const trimmed = line.trim();
		if (!trimmed) continue;
		try {
			records.push(JSON.parse(trimmed));
		} catch {
			records.push({ mime: 'text/plain', data: line });
		}
	}
	return records;
}

// ---------------------------------------------------------------------------
// Block serializer
// ---------------------------------------------------------------------------

function serializeBlock(block: Block): string {
	switch (block.kind) {
		case 'paragraph':
		case 'list':
		case 'quote':
		case 'table':
			return block.raw.replace(/\n+$/, '');
		case 'heading':
			return `${'#'.repeat(block.level)} ${block.text}`;
		case 'math':
			return `$$\n${block.tex}\n$$`;
		case 'divider':
			return '---';
		case 'code-block':
			return serializeCodeBlock(block);
		case 'code-cell':
			return serializeCodeCell(block);
		case 'widget':
			return '```cx-widget\n' + JSON.stringify(block.spec) + '\n```';
		case 'raw':
			return block.raw.replace(/\n+$/, '');
	}
}

function serializeCodeBlock(b: CodeBlock): string {
	return '```' + (b.lang || '') + '\n' + b.source.replace(/\n+$/, '') + '\n```';
}

function serializeCodeCell(b: CodeCell): string {
	const attrs: string[] = ['.run'];
	if (b.id) attrs.push(`#${b.id}`);
	if (!b.auto) attrs.push('auto=false');
	const meta = ` {${attrs.join(' ')}}`;
	const head = '```' + (b.lang || 'python') + meta;
	const cell = head + '\n' + b.source.replace(/\n+$/, '') + '\n```';
	if (!b.output || b.output.length === 0) return cell;
	const outAttr = b.id ? ` {for=${b.id}}` : '';
	const outBody = b.output.map((r) => JSON.stringify(r)).join('\n');
	return cell + '\n\n' + '```cx-output' + outAttr + '\n' + outBody + '\n```';
}
