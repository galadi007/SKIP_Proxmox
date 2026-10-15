import { API_URL } from '$env/static/private';
import { getApiAuthHeaders } from '$lib/server/auth';
import type { PageServerLoad, Actions } from './$types';
import { fail, redirect } from '@sveltejs/kit';

export const load: PageServerLoad = async ({ fetch, url, cookies, locals }) => {
	const headers = getApiAuthHeaders(locals);
	const success = url.searchParams.get('success');
	const [depRes, usersRes] = await Promise.all([
		fetch(`${API_URL}/api/apps`, { headers }),
		fetch(`${API_URL}/api/users`, { headers })
	]);

	if (depRes.status === 401 || usersRes.status === 401) {
		cookies.delete('skip_token', { path: '/' });
		cookies.delete('skip_user', { path: '/' });
		throw redirect(303, '/login');
	}

	const deployments = depRes.ok ? await depRes.json() : [];
	const users = usersRes.ok ? (await usersRes.json()).users || [] : [];

	return { deployments, availableUsers: users, success };
};

export const actions: Actions = {
	delete: async ({ fetch, request, locals }) => {
		const headers = getApiAuthHeaders(locals);
		const form = await request.formData();
		const template = String(form.get('template') ?? '');
		const namespace = String(form.get('namespace') ?? '');
		const name = String(form.get('name') ?? '');
		const response = await fetch(
			`${API_URL}/api/apps/${encodeURIComponent(template)}/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}`,
			{ method: 'DELETE', headers }
		);
		if (!response.ok) {
			const body = await response.json().catch(() => ({}));
			return fail(response.status, { error: body.detail ?? `Delete failed (${response.status})` });
		}
		return { success: true };
	},
	addMember: async ({ fetch, request, locals }) => {
		const headers = getApiAuthHeaders(locals);
		const form = await request.formData();
		const template = String(form.get('template') ?? '');
		const namespace = String(form.get('namespace') ?? '');
		const name = String(form.get('name') ?? '');
		const username = String(form.get('username') ?? '');

		const response = await fetch(
			`${API_URL}/api/apps/${encodeURIComponent(template)}/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}/members`,
			{
				method: 'POST',
				headers: { ...headers, 'Content-Type': 'application/json' },
				body: JSON.stringify({ username })
			}
		);
		if (!response.ok) {
			const body = await response.json().catch(() => ({}));
			return fail(response.status, { error: body.detail ?? `Konnte Mitglied nicht hinzufügen (${response.status})` });
		}
		return { success: true };
	},
	removeMember: async ({ fetch, request, locals }) => {
		const headers = getApiAuthHeaders(locals);
		const form = await request.formData();
		const template = String(form.get('template') ?? '');
		const namespace = String(form.get('namespace') ?? '');
		const name = String(form.get('name') ?? '');
		const username = String(form.get('username') ?? '');

		const response = await fetch(
			`${API_URL}/api/apps/${encodeURIComponent(template)}/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}/members/${encodeURIComponent(username)}`,
			{ method: 'DELETE', headers }
		);
		if (!response.ok) {
			const body = await response.json().catch(() => ({}));
			return fail(response.status, { error: body.detail ?? `Konnte Mitglied nicht entfernen (${response.status})` });
		}
		return { success: true };
	}
};
