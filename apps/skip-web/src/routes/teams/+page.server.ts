import { env } from '$env/dynamic/private';
import { getApiAuthHeaders } from '$lib/server/auth';
import type { PageServerLoad, Actions } from './$types';
import { fail, redirect } from '@sveltejs/kit';

export interface TeamMember {
	username: string;
	name?: string | null;
	email?: string | null;
	is_owner: boolean;
}

export interface Team {
	id: string;
	name: string;
	description: string;
	owner: string;
	is_owner: boolean;
	members: TeamMember[];
}

export const load: PageServerLoad = async ({ fetch, cookies, locals }) => {
	const headers = getApiAuthHeaders(locals);

	const [teamsRes, usersRes] = await Promise.all([
		fetch(`${env.API_URL}/api/teams`, { headers }),
		fetch(`${env.API_URL}/api/users`, { headers })
	]);

	if (teamsRes.status === 401 || usersRes.status === 401) {
		cookies.delete('skip_token', { path: '/' });
		cookies.delete('skip_user', { path: '/' });
		throw redirect(303, '/login');
	}

	const teams: Team[] = teamsRes.ok ? await teamsRes.json() : [];
	const usersData = usersRes.ok ? await usersRes.json() : { users: [] };
	const availableUsers: { username: string; name?: string; email?: string }[] = usersData.users || [];

	return {
		teams,
		availableUsers,
		currentUsername: locals.user?.username || ''
	};
};

export const actions: Actions = {
	createTeam: async ({ request, fetch, locals }) => {
		const headers = getApiAuthHeaders(locals);
		const form = await request.formData();
		const name = form.get('name')?.toString().trim();
		const description = form.get('description')?.toString().trim() || '';

		if (!name) {
			return fail(400, { error: 'Bitte gib einen Teamnamen ein.' });
		}

		const res = await fetch(`${env.API_URL}/api/teams`, {
			method: 'POST',
			headers: {
				...headers,
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({ name, description })
		});

		if (!res.ok) {
			const err = await res.json().catch(() => ({}));
			return fail(res.status, {
				error: err.detail || 'Team konnte nicht erstellt werden.'
			});
		}

		return { message: `Team '${name}' erfolgreich gegründet!` };
	},

	deleteTeam: async ({ request, fetch, locals }) => {
		const headers = getApiAuthHeaders(locals);
		const form = await request.formData();
		const teamName = form.get('teamName')?.toString();

		if (!teamName) {
			return fail(400, { error: 'Teamname fehlt.' });
		}

		const res = await fetch(`${env.API_URL}/api/teams/${encodeURIComponent(teamName)}`, {
			method: 'DELETE',
			headers
		});

		if (!res.ok) {
			const err = await res.json().catch(() => ({}));
			return fail(res.status, {
				error: err.detail || 'Team konnte nicht gelöscht werden.'
			});
		}

		return { message: `Team '${teamName}' erfolgreich gelöscht.` };
	},

	addMember: async ({ request, fetch, locals }) => {
		const headers = getApiAuthHeaders(locals);
		const form = await request.formData();
		const teamName = form.get('teamName')?.toString();
		const username = form.get('username')?.toString().trim();

		if (!teamName || !username) {
			return fail(400, { error: 'Teamname und Benutzername erforderlich.' });
		}

		const res = await fetch(`${env.API_URL}/api/teams/${encodeURIComponent(teamName)}/members`, {
			method: 'POST',
			headers: {
				...headers,
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({ username })
		});

		if (!res.ok) {
			const err = await res.json().catch(() => ({}));
			return fail(res.status, {
				error: err.detail || `Benutzer '${username}' konnte nicht hinzugefügt werden.`
			});
		}

		return { message: `'${username}' wurde erfolgreich zum Team hinzugefügt!` };
	},

	removeMember: async ({ request, fetch, locals }) => {
		const headers = getApiAuthHeaders(locals);
		const form = await request.formData();
		const teamName = form.get('teamName')?.toString();
		const username = form.get('username')?.toString().trim();

		if (!teamName || !username) {
			return fail(400, { error: 'Teamname und Benutzername erforderlich.' });
		}

		const res = await fetch(
			`${env.API_URL}/api/teams/${encodeURIComponent(teamName)}/members/${encodeURIComponent(username)}`,
			{
				method: 'DELETE',
				headers
			}
		);

		if (!res.ok) {
			const err = await res.json().catch(() => ({}));
			return fail(res.status, {
				error: err.detail || `Mitglied '${username}' konnte nicht entfernt werden.`
			});
		}

		const isSelf = locals.user?.username === username;
		return {
			message: isSelf
				? `Du hast das Team '${teamName}' verlassen.`
				: `'${username}' wurde aus dem Team entfernt.`
		};
	}
};
