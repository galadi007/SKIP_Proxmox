import { redirect } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { createAuthorizationUrl } from '$lib/server/auth';

export const GET: RequestHandler = async ({ url, cookies }) => {
	const state = crypto.randomUUID();
	const returnUrl = url.searchParams.get('redirect') || '/templates';

	cookies.set('skip_oauth_state', state, {
		path: '/',
		httpOnly: true,
		sameSite: 'lax',
		secure: false,
		maxAge: 600 // 10 Minuten
	});

	cookies.set('skip_oauth_redirect', returnUrl, {
		path: '/',
		httpOnly: true,
		sameSite: 'lax',
		secure: false,
		maxAge: 600 // 10 Minuten
	});

	const authUrl = createAuthorizationUrl(url.origin, state);
	throw redirect(302, authUrl);
};
