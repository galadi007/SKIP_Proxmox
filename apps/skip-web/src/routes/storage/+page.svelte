<script lang="ts">
	import type { PageData, ActionData } from './$types';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import { enhance } from '$app/forms';
	import { invalidateAll } from '$app/navigation';

	import FolderIcon from '@lucide/svelte/icons/folder';
	import FolderPlusIcon from '@lucide/svelte/icons/folder-plus';
	import FileIcon from '@lucide/svelte/icons/file';
	import HardDriveIcon from '@lucide/svelte/icons/hard-drive';
	import DownloadIcon from '@lucide/svelte/icons/download';
	import Share2Icon from '@lucide/svelte/icons/share-2';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import UploadIcon from '@lucide/svelte/icons/upload';
	import UsersIcon from '@lucide/svelte/icons/users';
	import UserIcon from '@lucide/svelte/icons/user';
	import XIcon from '@lucide/svelte/icons/x';
	import ChevronRightIcon from '@lucide/svelte/icons/chevron-right';
	import ArrowLeftIcon from '@lucide/svelte/icons/arrow-left';
	import ShieldCheckIcon from '@lucide/svelte/icons/shield-check';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	let activeTab = $state<'home' | 'sharedWithMe' | 'myShares'>('home');
	let isUploadOpen = $state(false);
	let isNewFolderOpen = $state(false);
	let newFolderName = $state('');

	let selectedItemForShare = $state<{ path: string; isDir: boolean } | null>(null);

	let shareType = $state<'user' | 'group'>('group');
	let targetUser = $state('');
	let targetGroup = $state('');
	let permission = $state<'read' | 'read_write'>('read');

	function formatBytes(bytes: number): string {
		if (bytes === 0) return '0 B';
		const k = 1024;
		const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
	}

	function formatDate(dateStr?: string): string {
		if (!dateStr) return '-';
		try {
			return new Date(dateStr).toLocaleString('de-DE', {
				day: '2-digit',
				month: '2-digit',
				year: 'numeric',
				hour: '2-digit',
				minute: '2-digit'
			});
		} catch {
			return dateStr;
		}
	}

	// Berechnet Breadcrumbs aus dem aktuellen Ordnerpfad (z. B. "ordner1/ordner2")
	const breadcrumbs = $derived.by(() => {
		const folder = data.currentFolder?.trim() || '';
		if (!folder) return [];
		const segments = folder.split('/').filter(Boolean);
		let accumulated = '';
		return segments.map((seg, i) => {
			accumulated = accumulated ? `${accumulated}/${seg}` : seg;
			return {
				name: seg,
				path: accumulated,
				isLast: i === segments.length - 1
			};
		});
	});

	// Elternordner für "Eine Ebene nach oben"
	const parentFolder = $derived.by(() => {
		const folder = data.currentFolder?.trim() || '';
		if (!folder) return null;
		const segments = folder.split('/').filter(Boolean);
		if (segments.length <= 1) return '';
		return segments.slice(0, -1).join('/');
	});
</script>

<svelte:head>
	<title>Dateien & Speicher | SKIP Platform</title>
</svelte:head>

<div class="container mx-auto px-4 py-8">
	<!-- Page Header -->
	<div class="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<div>
			<h1 class="text-2xl font-semibold tracking-tight">Dateien & Speicher</h1>
			<p class="text-muted-foreground mt-1 text-sm">
				Dein persönliches Home-Verzeichnis, Unterordner und geteilte Daten
			</p>
		</div>
		<div class="flex items-center gap-2">
			<Button variant="outline" onclick={() => (isNewFolderOpen = true)} class="gap-2">
				<FolderPlusIcon class="size-4" />
				Neuer Ordner
			</Button>
			<Button onclick={() => (isUploadOpen = true)} class="gap-2">
				<UploadIcon class="size-4" />
				Datei hochladen
			</Button>
		</div>
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
				<Card.Title class="text-sm font-medium">Home-Verzeichnis</Card.Title>
				<FolderIcon class="text-muted-foreground size-4" />
			</Card.Header>
			<Card.Content>
				<div class="font-mono text-base font-semibold truncate" title={data.overview.home_prefix}>
					{data.overview.home_prefix}
				</div>
				<p class="text-muted-foreground mt-1 text-xs">
					Benutzer: <span class="font-semibold text-foreground">{data.overview.username}</span>
				</p>
			</Card.Content>
		</Card.Root>

		<Card.Root>
			<Card.Header class="flex flex-row items-center justify-between pb-2">
				<Card.Title class="text-sm font-medium">Einträge im Ordner</Card.Title>
				<FileIcon class="text-muted-foreground size-4" />
			</Card.Header>
			<Card.Content>
				<div class="text-2xl font-bold">{data.files.length}</div>
				<p class="text-muted-foreground mt-1 text-xs">
					{data.files.filter((f) => f.is_dir).length} Ordner, {data.files.filter((f) => !f.is_dir).length} Datei(en)
				</p>
			</Card.Content>
		</Card.Root>

		<Card.Root>
			<Card.Header class="flex flex-row items-center justify-between pb-2">
				<Card.Title class="text-sm font-medium">Belegter Speicher</Card.Title>
				<HardDriveIcon class="text-muted-foreground size-4" />
			</Card.Header>
			<Card.Content>
				<div class="text-2xl font-bold">{formatBytes(data.overview.total_size_bytes)}</div>
				<p class="text-muted-foreground mt-1 text-xs">
					{data.overview.total_files} Datei(en) insgesamt im Home-Verzeichnis
				</p>
			</Card.Content>
		</Card.Root>
	</div>

	<!-- Navigation Tabs -->
	<div class="mb-6 flex gap-2 border-b border-border pb-2">
		<button
			type="button"
			class={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
				activeTab === 'home'
					? 'bg-primary text-primary-foreground shadow-sm'
					: 'text-muted-foreground hover:bg-muted hover:text-foreground'
			}`}
			onclick={() => (activeTab = 'home')}
		>
			Mein Home-Verzeichnis
		</button>
		<button
			type="button"
			class={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
				activeTab === 'sharedWithMe'
					? 'bg-primary text-primary-foreground shadow-sm'
					: 'text-muted-foreground hover:bg-muted hover:text-foreground'
			}`}
			onclick={() => (activeTab = 'sharedWithMe')}
		>
			Mit mir geteilt ({data.sharedWithMe.length})
		</button>
		<button
			type="button"
			class={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
				activeTab === 'myShares'
					? 'bg-primary text-primary-foreground shadow-sm'
					: 'text-muted-foreground hover:bg-muted hover:text-foreground'
			}`}
			onclick={() => (activeTab = 'myShares')}
		>
			Meine Freigaben ({data.myShares.length})
		</button>
	</div>

	<!-- Tab 1: Mein Home-Verzeichnis -->
	{#if activeTab === 'home'}
		<!-- Breadcrumb-Navigation -->
		<div class="mb-4 flex items-center justify-between rounded-lg border border-border/60 bg-muted/30 px-4 py-2.5 text-sm">
			<div class="flex items-center gap-1.5 flex-wrap">
				<a
					href="/storage"
					class={`flex items-center gap-1.5 font-medium hover:text-foreground transition-colors ${
						!data.currentFolder ? 'text-foreground' : 'text-muted-foreground'
					}`}
				>
					<FolderIcon class="size-4 text-primary" />
					<span>Home</span>
				</a>

				{#each breadcrumbs as b}
					<ChevronRightIcon class="size-3.5 text-muted-foreground" />
					{#if b.isLast}
						<span class="font-medium text-foreground">{b.name}</span>
					{:else}
						<a
							href={`/storage?folder=${encodeURIComponent(b.path)}`}
							class="text-muted-foreground hover:text-foreground transition-colors"
						>
							{b.name}
						</a>
					{/if}
				{/each}
			</div>

			{#if parentFolder !== null}
				<Button
					variant="ghost"
					size="sm"
					href={parentFolder ? `/storage?folder=${encodeURIComponent(parentFolder)}` : '/storage'}
					class="gap-1.5 text-xs text-muted-foreground hover:text-foreground h-7 px-2"
				>
					<ArrowLeftIcon class="size-3.5" />
					Eine Ebene hoch
				</Button>
			{/if}
		</div>

		{#if data.files.length === 0}
			<Card.Root>
				<Card.Content class="flex flex-col items-center justify-center py-16 text-center">
					<FolderIcon class="text-muted-foreground/40 mb-3 size-12" />
					<p class="text-muted-foreground text-sm">
						{#if data.currentFolder}
							Dieser Ordner ist noch leer.
						{:else}
							Noch keine Dateien oder Ordner im Home-Verzeichnis vorhanden.
						{/if}
					</p>
					<div class="mt-4 flex gap-2">
						<Button onclick={() => (isNewFolderOpen = true)} variant="outline" class="gap-2">
							<FolderPlusIcon class="size-4" />
							Ordner erstellen
						</Button>
						<Button onclick={() => (isUploadOpen = true)} class="gap-2">
							<UploadIcon class="size-4" />
							Datei hochladen
						</Button>
					</div>
				</Card.Content>
			</Card.Root>
		{:else}
			<Card.Root>
				<Table.Root>
					<Table.Header>
						<Table.Row>
							<Table.Head>Name</Table.Head>
							<Table.Head>Größe</Table.Head>
							<Table.Head>Zuletzt geändert</Table.Head>
							<Table.Head class="text-end">Aktionen</Table.Head>
						</Table.Row>
					</Table.Header>
					<Table.Body>
						{#each data.files as file (file.key)}
							<Table.Row class="hover:bg-muted/50 transition-colors">
								<Table.Cell class="font-medium">
									{#if file.is_dir}
										<a
											href={`/storage?folder=${encodeURIComponent(file.key)}`}
											class="flex items-center gap-2 hover:underline text-foreground group"
										>
											<FolderIcon class="text-amber-500 size-4 group-hover:scale-110 transition-transform" />
											<span class="font-semibold">{file.name}</span>
										</a>
									{:else}
										<div class="flex items-center gap-2">
											<FileIcon class="text-muted-foreground size-4" />
											<span>{file.name}</span>
										</div>
									{/if}
								</Table.Cell>
								<Table.Cell class="text-muted-foreground text-sm font-mono">
									{file.is_dir ? 'Ordner' : formatBytes(file.size_bytes)}
								</Table.Cell>
								<Table.Cell class="text-muted-foreground text-sm">
									{formatDate(file.last_modified)}
								</Table.Cell>
								<Table.Cell class="text-end">
									<div class="flex items-center justify-end gap-1">
										{#if !file.is_dir}
											<Button
												variant="ghost"
												size="sm"
												href={`/storage/download?path=${encodeURIComponent(data.overview.home_prefix + file.key)}`}
												title="Herunterladen"
												class="gap-1.5"
											>
												<DownloadIcon class="size-3.5" />
												Download
											</Button>
										{/if}

										<!-- Freigeben: Funktioniert jetzt fuer DATEIEN und GANZE ORDNER -->
										<Button
											variant="outline"
											size="sm"
											onclick={() => {
												selectedItemForShare = { path: file.key, isDir: file.is_dir };
												shareType = 'group';
												targetUser = '';
												targetGroup = data.availableGroups[0] ?? '';
											}}
											title={file.is_dir ? 'Ganzen Ordner freigeben' : 'Datei freigeben'}
											class="gap-1.5"
										>
											<Share2Icon class="size-3.5" />
											Teilen
										</Button>

										<form
											method="POST"
											action="?/deleteFile"
											use:enhance={() => {
												return async ({ update }) => {
													await update();
													await invalidateAll();
												};
											}}
										>
											<input type="hidden" name="path" value={file.key} />
											<Button
												variant="ghost"
												size="icon"
												type="submit"
												title={file.is_dir ? 'Ordner löschen' : 'Datei löschen'}
												class="text-destructive hover:bg-destructive/10 size-8"
											>
												<Trash2Icon class="size-3.5" />
											</Button>
										</form>
									</div>
								</Table.Cell>
							</Table.Row>
						{/each}
					</Table.Body>
				</Table.Root>
			</Card.Root>
		{/if}
	{/if}

	<!-- Tab 2: Mit mir geteilt (inkl. Gruppenfreigaben) -->
	{#if activeTab === 'sharedWithMe'}
		{#if data.sharedWithMe.length === 0}
			<Card.Root>
				<Card.Content class="flex flex-col items-center justify-center py-16 text-center">
					<UsersIcon class="text-muted-foreground/40 mb-3 size-12" />
					<p class="text-muted-foreground text-sm">Aktuell sind keine Dateien oder Ordner mit dir oder deinen Gruppen geteilt.</p>
				</Card.Content>
			</Card.Root>
		{:else}
			<Card.Root>
				<Table.Root>
					<Table.Header>
						<Table.Row>
							<Table.Head>Objekt / Pfad</Table.Head>
							<Table.Head>Besitzer</Table.Head>
							<Table.Head>Freigegeben für</Table.Head>
							<Table.Head>Berechtigung</Table.Head>
							<Table.Head class="text-end">Aktionen</Table.Head>
						</Table.Row>
					</Table.Header>
					<Table.Body>
						{#each data.sharedWithMe as share (share.share_id)}
							<Table.Row>
								<Table.Cell class="font-medium">
									<div class="flex items-center gap-2 font-mono text-sm">
										<FileIcon class="text-muted-foreground size-4" />
										<span>{share.path}</span>
									</div>
								</Table.Cell>
								<Table.Cell class="text-muted-foreground text-sm">
									<Badge variant="outline">{share.owner}</Badge>
								</Table.Cell>
								<Table.Cell>
									{#if share.target_groups?.length > 0}
										<div class="flex flex-wrap gap-1">
											{#each share.target_groups as g}
												<Badge variant="secondary" class="gap-1 font-normal">
													<UsersIcon class="size-3" />
													Gruppe: {g}
												</Badge>
											{/each}
										</div>
									{:else}
										<Badge variant="secondary" class="gap-1 font-normal">
											<UserIcon class="size-3" />
											Direkt
										</Badge>
									{/if}
								</Table.Cell>
								<Table.Cell>
									{#if share.permission === 'read_write'}
										<Badge variant="default">Lesen & Schreiben</Badge>
									{:else}
										<Badge variant="outline">Nur Lesen</Badge>
									{/if}
								</Table.Cell>
								<Table.Cell class="text-end">
									<Button
										variant="outline"
										size="sm"
										href={`/storage/download?path=${encodeURIComponent(`home/${share.owner}/${share.path}`)}`}
										class="gap-1.5"
									>
										<DownloadIcon class="size-3.5" />
										Download
									</Button>
								</Table.Cell>
							</Table.Row>
						{/each}
					</Table.Body>
				</Table.Root>
			</Card.Root>
		{/if}
	{/if}

	<!-- Tab 3: Meine aktiven Freigaben -->
	{#if activeTab === 'myShares'}
		{#if data.myShares.length === 0}
			<Card.Root>
				<Card.Content class="flex flex-col items-center justify-center py-16 text-center">
					<Share2Icon class="text-muted-foreground/40 mb-3 size-12" />
					<p class="text-muted-foreground text-sm">Du hast bisher keine Dateien oder Ordner freigegeben.</p>
				</Card.Content>
			</Card.Root>
		{:else}
			<Card.Root>
				<Table.Root>
					<Table.Header>
						<Table.Row>
							<Table.Head>Freigegebener Pfad</Table.Head>
							<Table.Head>Freigegeben an</Table.Head>
							<Table.Head>Berechtigung</Table.Head>
							<Table.Head>Erstellt am</Table.Head>
							<Table.Head class="text-end">Aktionen</Table.Head>
						</Table.Row>
					</Table.Header>
					<Table.Body>
						{#each data.myShares as share (share.share_id)}
							<Table.Row>
								<Table.Cell class="font-medium font-mono text-sm">
									{share.path}
								</Table.Cell>
								<Table.Cell>
									<div class="flex flex-wrap gap-1">
										{#each share.target_groups ?? [] as g}
											<Badge variant="secondary" class="gap-1 font-normal">
												<UsersIcon class="size-3" />
												Gruppe: {g}
											</Badge>
										{/each}
										{#each share.target_users ?? [] as u}
											<Badge variant="outline" class="gap-1 font-normal">
												<UserIcon class="size-3" />
												{u}
											</Badge>
										{/each}
									</div>
								</Table.Cell>
								<Table.Cell>
									{#if share.permission === 'read_write'}
										<Badge variant="default">Lesen & Schreiben</Badge>
									{:else}
										<Badge variant="outline">Nur Lesen</Badge>
									{/if}
								</Table.Cell>
								<Table.Cell class="text-muted-foreground text-sm">
									{formatDate(share.created_at)}
								</Table.Cell>
								<Table.Cell class="text-end">
									<form
										method="POST"
										action="?/deleteShare"
										use:enhance={() => {
											return async ({ update }) => {
												await update();
												await invalidateAll();
											};
										}}
									>
										<input type="hidden" name="shareId" value={share.share_id} />
										<Button
											variant="ghost"
											size="sm"
											type="submit"
											class="text-destructive hover:bg-destructive/10 gap-1.5"
										>
											<Trash2Icon class="size-3.5" />
											Widerrufen
										</Button>
									</form>
								</Table.Cell>
							</Table.Row>
						{/each}
					</Table.Body>
				</Table.Root>
			</Card.Root>
		{/if}
	{/if}

	<!-- Modal: Neuer Ordner -->
	{#if isNewFolderOpen}
		<div class="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
			<Card.Root class="w-full max-w-md shadow-2xl border-border">
				<Card.Header class="flex flex-row items-center justify-between pb-3">
					<div>
						<Card.Title class="text-lg">Neuen Ordner erstellen</Card.Title>
						<Card.Description class="text-xs">
							{#if data.currentFolder}
								Im Ordner: <span class="font-mono text-foreground font-semibold">{data.currentFolder}</span>
							{:else}
								Im Stammverzeichnis (Home)
							{/if}
						</Card.Description>
					</div>
					<Button variant="ghost" size="icon" class="size-8" onclick={() => (isNewFolderOpen = false)}>
						<XIcon class="size-4" />
					</Button>
				</Card.Header>

				<form
					method="POST"
					action="?/createFolder"
					use:enhance={() => {
						return async ({ update }) => {
							await update();
							isNewFolderOpen = false;
							newFolderName = '';
							await invalidateAll();
						};
					}}
				>
					<Card.Content class="space-y-4">
						<input type="hidden" name="parent" value={data.currentFolder || ''} />
						<div>
							<label for="folder-name-input" class="text-sm font-medium mb-1.5 block">Ordnername</label>
							<input
								id="folder-name-input"
								type="text"
								name="name"
								placeholder="z. B. forschungsdaten, messungen"
								bind:value={newFolderName}
								required
								class="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-offset-2"
							/>
						</div>
					</Card.Content>

					<Card.Footer class="border-t border-border/50 flex justify-end gap-2 py-3">
						<Button variant="outline" size="sm" type="button" onclick={() => (isNewFolderOpen = false)}>
							Abbrechen
						</Button>
						<Button size="sm" type="submit" class="gap-1.5">
							<FolderPlusIcon class="size-3.5" />
							Erstellen
						</Button>
					</Card.Footer>
				</form>
			</Card.Root>
		</div>
	{/if}

	<!-- Modal: Datei hochladen -->
	{#if isUploadOpen}
		<div class="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
			<Card.Root class="w-full max-w-md shadow-2xl border-border">
				<Card.Header class="flex flex-row items-center justify-between pb-3">
					<div>
						<Card.Title class="text-lg">Datei hochladen</Card.Title>
						<Card.Description class="text-xs">
							{#if data.currentFolder}
								Zielordner: <span class="font-mono text-foreground font-semibold">{data.currentFolder}</span>
							{:else}
								Ziel: Stammverzeichnis (Home)
							{/if}
						</Card.Description>
					</div>
					<Button variant="ghost" size="icon" class="size-8" onclick={() => (isUploadOpen = false)}>
						<XIcon class="size-4" />
					</Button>
				</Card.Header>

				<form
					method="POST"
					action="?/upload"
					enctype="multipart/form-data"
					use:enhance={() => {
						return async ({ update }) => {
							await update();
							isUploadOpen = false;
							await invalidateAll();
						};
					}}
				>
					<Card.Content class="space-y-4">
						<input type="hidden" name="folder" value={data.currentFolder || ''} />
						<div>
							<label for="file-upload" class="text-sm font-medium mb-1.5 block">Datei auswählen</label>
							<input
								id="file-upload"
								type="file"
								name="file"
								required
								class="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-offset-2 file:border-0 file:bg-transparent file:text-sm file:font-medium"
							/>
						</div>
					</Card.Content>

					<Card.Footer class="border-t border-border/50 flex justify-end gap-2 py-3">
						<Button variant="outline" size="sm" type="button" onclick={() => (isUploadOpen = false)}>
							Abbrechen
						</Button>
						<Button size="sm" type="submit" class="gap-1.5">
							<UploadIcon class="size-3.5" />
							Hochladen
						</Button>
					</Card.Footer>
				</form>
			</Card.Root>
		</div>
	{/if}

	<!-- Modal: Freigeben (Fuer DATEIEN oder ORDNER) -->
	{#if selectedItemForShare}
		<div class="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
			<Card.Root class="w-full max-w-md shadow-2xl border-border">
				<Card.Header class="flex flex-row items-center justify-between pb-3">
					<div>
						<Card.Title class="text-lg">
							{selectedItemForShare.isDir ? 'Ordner freigeben' : 'Datei freigeben'}
						</Card.Title>
						<Card.Description class="text-xs font-mono">
							{selectedItemForShare.path}
						</Card.Description>
					</div>
					<Button
						variant="ghost"
						size="icon"
						class="size-8"
						onclick={() => (selectedItemForShare = null)}
					>
						<XIcon class="size-4" />
					</Button>
				</Card.Header>

				<form
					method="POST"
					action="?/createShare"
					class="space-y-4"
					use:enhance={() => {
						return async ({ update }) => {
							await update();
							selectedItemForShare = null;
							await invalidateAll();
						};
					}}
				>
					<Card.Content class="space-y-4">
						<input type="hidden" name="path" value={selectedItemForShare.path} />
						<input type="hidden" name="shareType" value={shareType} />

						<!-- Share Type Selection (Group vs User) -->
						<div>
							<span class="text-sm font-medium mb-1.5 block">Freigeben für</span>
							<div class="grid grid-cols-2 gap-2">
								<button
									type="button"
									class={`flex items-center justify-center gap-2 rounded-md border p-2 text-sm transition-colors ${
										shareType === 'group'
											? 'border-primary bg-primary/10 text-primary font-medium'
											: 'border-input hover:bg-muted text-muted-foreground'
									}`}
									onclick={() => (shareType = 'group')}
								>
									<UsersIcon class="size-4" />
									Authentik-Gruppe
								</button>
								<button
									type="button"
									class={`flex items-center justify-center gap-2 rounded-md border p-2 text-sm transition-colors ${
										shareType === 'user'
											? 'border-primary bg-primary/10 text-primary font-medium'
											: 'border-input hover:bg-muted text-muted-foreground'
									}`}
									onclick={() => (shareType = 'user')}
								>
									<UserIcon class="size-4" />
									Einzelner Benutzer
								</button>
							</div>
						</div>

						<!-- Target Selection -->
						{#if shareType === 'group'}
							<div>
								<label for="target-group-select" class="text-sm font-medium mb-1.5 block">Zielgruppe</label>
								{#if data.availableGroups && data.availableGroups.length > 0}
									<select
										id="target-group-select"
										name="targetGroup"
										bind:value={targetGroup}
										class="border-input bg-background ring-offset-background focus:ring-ring flex h-9 w-full rounded-md border px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-offset-2"
										required
									>
										<option value="" disabled selected>Gruppe auswählen...</option>
										{#each data.availableGroups as g}
											<option value={g}>{g}</option>
										{/each}
									</select>
								{:else}
									<input
										id="target-group-select"
										type="text"
										name="targetGroup"
										placeholder="Gruppenname (z. B. team-data)"
										bind:value={targetGroup}
										class="border-input bg-background ring-offset-background focus:ring-ring flex h-9 w-full rounded-md border px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-offset-2"
										required
									/>
								{/if}
							</div>
						{:else}
							<div>
								<label for="target-user-select" class="text-sm font-medium mb-1.5 block">Zielbenutzer</label>
								{#if data.availableUsers && data.availableUsers.length > 0}
									<select
										id="target-user-select"
										name="targetUser"
										bind:value={targetUser}
										class="border-input bg-background ring-offset-background focus:ring-ring flex h-9 w-full rounded-md border px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-offset-2"
										required
									>
										<option value="" disabled selected>Benutzer auswählen...</option>
										{#each data.availableUsers as u}
											<option value={u.username}>{u.name || u.username} ({u.email || u.username})</option>
										{/each}
									</select>
								{:else}
									<input
										id="target-user-select"
										type="text"
										name="targetUser"
										placeholder="Benutzername (z. B. max.mustermann)"
										bind:value={targetUser}
										class="border-input bg-background ring-offset-background focus:ring-ring flex h-9 w-full rounded-md border px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-offset-2"
										required
									/>
								{/if}
							</div>
						{/if}

						<!-- Permissions -->
						<div>
							<label for="permission-select" class="text-sm font-medium mb-1.5 block">Berechtigungsstufe</label>
							<select
								id="permission-select"
								name="permission"
								bind:value={permission}
								class="border-input bg-background ring-offset-background focus:ring-ring flex h-9 w-full rounded-md border px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-offset-2"
							>
								<option value="read">Nur Lesen (Download)</option>
								<option value="read_write">Lesen & Schreiben (Änderungen erlaubt)</option>
							</select>
						</div>

						<div class="rounded-md border border-border/50 bg-muted/40 p-3 text-xs text-muted-foreground flex gap-2 items-start">
							<ShieldCheckIcon class="size-4 shrink-0 text-primary mt-0.5" />
							<div>
								{#if selectedItemForShare.isDir}
									{#if shareType === 'group'}
										💡 Alle Mitglieder von <strong class="text-foreground">{targetGroup || '...'}</strong> erhalten automatisch Zugriff auf diesen Ordner und <strong>alle darin enthaltenen Dateien</strong>.
									{:else}
										💡 Der Benutzer <strong class="text-foreground">{targetUser || '...'}</strong> erhält Zugriff auf diesen Ordner und <strong>alle darin enthaltenen Dateien</strong>.
									{/if}
								{:else}
									{#if shareType === 'group'}
										Alle Authentik-Benutzer der Gruppe <strong class="text-foreground">{targetGroup || '...'}</strong> erhalten sofort Zugriff auf diese Datei.
									{:else}
										Der Benutzer <strong class="text-foreground">{targetUser || '...'}</strong> erhält sofortigen Zugriff auf diese Datei.
									{/if}
								{/if}
							</div>
						</div>
					</Card.Content>

					<Card.Footer class="border-t border-border/50 flex justify-end gap-2 py-3">
						<Button variant="outline" size="sm" type="button" onclick={() => (selectedItemForShare = null)}>
							Abbrechen
						</Button>
						<Button size="sm" type="submit" class="gap-1.5">
							<Share2Icon class="size-3.5" />
							Freigeben
						</Button>
					</Card.Footer>
				</form>
			</Card.Root>
		</div>
	{/if}
</div>
