/**
 * Execution store — HTTP client for the Cryptopia kernel-backed runtime.
 *
 * Two operations:
 *   - `runCell(pageId, apiBase, cellId)`   POST /run-cell
 *   - `dispatch(pageId, apiBase, wid, v)`  POST /dispatch
 *
 * No long-lived connection. Each call returns a complete output list which is
 * folded into per-cell state. The store also exposes `seed(blocks)` so the
 * viewer can pre-populate widget values from cached `cx-output` blocks (so
 * sliders show their stored positions before the user clicks Run).
 *
 * The `apiBase` argument is accepted for backward compat but ignored — all
 * requests go through the SvelteKit proxy at `/api/...` so cookie-based auth
 * works without per-domain CORS headache.
 */
import { writable, get } from 'svelte/store';
import type { Block, OutputRecord } from '$lib/md/extended';

export type WidgetSpec =
	| {
			type: 'slider';
			id: string;
			label: string;
			value: number;
			min: number;
			max: number;
			step: number;
			has_callback?: boolean;
	  }
	| {
			type: 'select';
			id: string;
			label: string;
			value: string;
			options: string[];
			has_callback?: boolean;
	  }
	| {
			type: 'text_input';
			id: string;
			label: string;
			value: string;
			placeholder: string;
			has_callback?: boolean;
	  }
	| { type: 'button'; id: string; label: string; has_callback?: boolean }
	| { type: 'checkbox'; id: string; label: string; value: boolean; has_callback?: boolean }
	| { type: 'chart'; id: string; option: object; height?: number }
	| { type: 'dataframe'; id: string; columns: string[]; data: unknown[][]; title?: string }
	| { type: 'text'; id: string; content: string; format: 'plain' | 'markdown' | 'latex' };

/** Widget kinds whose role is to *collect* user input. These get routed to the
 * sidebar in the viewer so users can fiddle with them while the main content
 * (charts, dataframes, prose) stays in view. */
export const INPUT_WIDGET_TYPES = [
	'slider',
	'select',
	'text_input',
	'button',
	'checkbox'
] as const;

export function isInputWidget(spec: WidgetSpec): boolean {
	return (INPUT_WIDGET_TYPES as readonly string[]).includes(spec.type);
}

// Same shape as `OutputRecord` in $lib/md/extended. We re-declare it here to
// avoid the circular type-import (extended.ts imports `WidgetSpec` from here).
export type LiveOutputRecord =
	| {
			mime: 'text/plain' | 'text/html' | 'image/png' | 'image/svg+xml' | 'application/json';
			data: string;
	  }
	| { type: 'widget'; spec: WidgetSpec }
	| { type: 'error'; ename: string; evalue: string; traceback: string[] };

export type CellState = {
	status: 'idle' | 'running' | 'done' | 'error';
	outputs: LiveOutputRecord[];
	error: string | null;
};

export type ExecutionState = {
	/** Per code-cell state: status + outputs from the most recent run. */
	cells: Record<string, CellState>;
	/** Current values of every widget, keyed by widget id. Used as the
	 * `widget_values` payload on the next runCell — tracked client-side so
	 * the user's slider position survives a page refresh until the kernel
	 * itself is re-spawned. */
	widgetValues: Record<string, unknown>;
	/** Most recent page-level error (network failure, 4xx, etc.). */
	error: string | null;
	/** Track which widget ids declared `on_change`. Sliders without a
	 * callback fall back to "re-run the cell that owns me" on change. */
	hasCallback: Record<string, boolean>;
	/** Inverse map: which cell emitted which widget. Lets dispatch fall back
	 * to running the owner cell when no callback is registered. */
	widgetOwner: Record<string, string>;
};

const INITIAL: ExecutionState = {
	cells: {},
	widgetValues: {},
	error: null,
	hasCallback: {},
	widgetOwner: {}
};

function emptyCell(): CellState {
	return { status: 'idle', outputs: [], error: null };
}

function ensureCell(state: ExecutionState, cellId: string): ExecutionState {
	if (state.cells[cellId]) return state;
	return { ...state, cells: { ...state.cells, [cellId]: emptyCell() } };
}

function setCell(
	state: ExecutionState,
	cellId: string,
	patch: Partial<CellState>
): ExecutionState {
	const current = state.cells[cellId] ?? emptyCell();
	return {
		...state,
		cells: { ...state.cells, [cellId]: { ...current, ...patch } }
	};
}

/**
 * Walk an output record list and reconcile derived state — widget values,
 * which cell owns which widget, and which widgets declared on_change. Used
 * both for live runs and for the initial seed from cached `cx-output`.
 */
function ingestOutputs(
	state: ExecutionState,
	cellId: string,
	records: LiveOutputRecord[] | OutputRecord[]
): ExecutionState {
	const widgetValues = { ...state.widgetValues };
	const hasCallback = { ...state.hasCallback };
	const widgetOwner = { ...state.widgetOwner };
	for (const r of records) {
		if ('type' in r && r.type === 'widget') {
			const spec = r.spec as WidgetSpec;
			widgetOwner[spec.id] = cellId;
			if (typeof (spec as { has_callback?: boolean }).has_callback === 'boolean') {
				hasCallback[spec.id] = !!(spec as { has_callback?: boolean }).has_callback;
			}
			// Snapshot any value embedded in the spec so future runs send
			// the latest user-entered value.
			if ('value' in spec) {
				widgetValues[spec.id] = (spec as { value: unknown }).value;
			}
		}
	}
	return { ...state, widgetValues, hasCallback, widgetOwner };
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
	const res = await fetch(url, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});
	if (!res.ok) {
		const detail = await res
			.json()
			.then((j: { detail?: string }) => j.detail)
			.catch(() => null);
		throw new Error(detail ?? `HTTP ${res.status}`);
	}
	return res.json() as Promise<T>;
}

function createExecutionStore() {
	const { subscribe, set, update } = writable<ExecutionState>({ ...INITIAL });

	/** Pre-populate widget values from cached cx-output blocks on a parsed
	 * document. Does NOT run anything — this just makes sure the sidebar
	 * sliders display their stored positions before the user clicks Run. */
	function seed(blocks: Block[]) {
		update((state) => {
			let s: ExecutionState = state;
			for (const b of blocks) {
				if (b.kind !== 'code-cell' || !b.id) continue;
				if (!b.output || b.output.length === 0) continue;
				s = ensureCell(s, b.id);
				s = ingestOutputs(s, b.id, b.output);
			}
			return s;
		});
	}

	function reset() {
		set({ ...INITIAL });
	}

	async function runCell(
		pageId: number,
		_apiBase: string,
		cellId: string
	): Promise<void> {
		update((s) =>
			setCell(ensureCell(s, cellId), cellId, {
				status: 'running',
				error: null
			})
		);
		try {
			const widgetValues = get({ subscribe }).widgetValues;
			const result = await postJson<{
				outputs: LiveOutputRecord[];
				error: string | null;
			}>(`/api/pages/id/${pageId}/run-cell`, {
				cell_id: cellId,
				widget_values: widgetValues
			});
			update((s) => {
				let next = setCell(s, cellId, {
					status: result.error ? 'error' : 'done',
					outputs: result.outputs ?? [],
					error: result.error ?? null
				});
				next = ingestOutputs(next, cellId, result.outputs ?? []);
				return next;
			});
		} catch (e) {
			const message = e instanceof Error ? e.message : String(e);
			update((s) =>
				setCell({ ...s, error: message }, cellId, {
					status: 'error',
					error: message
				})
			);
		}
	}

	/** Run every auto code cell in document order — the "first run" path
	 * triggered by the viewer's Run button. */
	async function runAll(
		pageId: number,
		apiBase: string,
		blocks: Block[]
	): Promise<void> {
		for (const b of blocks) {
			if (b.kind !== 'code-cell' || !b.id || !b.auto) continue;
			await runCell(pageId, apiBase, b.id);
			const state = get({ subscribe });
			if (state.cells[b.id]?.status === 'error') break;
		}
	}

	/**
	 * Fire a widget change. If the widget declared `on_change` in the SDK
	 * we hit `/dispatch`, which runs only the callback. Otherwise we fall
	 * back to re-running the owning cell so the page still updates.
	 *
	 * Either way the new value is recorded in `widgetValues` first so even
	 * the fallback path passes the freshest value to the next run.
	 */
	async function dispatch(
		pageId: number,
		apiBase: string,
		widgetId: string,
		value: unknown
	): Promise<void> {
		update((s) => ({
			...s,
			widgetValues: { ...s.widgetValues, [widgetId]: value }
		}));

		const state = get({ subscribe });
		const owner = state.widgetOwner[widgetId];
		const callbackKnown = state.hasCallback[widgetId];

		if (callbackKnown) {
			try {
				const result = await postJson<{
					outputs: LiveOutputRecord[];
					error: string | null;
				}>(`/api/pages/id/${pageId}/dispatch`, {
					widget_id: widgetId,
					value
				});
				update((s) => {
					if (!owner) return result.error ? { ...s, error: result.error } : s;
					// Merge the dispatch outputs into the owning cell's slot — the
					// callback usually re-emits a chart/widget that should replace
					// the previous render keyed by widget id.
					let next = mergeIntoCell(s, owner, result.outputs ?? []);
					next = ingestOutputs(next, owner, result.outputs ?? []);
					if (result.error) next = { ...next, error: result.error };
					return next;
				});
			} catch (e) {
				const message = e instanceof Error ? e.message : String(e);
				update((s) => ({ ...s, error: message }));
			}
			return;
		}

		// No callback declared (or no first run yet) — re-run the owning cell.
		if (owner) {
			await runCell(pageId, apiBase, owner);
		}
	}

	function mergeIntoCell(
		state: ExecutionState,
		cellId: string,
		incoming: LiveOutputRecord[]
	): ExecutionState {
		const cell = state.cells[cellId] ?? emptyCell();
		const incomingWidgetIds = new Set<string>();
		for (const r of incoming) {
			if ('type' in r && r.type === 'widget') incomingWidgetIds.add(r.spec.id);
		}
		// Replace any existing widget output by id; keep non-widget outputs as
		// they were. New widgets are appended at the end.
		const replaced: LiveOutputRecord[] = [];
		const taken = new Set<string>();
		for (const r of cell.outputs) {
			if ('type' in r && r.type === 'widget' && incomingWidgetIds.has(r.spec.id)) {
				const repl = incoming.find(
					(x) => 'type' in x && x.type === 'widget' && x.spec.id === r.spec.id
				);
				if (repl) {
					replaced.push(repl);
					taken.add(r.spec.id);
				}
				continue;
			}
			replaced.push(r);
		}
		for (const r of incoming) {
			if ('type' in r && r.type === 'widget') {
				if (taken.has(r.spec.id)) continue;
				replaced.push(r);
			} else {
				replaced.push(r);
			}
		}
		return {
			...state,
			cells: {
				...state.cells,
				[cellId]: { ...cell, outputs: replaced, status: 'done', error: null }
			}
		};
	}

	return { subscribe, runCell, runAll, dispatch, seed, reset };
}

export const executionStore = createExecutionStore();
