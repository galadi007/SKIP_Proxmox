import { env } from '$env/dynamic/private';
import { redirect, type Handle } from '@sveltejs/kit';

const PUBLIC_PATHS = ['/login', '/auth/login', '/auth/callback', '/auth/logout'];

export const handle: Handle = async ({ event, resolve }) => {
	const token = event.cookies.get('skip_token') ?? null;
	const rawUser = event.cookies.get('skip_user') ?? null;

	let user: App.Locals['user'] = null;

	if (rawUser && token) {
		try {
			user = JSON.parse(rawUser);
		} catch {
			user = null;
		}
	}

	event.locals.token = token;
	event.locals.user = user;

	const pathname = event.url.pathname;
	const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + '/'));

	if (user && token && pathname === '/login') {
		throw redirect(303, '/templates');
	}

	if ((!user || !token) && !isPublic && !pathname.startsWith('/_app') && !pathname.includes('.')) {
		const target = pathname + event.url.search;

		if (env.AUTH_DIRECT_REDIRECT === 'true') {
			throw redirect(303, `/auth/login?redirect=${encodeURIComponent(target)}`);
		}

		throw redirect(303, `/login?redirect=${encodeURIComponent(target)}`);
	}

	return resolve(event);
};
