import { env } from '$env/dynamic/private';
import { getApiAuthHeaders } from '$lib/server/auth';
import { error, redirect, type RequestHandler } from '@sveltejs/kit';

export const GET: RequestHandler = async ({ url, fetch, locals }) => {
	const path = url.searchParams.get('path');
	if (!path) {
		throw error(400, 'Pfad fehlt');
	}

	const headers = getApiAuthHeaders(locals);
	const res = await fetch(
		`${env.API_URL}/api/storage/presigned-url?path=${encodeURIComponent(path)}&action=download`,
		{ headers }
	);

	if (!res.ok) {
		const body = await res.json().catch(() => ({}));
		throw error(res.status, body.detail ?? 'Download-URL konnte nicht erzeugt werden');
	}

	const data = await res.json();
	if (!data.url) {
		throw error(500, 'Keine Download-URL erhalten');
	}

	throw redirect(303, data.url);
};
