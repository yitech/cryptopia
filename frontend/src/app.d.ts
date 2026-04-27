declare global {
	namespace App {
		interface Locals {
			user: {
				id: number;
				username: string;
				email: string;
				full_name: string | null;
				bio: string | null;
				avatar_url: string | null;
			} | null;
		}
		interface PageData {
			user: App.Locals['user'];
		}
	}
}

export {};
