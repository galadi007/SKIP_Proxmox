import { createLogoutUrl } from '$lib/server/auth';
import { redirect } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ url, cookies }) => {
	cookies.delete('skip_token', { path: '/' });
	cookies.delete('skip_user', { path: '/' });
	cookies.delete('skip_oauth_state', { path: '/' });

	const logoutUrl = createLogoutUrl(url.origin);
	throw redirect(302, logoutUrl);
};
