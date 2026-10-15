<script lang="ts">
	import BadgeCheckIcon from '@lucide/svelte/icons/badge-check';
	import ChevronsUpDownIcon from '@lucide/svelte/icons/chevrons-up-down';
	import LogInIcon from '@lucide/svelte/icons/log-in';
	import LogOutIcon from '@lucide/svelte/icons/log-out';
	import ShieldIcon from '@lucide/svelte/icons/shield';
	import UsersIcon from '@lucide/svelte/icons/users';

	import * as Avatar from '$lib/components/ui/avatar/index.js';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import { useSidebar } from '$lib/components/ui/sidebar/index.js';

	let {
		user = null
	}: {
		user?: {
			name: string;
			email: string;
			username?: string;
			groups?: string[];
			avatar?: string;
		} | null;
	} = $props();

	const sidebar = useSidebar();

	const initials = $derived(
		user?.name
			? user.name
					.split(' ')
					.map((n) => n[0])
					.join('')
					.slice(0, 2)
					.toUpperCase()
			: 'US'
	);
</script>

<Sidebar.Menu>
	{#if user}
		<Sidebar.MenuItem>
			<DropdownMenu.Root>
				<DropdownMenu.Trigger>
					{#snippet child({ props })}
						<Sidebar.MenuButton
							{...props}
							size="lg"
							class="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
						>
							<Avatar.Root class="size-8 rounded-lg">
								{#if user.avatar}
									<Avatar.Image src={user.avatar} alt={user.name} />
								{/if}
								<Avatar.Fallback class="rounded-lg bg-primary/10 text-xs font-semibold text-primary">
									{initials}
								</Avatar.Fallback>
							</Avatar.Root>
							<div class="grid flex-1 text-start text-sm leading-tight">
								<span class="truncate font-medium">{user.name}</span>
								<span class="truncate text-xs text-muted-foreground">{user.email}</span>
							</div>
							<ChevronsUpDownIcon class="ms-auto size-4 text-muted-foreground" />
						</Sidebar.MenuButton>
					{/snippet}
				</DropdownMenu.Trigger>
				<DropdownMenu.Content
					class="w-(--bits-dropdown-menu-anchor-width) min-w-56 rounded-lg"
					side={sidebar.isMobile ? 'bottom' : 'right'}
					align="end"
					sideOffset={4}
				>
					<DropdownMenu.Label class="p-0 font-normal">
						<div class="flex items-center gap-2 px-2 py-2 text-start text-sm">
							<Avatar.Root class="size-8 rounded-lg">
								{#if user.avatar}
									<Avatar.Image src={user.avatar} alt={user.name} />
								{/if}
								<Avatar.Fallback class="rounded-lg bg-primary/10 text-xs font-semibold text-primary">
									{initials}
								</Avatar.Fallback>
							</Avatar.Root>
							<div class="grid flex-1 text-start text-sm leading-tight">
								<span class="truncate font-medium">{user.name}</span>
								<span class="truncate text-xs text-muted-foreground">{user.email}</span>
							</div>
						</div>
					</DropdownMenu.Label>
					{#if user.groups && user.groups.length > 0}
						<DropdownMenu.Separator />
						<div class="px-2 py-1.5 text-xs text-muted-foreground">
							<div class="flex items-center gap-1.5 font-medium">
								<UsersIcon class="size-3.5" />
								<span>Gruppen:</span>
							</div>
							<div class="mt-1 flex flex-wrap gap-1">
								{#each Array.from(new Set(user.groups)) as group}
									<span class="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-foreground">
										{group}
									</span>
								{/each}
							</div>
						</div>
					{/if}
					<DropdownMenu.Separator />
					<DropdownMenu.Item class="text-destructive focus:text-destructive cursor-pointer">
						{#snippet child({ props })}
							<a href="/auth/logout" class="flex w-full items-center gap-2" {...props}>
								<LogOutIcon class="size-4" />
								<span>Abmelden</span>
							</a>
						{/snippet}
					</DropdownMenu.Item>
				</DropdownMenu.Content>
			</DropdownMenu.Root>
		</Sidebar.MenuItem>
	{:else}
		<Sidebar.MenuItem>
			<Sidebar.MenuButton
				size="lg"
				class="bg-primary text-primary-foreground hover:bg-primary/90 justify-center gap-2 font-medium"
			>
				{#snippet child({ props })}
					<a href="/auth/login" class="flex w-full items-center justify-center gap-2" {...props}>
						<LogInIcon class="size-4" />
						<span>Mit Authentik anmelden</span>
					</a>
				{/snippet}
			</Sidebar.MenuButton>
		</Sidebar.MenuItem>
	{/if}
</Sidebar.Menu>
