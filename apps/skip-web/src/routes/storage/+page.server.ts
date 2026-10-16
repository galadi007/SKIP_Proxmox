import { env } from '$env/dynamic/private';
import { getApiAuthHeaders } from '$lib/server/auth';
import type { PageServerLoad, Actions } from './$types';
import { fail, redirect } from '@sveltejs/kit';

export const load: PageServerLoad = async ({ fetch, url, cookies, locals }) => {
	const headers = getApiAuthHeaders(locals);
	const currentFolder = url.searchParams.get('folder') ?? '';

	const [overviewRes, filesRes, mySharesRes, sharedWithMeRes, usersRes, groupsRes] =
		await Promise.all([
			fetch(`${env.API_URL}/api/storage/overview`, { headers }),
			fetch(`${env.API_URL}/api/storage/files?folder=${encodeURIComponent(currentFolder)}`, { headers }),
			fetch(`${env.API_URL}/api/storage/shares/my`, { headers }),
			fetch(`${env.API_URL}/api/storage/shares/shared-with-me`, { headers }),
			fetch(`${env.API_URL}/api/users`, { headers }),
			fetch(`${env.API_URL}/api/groups`, { headers })
		]);

	if (overviewRes.status === 401 || filesRes.status === 401) {
		cookies.delete('skip_token', { path: '/' });
		cookies.delete('skip_user', { path: '/' });
		throw redirect(303, '/login');
	}

	const overview = overviewRes.ok
		? await overviewRes.json()
		: {
				username: locals.user?.username || 'User',
				bucket: 'skip-storage',
				home_prefix: `home/${locals.user?.username || 'user'}/`,
				total_files: 0,
				total_size_bytes: 0,
				endpoint: 'http://s3.localhost:8080'
			};

	const files = filesRes.ok ? await filesRes.json() : [];
	const myShares = mySharesRes.ok ? await mySharesRes.json() : [];
	const sharedWithMe = sharedWithMeRes.ok ? await sharedWithMeRes.json() : [];
	const users = usersRes.ok ? (await usersRes.json()).users || [] : [];
	const groups = groupsRes.ok ? (await groupsRes.json()).groups || [] : [];

	return {
		overview,
		files,
		currentFolder,
		myShares,
		sharedWithMe,
		availableUsers: users,
		availableGroups: groups,
		user: locals.user
	};
};

export const actions: Actions = {
	upload: async ({ fetch, request, locals }) => {
		const headers = getApiAuthHeaders(locals);
		const form = await request.formData();
		const file = form.get('file');

		if (!file || !(file instanceof File) || file.size === 0) {
			return fail(400, { error: 'Bitte eine gültige Datei zum Hochladen auswählen.' });
		}

		const uploadForm = new FormData();
		uploadForm.append('file', file);
		const folder = String(form.get('folder') ?? '');
		if (folder) {
			uploadForm.append('folder', folder);
		}

		const res = await fetch(`${env.API_URL}/api/storage/upload`, {
			method: 'POST',
			headers,
			body: uploadForm
		});

		if (!res.ok) {
			const body = await res.json().catch(() => ({}));
			return fail(res.status, {
				error: body.detail ?? `Upload fehlgeschlagen (${res.status})`
			});
		}

		return { success: true, message: `Datei "${file.name}" erfolgreich hochgeladen.` };
	},

	createFolder: async ({ fetch, request, locals }) => {
		const headers = getApiAuthHeaders(locals);
		const form = await request.formData();
		const name = String(form.get('name') ?? '').trim();
		const parent = String(form.get('parent') ?? '').trim();

		if (!name) {
			return fail(400, { error: 'Bitte einen Ordnernamen eingeben.' });
		}

		const res = await fetch(`${env.API_URL}/api/storage/folders`, {
			method: 'POST',
			headers: { ...headers, 'Content-Type': 'application/json' },
			body: JSON.stringify({ name, parent })
		});

		if (!res.ok) {
			const body = await res.json().catch(() => ({}));
			return fail(res.status, {
				error: body.detail ?? `Ordner konnte nicht erstellt werden (${res.status})`
			});
		}

		return { success: true, message: `Ordner "${name}" erfolgreich erstellt.` };
	},

	deleteFile: async ({ fetch, request, locals }) => {
		const headers = getApiAuthHeaders(locals);
		const form = await request.formData();
		const path = String(form.get('path') ?? '');

		if (!path) {
			return fail(400, { error: 'Dateipfad fehlt.' });
		}

		const res = await fetch(
			`${env.API_URL}/api/storage/files?path=${encodeURIComponent(path)}`,
			{
				method: 'DELETE',
				headers
			}
		);

		if (!res.ok) {
			const body = await res.json().catch(() => ({}));
			return fail(res.status, {
				error: body.detail ?? `Löschen fehlgeschlagen (${res.status})`
			});
		}

		return { success: true, message: 'Element gelöscht.' };
	},

	createShare: async ({ fetch, request, locals }) => {
		const headers = getApiAuthHeaders(locals);
		const form = await request.formData();
		const path = String(form.get('path') ?? '');
		const shareType = String(form.get('shareType') ?? 'group');
		const targetUser = String(form.get('targetUser') ?? '').trim();
		const targetGroup = String(form.get('targetGroup') ?? '').trim();
		const permission = String(form.get('permission') ?? 'read');

		if (!path) {
			return fail(400, { error: 'Pfad fehlt.' });
		}

		if (shareType === 'user' && !targetUser) {
			return fail(400, { error: 'Bitte einen Zielbenutzer auswählen.' });
		}
		if (shareType === 'group' && !targetGroup) {
			return fail(400, { error: 'Bitte eine Zielgruppe auswählen.' });
		}

		const payload = {
			path,
			target_users: shareType === 'user' ? [targetUser] : [],
			target_groups: shareType === 'group' ? [targetGroup] : [],
			permission
		};

		const res = await fetch(`${env.API_URL}/api/storage/shares`, {
			method: 'POST',
			headers: { ...headers, 'Content-Type': 'application/json' },
			body: JSON.stringify(payload)
		});

		if (!res.ok) {
			const body = await res.json().catch(() => ({}));
			return fail(res.status, {
				error: body.detail ?? `Freigabe fehlgeschlagen (${res.status})`
			});
		}

		return { success: true, message: 'Freigabe erfolgreich erstellt.' };
	},

	deleteShare: async ({ fetch, request, locals }) => {
		const headers = getApiAuthHeaders(locals);
		const form = await request.formData();
		const shareId = String(form.get('shareId') ?? '');

		if (!shareId) {
			return fail(400, { error: 'Share-ID fehlt.' });
		}

		const res = await fetch(
			`${env.API_URL}/api/storage/shares/${encodeURIComponent(shareId)}`,
			{
				method: 'DELETE',
				headers
			}
		);

		if (!res.ok) {
			const body = await res.json().catch(() => ({}));
			return fail(res.status, {
				error: body.detail ?? `Widerruf fehlgeschlagen (${res.status})`
			});
		}

		return { success: true, message: 'Freigabe widerrufen.' };
	}
};
