<script lang="ts">
	import SliderWidget from './SliderWidget.svelte';
	import SelectWidget from './SelectWidget.svelte';
	import TextInputWidget from './TextInputWidget.svelte';
	import ButtonWidget from './ButtonWidget.svelte';
	import CheckboxWidget from './CheckboxWidget.svelte';
	import ChartWidget from './ChartWidget.svelte';
	import DataFrameWidget from './DataFrameWidget.svelte';
	import Markdown from '$lib/render/Markdown.svelte';
	import type { WidgetSpec } from '$lib/stores/execution';
	import { executionStore } from '$lib/stores/execution';

	let {
		spec,
		researchId,
		apiBase
	}: {
		spec: WidgetSpec;
		researchId: number;
		apiBase: string;
	} = $props();

	function emit(value: unknown) {
		void executionStore.dispatch(researchId, apiBase, spec.id, value);
	}
</script>

{#if spec.type === 'slider'}
	<SliderWidget
		label={spec.label}
		value={spec.value}
		min={spec.min}
		max={spec.max}
		step={spec.step}
		onchange={(v) => emit(v)}
	/>
{:else if spec.type === 'select'}
	<SelectWidget
		label={spec.label}
		value={spec.value}
		options={spec.options}
		onchange={(v) => emit(v)}
	/>
{:else if spec.type === 'text_input'}
	<TextInputWidget
		label={spec.label}
		value={spec.value}
		placeholder={spec.placeholder}
		onsubmit={(v) => emit(v)}
	/>
{:else if spec.type === 'button'}
	<ButtonWidget label={spec.label} onclick={() => emit(true)} />
{:else if spec.type === 'checkbox'}
	<CheckboxWidget
		label={spec.label}
		value={spec.value}
		onchange={(v) => emit(v)}
	/>
{:else if spec.type === 'chart'}
	<ChartWidget option={spec.option as Record<string, unknown>} height={spec.height} />
{:else if spec.type === 'dataframe'}
	<DataFrameWidget columns={spec.columns} data={spec.data} title={spec.title} />
{:else if spec.type === 'text'}
	{#if spec.format === 'markdown' || spec.format === 'latex'}
		<div class="widget-container">
			<Markdown source={spec.content} />
		</div>
	{:else}
		<div class="widget-container">
			<p class="text-slate-300 text-sm">{spec.content}</p>
		</div>
	{/if}
{/if}
