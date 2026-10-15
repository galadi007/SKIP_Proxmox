// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		interface Locals {
			user: {
				name: string;
				email: string;
				username: string;
				groups: string[];
			} | null;
			token: string | null;
		}
		interface PageData {
			user?: {
				name: string;
				email: string;
				username: string;
				groups: string[];
			} | null;
		}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
