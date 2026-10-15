import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ url }) => {
	const redirectUrl = url.searchParams.get('redirect') || '/templates';
	return {
		redirectUrl
	};
};
