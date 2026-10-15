import { env } from '$env/dynamic/private';

export interface UserProfile {
	name: string;
	email: string;
	username: string;
	groups: string[];
}

function getAuthentikBaseUrl(): string {
	const issuer = env.OIDC_ISSUER_URL || 'http://auth.localhost:8080/application/o/skip-platform/';
	try {
		const u = new URL(issuer);
		return `${u.protocol}//${u.host}`;
	} catch {
		return 'http://auth.localhost:8080';
	}
}

export function createAuthorizationUrl(origin: string, state: string): string {
	const baseUrl = getAuthentikBaseUrl();
	const clientId = env.OIDC_CLIENT_ID || 'kTR1jMV4yE1AauRard9rMBoD0yBs1yQN8TEczVjh';
	const redirectUri = env.OIDC_REDIRECT_URI || `${origin}/auth/callback`;

	const params = new URLSearchParams({
		response_type: 'code',
		client_id: clientId,
		redirect_uri: redirectUri,
		scope: 'openid profile email groups',
		state
	});

	return `${baseUrl}/application/o/authorize/?${params.toString()}`;
}

export function createLogoutUrl(origin: string): string {
	const baseUrl = getAuthentikBaseUrl();
	const postLogoutRedirect = encodeURIComponent(`${origin}/login`);
	return `${baseUrl}/if/flow/default-invalidation-flow/?next=${postLogoutRedirect}`;
}

export async function exchangeCode(
	code: string,
	origin: string
): Promise<{ access_token: string; id_token?: string; expires_in?: number }> {
	const clientId = env.OIDC_CLIENT_ID || 'kTR1jMV4yE1AauRard9rMBoD0yBs1yQN8TEczVjh';
	const clientSecret = env.OIDC_CLIENT_SECRET || 'K32Ch9QIxp6RKZ4cqgMnSUgT2axdO25iHGYT8INefiYHCN7F1a8sWSC0yQwvnYin845sxVDNIPhkVjNysbRY4FQ1omGiEv5kuWESQJmgzuleYTtYMzfGN5XK7t7P2wbs';
	const redirectUri = env.OIDC_REDIRECT_URI || `${origin}/auth/callback`;

	// Der Token-Endpunkt wird serverseitig aufgerufen: im Cluster ueber die
	// interne Service-URL (OIDC_TOKEN_URL aus platform-env), sonst ueber den Ingress.
	const tokenUrl = env.OIDC_TOKEN_URL || `${getAuthentikBaseUrl()}/application/o/token/`;

	const body = new URLSearchParams({
		grant_type: 'authorization_code',
		code,
		client_id: clientId,
		client_secret: clientSecret,
		redirect_uri: redirectUri
	});

	const response = await fetch(tokenUrl, {
		method: 'POST',
		headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
		body
	});

	if (!response.ok) {
		const err = await response.text();
		throw new Error(`Token exchange failed (${response.status}): ${err}`);
	}

	return await response.json();
}

export function decodeJwtPayload(token: string): Record<string, any> {
	try {
		const parts = token.split('.');
		if (parts.length < 2) return {};
		const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
		const json = decodeURIComponent(
			atob(base64)
				.split('')
				.map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
				.join('')
		);
		return JSON.parse(json);
	} catch {
		return {};
	}
}

export function extractUserProfile(tokens: {
	id_token?: string;
	access_token: string;
}): UserProfile {
	const payload = decodeJwtPayload(tokens.id_token || tokens.access_token);

	const username =
		payload.preferred_username ||
		payload.username ||
		payload.name ||
		payload.email ||
		payload.sub ||
		'User';
	const name = payload.name || payload.preferred_username || username;
	const email = payload.email || `${username}@fh-swf.de`;
	let groups: string[] = [];

	if (Array.isArray(payload.groups)) {
		groups = Array.from(
			new Set(payload.groups.filter((g): g is string => typeof g === 'string' && g.trim() !== ''))
		);
	} else if (typeof payload.groups === 'string' && payload.groups.trim() !== '') {
		groups = [payload.groups.trim()];
	}

	return { name, email, username, groups };
}

export function getApiAuthHeaders(locals: App.Locals): Record<string, string> {
	if (locals.token) {
		return { Authorization: `Bearer ${locals.token}` };
	}
	if (locals.user?.username) {
		return { 'X-User': locals.user.username };
	}
	return { 'X-User': 'developer@skip.de' };
}
