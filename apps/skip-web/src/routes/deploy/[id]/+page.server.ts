import { API_URL } from '$env/static/private';
import { getApiAuthHeaders } from '$lib/server/auth';
import type { PageServerLoad, Actions } from './$types';
import { fail, redirect } from '@sveltejs/kit';

export const load: PageServerLoad = async ({ fetch, params, locals }) => {
	const headers = getApiAuthHeaders(locals);

	const [templateRes, nsRes] = await Promise.all([
		fetch(`${API_URL}/api/templates/${encodeURIComponent(params.id)}`, { headers }),
		fetch(`${API_URL}/api/namespaces`, { headers })
	]);

	if (!templateRes.ok) {
		throw new Error(`Template '${params.id}' not found`);
	}

	// Enthaelt parameters, capabilities, components sowie die JSON-Schema-Sicht.
	const template = await templateRes.json();

	let allowedNamespaces: string[] = ['team-data'];
	if (nsRes.ok) {
		const nsData = await nsRes.json();
		allowedNamespaces = nsData.namespaces || ['team-data'];
	}

	return { template, allowedNamespaces };
};

export const actions: Actions = {
	deploy: async ({ fetch, request, params, locals }) => {
		const headers = getApiAuthHeaders(locals);
		const form = await request.formData();
		const name = String(form.get('release_name') ?? '');
		const namespace = String(form.get('namespace') ?? '');
		const values = Object.fromEntries(
			[...form.entries()]
				.filter(([key]) => !['release_name', 'namespace'].includes(key))
				.map(([key, value]) => [key, String(value)])
		);
		const response = await fetch(`${API_URL}/api/apps`, {
			method: 'POST',
			headers: { ...headers, 'Content-Type': 'application/json' },
			body: JSON.stringify({ template: params.id, name, namespace, values })
		});
		if (!response.ok) {
			const body = await response.json().catch(() => ({}));
			return fail(response.status, { error: body.detail ?? `Deployment failed (${response.status})` });
		}
		redirect(303, `/deployments?success=${encodeURIComponent(name)}`);
	}
};
