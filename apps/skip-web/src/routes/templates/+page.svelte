<script lang="ts">
	import type { PageData } from './$types';
	import { Button } from '$lib/components/ui/button/index.js';
	import TemplateCard from './template-card.svelte';

	let { data }: { data: PageData } = $props();

	let selected: string | null = $state(null);
</script>

<div class="container mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-semibold tracking-tight">Templates</h1>
		<p class="text-muted-foreground mt-1 text-sm">
			Wähle eine der Vorlagen aus, um sie zu deployen.
		</p>
	</div>

	<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
		{#each data.templates as template (template.name)}
			<TemplateCard
				{template}
				selected={selected === template.name}
				onSelect={() => (selected = template.name)}
			/>
		{/each}
	</div>

	{#if selected}
		<div class="mt-8 flex justify-end">
			<Button href="/deploy/{selected}">
				Configure {data.templates.find((t: any) => t.name === selected)?.displayName} →
			</Button>
		</div>
	{/if}
</div>
