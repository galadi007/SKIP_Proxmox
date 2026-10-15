<script lang="ts">
	import type { PageData, ActionData } from './$types';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import { enhance } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import UsersIcon from '@lucide/svelte/icons/users';
	import UserPlusIcon from '@lucide/svelte/icons/user-plus';
	import UserMinusIcon from '@lucide/svelte/icons/user-minus';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import ShieldCheckIcon from '@lucide/svelte/icons/shield-check';
	import LogOutIcon from '@lucide/svelte/icons/log-out';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import XIcon from '@lucide/svelte/icons/x';
	import UserIcon from '@lucide/svelte/icons/user';
	import type { Team } from './+page.server';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	let isCreateOpen = $state(false);
	let newTeamName = $state('');
	let newTeamDescription = $state('');

	let selectedTeamForInvite = $state<Team | null>(null);
	let selectedInviteUser = $state('');

	// Filtere Benutzer heraus, die bereits im ausgewaehlten Team sind
	let nonMemberUsers = $derived.by(() => {
		if (!selectedTeamForInvite) return [];
		const currentMemberUsernames = new Set(selectedTeamForInvite.members.map((m) => m.username));
		return data.availableUsers.filter((u) => !currentMemberUsernames.has(u.username));
	});

	let ownTeamsCount = $derived(data.teams.filter((t) => t.is_owner).length);
</script>

<div class="container mx-auto px-4 py-8">
	<!-- Page Header -->
	<div class="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
		<div>
			<h1 class="text-2xl font-semibold tracking-tight">Teams & Arbeitsgruppen</h1>
			<p class="text-muted-foreground mt-1 text-sm">
				Gründe eigene Teams, verwalte Mitglieder und teile Dateien oder Deployments direkt mit deinen Kollegen
			</p>
		</div>
		<Button onclick={() => (isCreateOpen = true)} class="gap-2">
			<PlusIcon class="size-4" />
			Neues Team
		</Button>
	</div>

	<!-- Status / Feedback Messages -->
	{#if form?.error}
		<div class="bg-destructive/10 text-destructive mb-6 rounded-md px-4 py-3 text-sm">
			{form.error}
		</div>
	{/if}
	{#if form?.message}
		<div class="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 mb-6 rounded-md px-4 py-3 text-sm">
			{form.message}
		</div>
	{/if}

	<!-- Overview Cards -->
	<div class="mb-8 grid gap-4 sm:grid-cols-3">
		<Card.Root>
			<Card.Header class="flex flex-row items-center justify-between pb-2">
				<Card.Title class="text-sm font-medium">Meine Teams</Card.Title>
				<UsersIcon class="text-muted-foreground size-4" />
			</Card.Header>
			<Card.Content>
				<div class="text-2xl font-bold">{data.teams.length}</div>
				<p class="text-muted-foreground mt-1 text-xs">
					Mitgliedschaften & eigene Gruppen
				</p>
			</Card.Content>
		</Card.Root>

		<Card.Root>
			<Card.Header class="flex flex-row items-center justify-between pb-2">
				<Card.Title class="text-sm font-medium">Gegründete Teams (Owner)</Card.Title>
				<ShieldCheckIcon class="text-muted-foreground size-4" />
			</Card.Header>
			<Card.Content>
				<div class="text-2xl font-bold">{ownTeamsCount}</div>
				<p class="text-muted-foreground mt-1 text-xs">
					Volle Administrationsrechte
				</p>
			</Card.Content>
		</Card.Root>

		<Card.Root>
			<Card.Header class="flex flex-row items-center justify-between pb-2">
				<Card.Title class="text-sm font-medium">Verfügbare Plattform-Nutzer</Card.Title>
				<UserIcon class="text-muted-foreground size-4" />
			</Card.Header>
			<Card.Content>
				<div class="text-2xl font-bold">{data.availableUsers.length}</div>
				<p class="text-muted-foreground mt-1 text-xs">
					In Authentik registriert
				</p>
			</Card.Content>
		</Card.Root>
	</div>

	<!-- Team List -->
	{#if data.teams.length === 0}
		<Card.Root>
			<Card.Content class="flex flex-col items-center justify-center py-16 text-center">
				<UsersIcon class="text-muted-foreground/40 mb-3 size-12" />
				<h3 class="text-base font-semibold">Noch keine Teams vorhanden</h3>
				<p class="text-muted-foreground mt-1 text-sm max-w-sm">
					Du bist noch keinem Team beigetreten und hast noch keine eigene Arbeitsgruppe gegründet.
				</p>
				<Button onclick={() => (isCreateOpen = true)} class="mt-4 gap-2" variant="outline">
					<PlusIcon class="size-4" />
					Erstes Team gründen
				</Button>
			</Card.Content>
		</Card.Root>
	{:else}
		<div class="grid gap-6">
			{#each data.teams as team (team.id)}
				<Card.Root class="overflow-hidden border-border/80">
					<Card.Header class="bg-muted/30 pb-4">
						<div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
							<div class="flex items-center gap-3">
								<div class="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
									<UsersIcon class="size-5" />
								</div>
								<div>
									<div class="flex items-center gap-2">
										<Card.Title class="text-lg font-mono font-semibold">{team.name}</Card.Title>
										{#if team.is_owner}
											<Badge variant="default">Owner</Badge>
										{:else}
											<Badge variant="outline">Mitglied</Badge>
										{/if}
									</div>
									<Card.Description class="text-xs mt-0.5">
										{#if team.description}
											{team.description} &bull;
										{/if}
										Gründer: <span class="font-semibold text-foreground">{team.owner || 'System'}</span>
									</Card.Description>
								</div>
							</div>

							<!-- Header Actions -->
							<div class="flex items-center gap-2">
								{#if team.is_owner}
									<Button
										size="sm"
										variant="outline"
										onclick={() => {
											selectedTeamForInvite = team;
											selectedInviteUser = '';
										}}
										class="gap-1.5 h-8 text-xs"
									>
										<UserPlusIcon class="size-3.5" />
										Kollegen einladen
									</Button>

									<form
										method="POST"
										action="?/deleteTeam"
										use:enhance={() => {
											if (!confirm(`Möchtest du das Team '${team.name}' wirklich auflösen?`)) {
												return () => {};
											}
											return async ({ update }) => {
												await update();
												await invalidateAll();
											};
										}}
									>
										<input type="hidden" name="teamName" value={team.name} />
										<Button
											type="submit"
											variant="ghost"
											size="sm"
											class="text-destructive hover:text-destructive h-8 px-2"
											title="Team auflösen"
										>
											<Trash2Icon class="size-4" />
										</Button>
									</form>
								{:else}
									<form
										method="POST"
										action="?/removeMember"
										use:enhance={() => {
											if (!confirm(`Möchtest du das Team '${team.name}' wirklich verlassen?`)) {
												return () => {};
											}
											return async ({ update }) => {
												await update();
												await invalidateAll();
											};
										}}
									>
										<input type="hidden" name="teamName" value={team.name} />
										<input type="hidden" name="username" value={data.currentUsername} />
										<Button
											type="submit"
											variant="outline"
											size="sm"
											class="gap-1.5 h-8 text-xs text-muted-foreground hover:text-destructive"
										>
											<LogOutIcon class="size-3.5" />
											Verlassen
										</Button>
									</form>
								{/if}
							</div>
						</div>
					</Card.Header>

					<Card.Content class="pt-4">
						<div class="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
							Mitglieder ({team.members.length})
						</div>

						<Table.Root>
							<Table.Header>
								<Table.Row class="hover:bg-transparent">
									<Table.Head class="h-8 text-xs">Benutzer</Table.Head>
									<Table.Head class="h-8 text-xs">E-Mail</Table.Head>
									<Table.Head class="h-8 text-xs">Rolle</Table.Head>
									{#if team.is_owner}
										<Table.Head class="h-8 text-end text-xs">Aktion</Table.Head>
									{/if}
								</Table.Row>
							</Table.Header>
							<Table.Body>
								{#each team.members as member (member.username)}
									<Table.Row class="hover:bg-muted/40">
										<Table.Cell class="py-2.5">
											<div class="flex items-center gap-2">
												<div class="flex size-7 items-center justify-center rounded-full bg-muted font-mono text-xs font-semibold">
													{member.username.charAt(0).toUpperCase()}
												</div>
												<div>
													<div class="font-medium text-sm text-foreground">
														{member.name || member.username}
													</div>
													{#if member.name && member.name !== member.username}
														<div class="font-mono text-xs text-muted-foreground">
															{member.username}
														</div>
													{/if}
												</div>
											</div>
										</Table.Cell>
										<Table.Cell class="py-2.5 text-muted-foreground text-xs font-mono">
											{member.email || '-'}
										</Table.Cell>
										<Table.Cell class="py-2.5">
											{#if member.is_owner}
												<Badge variant="default" class="text-[11px] font-normal">Owner</Badge>
											{:else}
												<Badge variant="outline" class="text-[11px] font-normal">Mitglied</Badge>
											{/if}
										</Table.Cell>
										{#if team.is_owner}
											<Table.Cell class="py-2.5 text-end">
												{#if !member.is_owner}
													<form
														method="POST"
														action="?/removeMember"
														use:enhance={() => {
															return async ({ update }) => {
																await update();
																await invalidateAll();
															};
														}}
													>
														<input type="hidden" name="teamName" value={team.name} />
														<input type="hidden" name="username" value={member.username} />
														<Button
															type="submit"
															variant="ghost"
															size="sm"
															class="h-7 px-2 text-xs text-destructive hover:text-destructive"
															title="Mitglied entfernen"
														>
															<UserMinusIcon class="size-3.5" />
														</Button>
													</form>
												{:else}
													<span class="text-xs text-muted-foreground italic">-</span>
												{/if}
											</Table.Cell>
										{/if}
									</Table.Row>
								{/each}
							</Table.Body>
						</Table.Root>
					</Card.Content>
				</Card.Root>
			{/each}
		</div>
	{/if}

	<!-- Modal: Neues Team erstellen -->
	{#if isCreateOpen}
		<div class="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
			<Card.Root class="w-full max-w-md shadow-2xl border-border">
				<Card.Header class="flex flex-row items-center justify-between pb-3">
					<div>
						<Card.Title class="text-lg">Neues Team gründen</Card.Title>
						<Card.Description class="text-xs">
							Erstelle eine Arbeitsgruppe für gemeinsame Projekte und Freigaben
						</Card.Description>
					</div>
					<Button variant="ghost" size="icon" class="size-8" onclick={() => (isCreateOpen = false)}>
						<XIcon class="size-4" />
					</Button>
				</Card.Header>

				<form
					method="POST"
					action="?/createTeam"
					use:enhance={() => {
						return async ({ update }) => {
							await update();
							isCreateOpen = false;
							newTeamName = '';
							newTeamDescription = '';
							await invalidateAll();
						};
					}}
				>
					<Card.Content class="space-y-4">
						<div>
							<label for="team-name" class="text-sm font-medium mb-1.5 block">Teamname</label>
							<input
								id="team-name"
								type="text"
								name="name"
								placeholder="z. B. ki-arbeitsgruppe oder projekt-alpha"
								bind:value={newTeamName}
								required
								class="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-offset-2 font-mono"
							/>
							{#if newTeamName}
								<p class="text-muted-foreground text-xs mt-1.5 font-mono">
									Kennung: <span class="text-foreground font-semibold">team-{newTeamName.toLowerCase().replace(/^team-/, '').replace(/\s+/g, '-')}</span>
								</p>
							{/if}
						</div>

						<div>
							<label for="team-desc" class="text-sm font-medium mb-1.5 block">Beschreibung (optional)</label>
							<input
								id="team-desc"
								type="text"
								name="description"
								placeholder="Kurze Beschreibung des Projektziels"
								bind:value={newTeamDescription}
								class="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-offset-2"
							/>
						</div>

						<div class="rounded-md border border-border/50 bg-muted/40 p-3 text-xs text-muted-foreground flex gap-2 items-start">
							<ShieldCheckIcon class="size-4 shrink-0 text-primary mt-0.5" />
							<div>
								Du wirst automatisch als <strong>Owner</strong> eingetragen und kannst anschließend beliebig viele Kollegen zu diesem Team einladen. Das Team wird direkt in Authentik hinterlegt.
							</div>
						</div>
					</Card.Content>

					<Card.Footer class="border-t border-border/50 flex justify-end gap-2 py-3">
						<Button variant="outline" size="sm" type="button" onclick={() => (isCreateOpen = false)}>
							Abbrechen
						</Button>
						<Button size="sm" type="submit" class="gap-1.5">
							<PlusIcon class="size-3.5" />
							Team erstellen
						</Button>
					</Card.Footer>
				</form>
			</Card.Root>
		</div>
	{/if}

	<!-- Modal: Kollegen einladen -->
	{#if selectedTeamForInvite}
		<div class="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
			<Card.Root class="w-full max-w-md shadow-2xl border-border">
				<Card.Header class="flex flex-row items-center justify-between pb-3">
					<div>
						<Card.Title class="text-lg">Kollegen einladen</Card.Title>
						<Card.Description class="text-xs font-mono">
							Team: {selectedTeamForInvite.name}
						</Card.Description>
					</div>
					<Button
						variant="ghost"
						size="icon"
						class="size-8"
						onclick={() => (selectedTeamForInvite = null)}
					>
						<XIcon class="size-4" />
					</Button>
				</Card.Header>

				<form
					method="POST"
					action="?/addMember"
					use:enhance={() => {
						return async ({ update }) => {
							await update();
							selectedTeamForInvite = null;
							selectedInviteUser = '';
							await invalidateAll();
						};
					}}
				>
					<Card.Content class="space-y-4">
						<input type="hidden" name="teamName" value={selectedTeamForInvite.name} />

						<div>
							<label for="invite-user" class="text-sm font-medium mb-1.5 block">Plattform-Benutzer auswählen</label>
							{#if nonMemberUsers.length === 0}
								<p class="text-muted-foreground text-xs italic">
									Alle verfügbaren Plattform-Benutzer sind bereits Mitglied in diesem Team.
								</p>
							{:else}
								<select
									id="invite-user"
									name="username"
									bind:value={selectedInviteUser}
									required
									class="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-offset-2"
								>
									<option value="" disabled selected>-- Benutzer auswählen --</option>
									{#each nonMemberUsers as user (user.username)}
										<option value={user.username}>
											{user.name ? `${user.name} (${user.username})` : user.username}
										</option>
									{/each}
								</select>
							{/if}
						</div>

						<div class="rounded-md border border-border/50 bg-muted/40 p-3 text-xs text-muted-foreground flex gap-2 items-start">
							<ShieldCheckIcon class="size-4 shrink-0 text-primary mt-0.5" />
							<div>
								Eingeladene Mitglieder erhalten sofort Zugriff auf alle für <strong class="text-foreground">{selectedTeamForInvite.name}</strong> freigegebenen Ordner, Dateien und Deployments.
							</div>
						</div>
					</Card.Content>

					<Card.Footer class="border-t border-border/50 flex justify-end gap-2 py-3">
						<Button
							variant="outline"
							size="sm"
							type="button"
							onclick={() => (selectedTeamForInvite = null)}
						>
							Abbrechen
						</Button>
						<Button
							size="sm"
							type="submit"
							class="gap-1.5"
							disabled={!selectedInviteUser || nonMemberUsers.length === 0}
						>
							<UserPlusIcon class="size-3.5" />
							Hinzufügen
						</Button>
					</Card.Footer>
				</form>
			</Card.Root>
		</div>
	{/if}
</div>
