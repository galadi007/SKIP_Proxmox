<script lang="ts" module>
	import LifeBuoyIcon from '@lucide/svelte/icons/life-buoy';
	import SendIcon from '@lucide/svelte/icons/send';
	import LayoutGridIcon from '@lucide/svelte/icons/layout-grid';
	import RocketIcon from '@lucide/svelte/icons/rocket';
	import FolderIcon from '@lucide/svelte/icons/folder';
	import UsersIcon from '@lucide/svelte/icons/users';
	import ServerIcon from '@lucide/svelte/icons/server';
	import LockIcon from '@lucide/svelte/icons/lock';

	const data = {
		navPlatform: [
			{
				title: 'Templates',
				url: '/templates',
				icon: LayoutGridIcon,
				isActive: true
			},
			{
				title: 'Deployments',
				url: '/deployments',
				icon: RocketIcon,
				isActive: false
			},
			{
				title: 'Dateien',
				url: '/storage',
				icon: FolderIcon,
				isActive: false
			},
			{
				title: 'Teams',
				url: '/teams',
				icon: UsersIcon,
				isActive: false
			}
		],
		navCluster: [
			{
				title: 'Nodes',
				url: '#',
				icon: ServerIcon,
				isActive: false
			},
			{
				title: 'Secrets',
				url: '#',
				icon: LockIcon,
				isActive: false
			}
		],
		navSecondary: [
			{
				title: 'Support',
				url: '#',
				icon: LifeBuoyIcon
			},
			{
				title: 'Feedback',
				url: '#',
				icon: SendIcon
			}
		]
	};
</script>

<script lang="ts">
	import Nav from './nav.svelte';
	import NavSecondary from './nav-secondary.svelte';
	import NavUser from './nav-user.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import CommandIcon from '@lucide/svelte/icons/command';
	import type { ComponentProps } from 'svelte';

	interface Props extends ComponentProps<typeof Sidebar.Root> {
		user?: App.Locals['user'];
	}

	let { ref = $bindable(null), user = null, ...restProps }: Props = $props();
</script>

<Sidebar.Root bind:ref variant="inset" {...restProps}>
	<Sidebar.Header>
		<Sidebar.Menu>
			<Sidebar.MenuItem>
				<Sidebar.MenuButton size="lg">
					{#snippet child({ props })}
						<a href="/" {...props}>
							<div
								class="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground"
							>
								<CommandIcon class="size-4" />
							</div>
							<div class="grid flex-1 text-start text-sm leading-tight">
								<span class="truncate font-medium">SKIP Platform</span>
								<span class="truncate text-xs text-muted-foreground">Self-Service AI & Data</span>
							</div>
						</a>
					{/snippet}
				</Sidebar.MenuButton>
			</Sidebar.MenuItem>
		</Sidebar.Menu>
	</Sidebar.Header>
	<Sidebar.Content>
		<Nav title="Plattform" items={data.navPlatform} />
		<Nav title="Cluster" items={data.navCluster} />
		<NavSecondary items={data.navSecondary} class="mt-auto" />
	</Sidebar.Content>
	<Sidebar.Footer>
		<NavUser {user} />
	</Sidebar.Footer>
</Sidebar.Root>
