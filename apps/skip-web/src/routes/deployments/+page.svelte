<script lang="ts">
	import type { PageData, ActionData } from './$types';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import { enhance } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import UsersIcon from '@lucide/svelte/icons/users';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import UserPlusIcon from '@lucide/svelte/icons/user-plus';
	import XIcon from '@lucide/svelte/icons/x';
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	const statusVariant: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
		Running: 'default',
		Deploying: 'secondary',
		Failed: 'destructive'
	};

	let selectedSharingApp = $state<{ template: string; namespace: string; name: string } | null>(null);
	let newMemberUsername = $state('');
</script>

<div class="container mx-auto px-4 py-8">
	<div class="mb-8 flex items-center justify-between">
		<div>
			<h1 class="text-2xl font-semibold tracking-tight">Deployments</h1>
			<p class="text-muted-foreground mt-1 text-sm">
				Deine laufenden und mit dir geteilten Anwendungen
			</p>
		</div>
		<Button href="/templates">+ Neues Deployment</Button>
	</div>


	{#if form?.error}
		<div class="bg-destructive/10 text-destructive mb-6 rounded-md px-4 py-3 text-sm">
			{form.error}
		</div>
	{/if}

	{#if data.deployments.length === 0}
		<Card.Root>
			<Card.Content class="flex flex-col items-center justify-center py-16 text-center">
				<p class="text-muted-foreground text-sm">Noch keine Deployments vorhanden.</p>
				<Button href="/templates" class="mt-4" variant="outline">Template bereitstellen</Button>
			</Card.Content>
		</Card.Root>
	{:else}
		<Card.Root>
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>Template</Table.Head>
						<Table.Head>Name</Table.Head>
						<Table.Head>Namespace</Table.Head>
						<Table.Head>Rolle</Table.Head>
						<Table.Head>Status</Table.Head>
						<Table.Head>Meldung</Table.Head>
						<Table.Head class="text-end">Aktionen</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each data.deployments as dep (`${dep.template}/${dep.namespace}/${dep.name}`)}
						<Table.Row>
							<Table.Cell class="font-medium">{dep.template}</Table.Cell>
							<Table.Cell class="font-mono text-sm">
								{dep.name}
								{#if dep.components?.length > 1}
									<div class="text-muted-foreground mt-1 flex flex-wrap gap-1 font-sans text-xs">
										{#each dep.components as c (c.instance)}
											<Badge variant={statusVariant[c.phase] ?? 'outline'} class="font-normal">{c.name}</Badge>
										{/each}
									</div>
								{/if}
							</Table.Cell>
							<Table.Cell class="font-mono text-sm">{dep.namespace}</Table.Cell>
							<Table.Cell>
								{#if dep.isOwner}
									<Badge variant="default">Owner</Badge>
								{:else}
									<Badge variant="outline">Mitglied</Badge>
								{/if}
							</Table.Cell>
							<Table.Cell>
								<Badge variant={statusVariant[dep.phase] ?? 'outline'}>
									{dep.phase}
								</Badge>
							</Table.Cell>
							<Table.Cell class="text-muted-foreground text-sm">
								{dep.message ?? '-'}
							</Table.Cell>
							<Table.Cell class="text-end">
								<div class="flex items-center justify-end gap-2">
									{#if dep.url}
										<Button
											variant={dep.phase === 'Running' ? 'default' : 'outline'}
											size="sm"
											href={dep.url}
											target="_blank"
											rel="noopener"
											title={dep.url}
										>
											<ExternalLinkIcon class="mr-1 size-4" />
											Öffnen
										</Button>
									{/if}
									{#if dep.isOwner}
										<Button
											variant="outline"
											size="sm"
											class="gap-1.5 text-xs"
											onclick={() => {
												selectedSharingApp = {
													template: dep.template,
													namespace: dep.namespace,
													name: dep.name
												};
												newMemberUsername = '';
											}}
										>
											<UsersIcon class="size-3.5" />
											Teilen
										</Button>

										<form
											method="POST"
											action="?/delete"
											use:enhance={() => {
												return async ({ update }) => {
													await update();
													await invalidateAll();
												};
											}}
										>
											<input type="hidden" name="template" value={dep.template} />
											<input type="hidden" name="namespace" value={dep.namespace} />
											<input type="hidden" name="name" value={dep.name} />
											<Button
												type="submit"
												variant="ghost"
												size="sm"
												class="text-destructive hover:text-destructive text-xs"
											>
												<Trash2Icon class="size-3.5" />
											</Button>
										</form>
									{/if}
								</div>
							</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</Card.Root>
	{/if}

	{#if selectedSharingApp}
		<div class="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
			<Card.Root class="w-full max-w-md shadow-2xl border-border">
				<Card.Header class="flex flex-row items-center justify-between pb-3">
					<div>
						<Card.Title class="text-lg">App freigeben</Card.Title>
						<Card.Description class="text-xs font-mono">
							{selectedSharingApp.namespace} / {selectedSharingApp.name}
						</Card.Description>
					</div>
					<Button
						variant="ghost"
						size="icon"
						class="size-8"
						onclick={() => (selectedSharingApp = null)}
					>
						<XIcon class="size-4" />
					</Button>
				</Card.Header>

				<Card.Content class="space-y-4">
					<form
						method="POST"
						action="?/addMember"
						class="flex gap-2"
						use:enhance={() => {
							return async ({ update }) => {
								await update();
								newMemberUsername = '';
								await invalidateAll();
							};
						}}
					>
						<input type="hidden" name="template" value={selectedSharingApp.template} />
						<input type="hidden" name="namespace" value={selectedSharingApp.namespace} />
						<input type="hidden" name="name" value={selectedSharingApp.name} />

						{#if data.availableUsers && data.availableUsers.length > 0}
							<select
								name="username"
								bind:value={newMemberUsername}
								class="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus:ring-ring flex h-9 flex-1 rounded-md border px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-offset-2"
								required
							>
								<option value="" disabled selected>Benutzer auswählen...</option>
								{#each data.availableUsers as u (u.username)}
									<option value={u.username}>{u.name || u.username} ({u.email || u.username})</option>
								{/each}
							</select>
						{:else}
							<input
								type="text"
								name="username"
								placeholder="Benutzername (z. B. max.mustermann)"
								bind:value={newMemberUsername}
								class="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus:ring-ring flex h-9 flex-1 rounded-md border px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-offset-2"
								required
							/>
						{/if}

						<Button type="submit" size="sm" class="gap-1">
							<UserPlusIcon class="size-3.5" />
							Hinzufügen
						</Button>
					</form>

					<div class="rounded-md border border-border/50 bg-muted/40 p-3 text-xs text-muted-foreground">
						💡 Alle hinzugefügten Benutzer erhalten Zugriff auf diese App in ihrer Deployments-Übersicht und werden automatisch in der Authentik-Gruppe <code class="text-foreground">app-{selectedSharingApp.namespace}-{selectedSharingApp.name}</code> hinterlegt.
					</div>
				</Card.Content>

				<Card.Footer class="border-t border-border/50 flex justify-end py-3">
					<Button variant="outline" size="sm" onclick={() => (selectedSharingApp = null)}>
						Fertig
					</Button>
				</Card.Footer>
			</Card.Root>
		</div>
	{/if}
</div>
