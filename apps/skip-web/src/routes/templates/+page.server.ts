import { API_URL } from '$env/static/private';
import { getApiAuthHeaders } from '$lib/server/auth';
import type { PageServerLoad } from './$types';
import { redirect } from '@sveltejs/kit';

export const load: PageServerLoad = async ({ fetch, cookies, locals }) => {
	const headers = getApiAuthHeaders(locals);

	const res = await fetch(`${API_URL}/api/templates`, {
		headers
	});

	if (res.status === 401) {
		cookies.delete('skip_token', { path: '/' });
		cookies.delete('skip_user', { path: '/' });
		throw redirect(303, '/login');
	}

	if (!res.ok) {
		throw new Error(`Failed to load templates: ${res.status}`);
	}

	const templates = await res.json();

	return { templates };
};
