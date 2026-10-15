<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import * as Card from '$lib/components/ui/card/index.js';

	type Template = {
		icon?: string;
		name: string;
		displayName: string;
		summary: string;
		version: string;
		author: string;
		category: string;
		tags: string[];
		maturity: string;
	};

	let {
		template,
		selected = false,
		onSelect
	}: {
		template: Template;
		selected?: boolean;
		onSelect: () => void;
	} = $props();
</script>

<Card.Root
	class="w-full cursor-pointer transition-all {selected
		? 'ring-primary ring-2'
		: 'hover:border-primary/50'}"
	onclick={onSelect}
>
	<Card.Header>
		<Card.Title>{template.displayName}</Card.Title>
		<Card.Description>{template.summary}</Card.Description>
	</Card.Header>

	<Card.Content>
		<div class="flex flex-wrap gap-2">
			<Badge variant="outline">v{template.version}</Badge>
			{#each template.tags as tag (tag)}
				<Badge variant="secondary">{tag}</Badge>
			{/each}
		</div>
	</Card.Content>

	<Card.Footer>
		<Button
			class="w-full"
			variant={selected ? 'default' : 'outline'}
			onclick={onSelect}
		>
			{selected ? '✓ Selected' : 'Select'}
		</Button>
	</Card.Footer>
</Card.Root>
