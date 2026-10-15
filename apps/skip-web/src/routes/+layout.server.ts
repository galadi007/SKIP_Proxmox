import { API_URL } from '$env/static/private';
import { getApiAuthHeaders } from '$lib/server/auth';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ fetch, locals }) => {
	if (!locals.user) {
		return { user: null };
	}

	try {
		const res = await fetch(`${API_URL}/api/me`, {
			headers: getApiAuthHeaders(locals)
		});
		if (res.ok) {
			const me = await res.json();
			const liveGroups = Array.from(
				new Set([...(locals.user.groups ?? []), ...(me.groups ?? [])])
			);
			const updatedUser = {
				...locals.user,
				name: me.name || locals.user.name,
				email: me.email || locals.user.email,
				groups: liveGroups
			};
			locals.user = updatedUser;
			return { user: updatedUser };
		}
	} catch (err) {
		console.warn('Live-Aktualisierung von /api/me fehlgeschlagen:', err);
	}

	return {
		user: {
			...locals.user,
			groups: Array.from(new Set(locals.user.groups ?? []))
		}
	};
};
