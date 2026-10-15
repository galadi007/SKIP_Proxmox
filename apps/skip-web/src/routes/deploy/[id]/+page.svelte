<script lang="ts">
	import type { PageData, ActionData } from './$types';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import * as Card from '$lib/components/ui/card/index.js';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	let releaseName = $state('');
	let namespace = $state('');

	$effect(() => {
		if (!releaseName && data.template?.name) {
			releaseName = `my-${data.template.name}`;
		}
		if (!namespace && data.allowedNamespaces?.length) {
			namespace = data.allowedNamespaces[0];
		}
	});

	type ParameterValue = { name: string; displayName?: string | null; description?: string | null };
	type Parameter = {
		name: string;
		displayName?: string | null;
		description?: string | null;
		type: 'string' | 'integer' | 'number' | 'boolean' | 'enum';
		default?: unknown;
		required?: boolean;
		values?: ParameterValue[];
		pattern?: string | null;
		minimum?: number | null;
		maximum?: number | null;
		advanced?: boolean;
	};
	type Capability = { name: string; type: string; class: string; optional: boolean };

	const parameters = $derived<Parameter[]>(data.template.parameters ?? []);
	const basic = $derived(parameters.filter((p) => !p.advanced));
	const advanced = $derived(parameters.filter((p) => p.advanced));
	const capabilities = $derived<Capability[]>(data.template.capabilities ?? []);

	const selectClass =
		'border-input bg-background ring-offset-background placeholder:text-muted-foreground focus:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-offset-2';
</script>

{#snippet parameterField(p: Parameter)}
	<div class="grid gap-2">
		<Label for={p.name}>
			{p.displayName ?? p.name}
			{#if !p.required}
				<span class="text-muted-foreground text-xs">(optional)</span>
			{/if}
		</Label>

		{#if p.type === 'enum'}
			<select id={p.name} name={p.name} class={selectClass}>
				{#each p.values ?? [] as option (option.name)}
					<option value={option.name} selected={option.name === p.default}>
						{option.displayName ?? option.name}
					</option>
				{/each}
			</select>
		{:else if p.type === 'boolean'}
			<select id={p.name} name={p.name} class={selectClass}>
				<option value="true" selected={p.default === true}>Ja</option>
				<option value="false" selected={p.default !== true}>Nein</option>
			</select>
		{:else if p.type === 'integer' || p.type === 'number'}
			<Input
				id={p.name}
				name={p.name}
				type="number"
				step={p.type === 'integer' ? 1 : 'any'}
				min={p.minimum ?? undefined}
				max={p.maximum ?? undefined}
				value={(p.default as number | undefined) ?? ''}
				required={p.required}
			/>
		{:else}
			<Input
				id={p.name}
				name={p.name}
				type="text"
				pattern={p.pattern ?? undefined}
				value={(p.default as string | undefined) ?? ''}
				required={p.required}
			/>
		{/if}

		{#if p.description}
			<p class="text-muted-foreground text-xs">{p.description}</p>
		{/if}
	</div>
{/snippet}

<div class="container mx-auto px-4 py-8">
	<div class="mb-8">
		<a href="/templates" class="text-muted-foreground hover:text-foreground mb-4 inline-block text-sm">
			← Zurück zu den Templates
		</a>
		<h1 class="text-2xl font-semibold tracking-tight">{data.template.displayName}</h1>
		<p class="text-muted-foreground mt-1 text-sm">
			{data.template.summary}
		</p>
	</div>

	{#if form?.error}
		<div class="bg-destructive/10 text-destructive mb-6 rounded-md px-4 py-3 text-sm">
			{form.error}
		</div>
	{/if}

	<form method="POST" action="?/deploy">
		<Card.Root>
			<Card.Header>
				<Card.Title>Deployment</Card.Title>
			</Card.Header>
			<Card.Content class="flex flex-col gap-4">
				<div class="grid gap-2">
					<Label for="release_name">Name</Label>
					<Input
						id="release_name"
						name="release_name"
						bind:value={releaseName}
						pattern="[a-z0-9\-]+"
						required
					/>
					<p class="text-muted-foreground text-xs">Nur Kleinbuchstaben, Ziffern und Bindestriche</p>
				</div>
				<div class="grid gap-2">
					<Label for="namespace">Namespace</Label>
					<select id="namespace" name="namespace" bind:value={namespace} class={selectClass} required>
						{#each data.allowedNamespaces as ns (ns)}
							<option value={ns}>{ns}</option>
						{/each}
					</select>
					<p class="text-muted-foreground text-xs">Persönlicher Namespace oder Gruppen aus Authentik</p>
				</div>
			</Card.Content>
		</Card.Root>

		{#if parameters.length > 0}
			<Card.Root class="mt-4">
				<Card.Header>
					<Card.Title>Konfiguration</Card.Title>
				</Card.Header>
				<Card.Content class="flex flex-col gap-4">
					{#each basic as p (p.name)}
						{@render parameterField(p)}
					{/each}
					{#if advanced.length > 0}
						<details class="mt-2">
							<summary class="text-muted-foreground cursor-pointer text-sm">Erweiterte Einstellungen</summary>
							<div class="mt-4 flex flex-col gap-4">
								{#each advanced as p (p.name)}
									{@render parameterField(p)}
								{/each}
							</div>
						</details>
					{/if}
				</Card.Content>
			</Card.Root>
		{/if}

		{#if capabilities.length > 0}
			<Card.Root class="mt-4">
				<Card.Header>
					<Card.Title>Plattform-Dienste</Card.Title>
					<Card.Description>Diese Capabilities fordert die App beim Deploy an.</Card.Description>
				</Card.Header>
				<Card.Content class="flex flex-col gap-2 text-sm">
					{#each capabilities as cap (cap.name)}
						<div class="flex items-center justify-between">
							<span><code>{cap.name}</code> <span class="text-muted-foreground">({cap.type}, {cap.class})</span></span>
							<span class="text-muted-foreground text-xs">{cap.optional ? 'optional' : 'erforderlich'}</span>
						</div>
					{/each}
				</Card.Content>
			</Card.Root>
		{/if}

		<div class="mt-4 flex justify-between">
			<Button variant="outline" href="/templates">Abbrechen</Button>
			<Button type="submit">Deploy →</Button>
		</div>
	</form>
</div>
