CREATE TABLE `custom_charts` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`name` text NOT NULL,
	`sql` text NOT NULL,
	`chart_config` text NOT NULL,
	`database_id` integer,
	`created_by` integer,
	`created_at` text,
	`updated_at` text,
	FOREIGN KEY (`database_id`) REFERENCES `external_databases`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`created_by`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `custom_dashboards` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`name` text NOT NULL,
	`render_config` text NOT NULL,
	`created_by` integer,
	`created_at` text,
	`updated_at` text,
	FOREIGN KEY (`created_by`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `external_databases` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`name` text NOT NULL,
	`db_type` text DEFAULT 'postgresql' NOT NULL,
	`host` text DEFAULT 'localhost' NOT NULL,
	`port` integer DEFAULT 5432 NOT NULL,
	`database` text DEFAULT '' NOT NULL,
	`username` text DEFAULT '' NOT NULL,
	`password` text DEFAULT '' NOT NULL,
	`ssl_enabled` integer DEFAULT false NOT NULL,
	`file_path` text,
	`created_by` integer,
	`created_at` text,
	`updated_at` text,
	FOREIGN KEY (`created_by`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `users` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`name` text NOT NULL,
	`email` text NOT NULL,
	`password` text NOT NULL,
	`is_admin` integer DEFAULT false NOT NULL,
	`created_at` text,
	`updated_at` text
);
--> statement-breakpoint
CREATE UNIQUE INDEX `users_email_unique` ON `users` (`email`);