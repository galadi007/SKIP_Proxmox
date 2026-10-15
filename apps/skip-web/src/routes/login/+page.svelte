<script lang="ts">
	import ArrowRightIcon from '@lucide/svelte/icons/arrow-right';
	import CpuIcon from '@lucide/svelte/icons/cpu';
	import LayersIcon from '@lucide/svelte/icons/layers';
	import LockIcon from '@lucide/svelte/icons/lock';
	import ShieldCheckIcon from '@lucide/svelte/icons/shield-check';
	import SparklesIcon from '@lucide/svelte/icons/sparkles';

	import * as Card from '$lib/components/ui/card/index.js';
	import { Button } from '$lib/components/ui/button/index.js';

	let { data } = $props();

	const loginTarget = $derived(
		`/auth/login${data.redirectUrl ? `?redirect=${encodeURIComponent(data.redirectUrl)}` : ''}`
	);
</script>

<svelte:head>
	<title>Anmelden | SKIP Platform</title>
</svelte:head>

<div class="inset-0 h-screen flex items-center justify-center">
	
	<Card.Root>
		<Card.Header>
			<Card.Title><span class="text-xl font-bold">Melde dich mit deinem Account an</span></Card.Title>
		</Card.Header>

		<Card.Content class="space-y-4 pt-2">
			<Button
				href={loginTarget}
				size="lg"
				class="w-full gap-2 font-medium transition-all"
			>
				<SparklesIcon class="size-4" />
				<span>Mit Authentik anmelden</span>
				<ArrowRightIcon class="ms-auto size-4" />
			</Button>
		</Card.Content>
	</Card.Root>
</div>

 
