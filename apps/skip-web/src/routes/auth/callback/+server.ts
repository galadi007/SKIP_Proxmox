import { error, redirect } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { exchangeCode, extractUserProfile } from '$lib/server/auth';

export const GET: RequestHandler = async ({ url, cookies }) => {
	const code = url.searchParams.get('code');
	const state = url.searchParams.get('state');
	const savedState = cookies.get('skip_oauth_state');
	const returnUrl = cookies.get('skip_oauth_redirect') || '/templates';

	if (!code) {
		const errorParam = url.searchParams.get('error_description') || url.searchParams.get('error');
		throw error(400, `Authentifizierung fehlgeschlagen: ${errorParam || 'Kein Code übergeben'}`);
	}

	if (state && savedState && state !== savedState) {
		throw error(400, 'Ungültiger State-Parameter (CSRF-Schutz)');
	}

	cookies.delete('skip_oauth_state', { path: '/' });
	cookies.delete('skip_oauth_redirect', { path: '/' });

	try {
		const tokens = await exchangeCode(code, url.origin);
		const userProfile = extractUserProfile(tokens);

		cookies.set('skip_token', tokens.access_token, {
			path: '/',
			httpOnly: true,
			sameSite: 'lax',
			secure: false,
			maxAge: tokens.expires_in || 3600 * 8
		});

		cookies.set('skip_user', JSON.stringify(userProfile), {
			path: '/',
			httpOnly: true,
			sameSite: 'lax',
			secure: false,
			maxAge: tokens.expires_in || 3600 * 8
		});
	} catch (err: any) {
		console.error('OIDC Callback Fehler:', err);
		throw error(500, `Token-Austausch fehlgeschlagen: ${err.message}`);
	}

	throw redirect(302, returnUrl);
};
