-- Adminer 4.7.1 PostgreSQL dump

DROP TABLE IF EXISTS "accounts";
CREATE TABLE "public"."accounts" (
    "name" character varying(16) NOT NULL,
    "upvote_comment" character varying(2048) NOT NULL,
    CONSTRAINT "accounts_name" PRIMARY KEY ("name")
) WITH (oids = false);

CREATE INDEX "ix_accounts_6ae999552a0d2dca" ON "public"."accounts" USING btree ("name");


DROP TABLE IF EXISTS "commands";
CREATE TABLE "public"."commands" (
    "authorperm" character varying(300) NOT NULL,
    "command" character varying(256) NOT NULL,
    "account" character varying(16) NOT NULL,
    "valid" boolean NOT NULL,
    "created" timestamp NOT NULL,
    "in_progress" boolean NOT NULL,
    "done" boolean NOT NULL,
    "block" integer NOT NULL,
    CONSTRAINT "commands_authorperm" PRIMARY KEY ("authorperm")
) WITH (oids = false);

CREATE INDEX "ix_commands_567819135781dcea" ON "public"."commands" USING btree ("authorperm");


DROP TABLE IF EXISTS "configuration";
DROP SEQUENCE IF EXISTS configuration_id_seq;
CREATE SEQUENCE configuration_id_seq INCREMENT 1 MINVALUE 1 MAXVALUE 2147483647 START 1 CACHE 1;

CREATE TABLE "public"."configuration" (
    "id" integer DEFAULT nextval('configuration_id_seq') NOT NULL,
    "last_streamed_block" integer DEFAULT '0' NOT NULL,
    "last_processed_timestamp" timestamp,
    "last_command" timestamp,
    "last_vote" timestamp
) WITH (oids = false);


DROP TABLE IF EXISTS "failed_vote_log";
CREATE TABLE "public"."failed_vote_log" (
    "authorperm" character varying(300) NOT NULL,
    "voter" character varying(16) NOT NULL,
    "error" character varying(1024) NOT NULL,
    "timestamp" timestamp NOT NULL,
    "vote_weight" real NOT NULL,
    "vote_delay_min" real NOT NULL,
    "min_vp" real NOT NULL,
    "vp" real NOT NULL,
    "vote_when_vp_reached" boolean NOT NULL,
    CONSTRAINT "failed_vote_log_authorperm_voter" PRIMARY KEY ("authorperm", "voter")
) WITH (oids = false);

CREATE INDEX "ix_failed_vote_log_75a831de789ee9f6" ON "public"."failed_vote_log" USING btree ("authorperm", "voter");


DROP TABLE IF EXISTS "pending_votes";
CREATE TABLE "public"."pending_votes" (
    "authorperm" character varying(300) NOT NULL,
    "voter" character varying(16) NOT NULL,
    "vote_weight" real NOT NULL,
    "comment_timestamp" timestamp NOT NULL,
    "vote_delay_min" real NOT NULL,
    "created" timestamp NOT NULL,
    "min_vp" real DEFAULT '90' NOT NULL,
    "vote_when_vp_reached" boolean DEFAULT false NOT NULL,
    "vp_reached_order" smallint DEFAULT '1' NOT NULL,
    "max_net_votes" smallint DEFAULT '-1' NOT NULL,
    "max_pending_payout" real DEFAULT '-1' NOT NULL,
    "max_votes_per_day" smallint DEFAULT '-1' NOT NULL,
    "max_votes_per_week" smallint DEFAULT '-1' NOT NULL,
    "vp_scaler" real DEFAULT '0' NOT NULL,
    "leave_comment" boolean DEFAULT false NOT NULL,
    "comment_command" character varying(300),
    "vote_sbd" text,
    "exclude_declined_payout" boolean,
    "maximum_vote_delay_min" real DEFAULT '-1' NOT NULL,
    CONSTRAINT "pending_votes_authorperm_voter_vote_when_vp_reached" PRIMARY KEY ("authorperm", "voter", "vote_when_vp_reached")
) WITH (oids = false);

CREATE INDEX "ix_pending_votes_25f35862d08f9a78" ON "public"."pending_votes" USING btree ("authorperm", "voter", "vote_when_vp_reached");

CREATE INDEX "ix_pending_votes_75a831de789ee9f6" ON "public"."pending_votes" USING btree ("authorperm", "voter");

CREATE INDEX "pending_votes_vote_when_vp_reached" ON "public"."pending_votes" USING btree ("vote_when_vp_reached");

CREATE INDEX "pending_votes_voter" ON "public"."pending_votes" USING btree ("voter");


DROP TABLE IF EXISTS "posts";
CREATE TABLE "public"."posts" (
    "authorperm" character varying(300) NOT NULL,
    "author" character varying(16) NOT NULL,
    "created" timestamp NOT NULL,
    "block" integer NOT NULL,
    "tags" character varying(256),
    "app" character varying(256),
    "net_votes" integer,
    "vote_rshares" bigint,
    "pending_payout_value" character varying(20),
    "update" timestamp NOT NULL,
    "main_post" boolean DEFAULT true NOT NULL,
    "decline_payout" boolean DEFAULT false NOT NULL,
    "word_count" integer DEFAULT '0' NOT NULL,
    CONSTRAINT "posts_authorperm" PRIMARY KEY ("authorperm")
) WITH (oids = false);

CREATE INDEX "ix_posts_567819135781dcea" ON "public"."posts" USING btree ("authorperm");


DROP TABLE IF EXISTS "trail_vote_rules";
CREATE TABLE "public"."trail_vote_rules" (
    "voter_to_follow" character varying(16) NOT NULL,
    "account" character varying(16) NOT NULL,
    "only_main_post" boolean DEFAULT true NOT NULL,
    "vote_weight_treshold" real DEFAULT '0' NOT NULL,
    "include_authors" character varying(1024) DEFAULT '' NOT NULL,
    "exclude_authors" character varying(1024) DEFAULT '' NOT NULL,
    "min_vp" real DEFAULT '90' NOT NULL,
    "vote_weight_scaler" real DEFAULT '50' NOT NULL,
    "vote_weight_offset" real DEFAULT '0' NOT NULL,
    "max_votes_per_day" integer DEFAULT '-1' NOT NULL,
    "max_votes_per_week" integer DEFAULT '-1' NOT NULL,
    "include_tags" character varying(1024) DEFAULT '' NOT NULL,
    "exclude_tags" character varying(1024) DEFAULT '' NOT NULL,
    "exclude_declined_payout" boolean DEFAULT true NOT NULL,
    "minimum_vote_delay_min" real DEFAULT '13' NOT NULL,
    "maximum_vote_delay_min" real DEFAULT '9360' NOT NULL,
    "enabled" boolean DEFAULT true NOT NULL,
    "max_net_votes" integer DEFAULT '-1' NOT NULL,
    "max_pending_payout" real DEFAULT '-1' NOT NULL,
    "vp_scaler" real DEFAULT '0' NOT NULL,
    CONSTRAINT "trail_vote_rules_voter_account" PRIMARY KEY ("voter_to_follow", "account")
) WITH (oids = false);

CREATE INDEX "ix_trail_vote_rules_355e207b769c3ac8" ON "public"."trail_vote_rules" USING btree ("voter_to_follow", "account");


DROP TABLE IF EXISTS "vote_log";
CREATE TABLE "public"."vote_log" (
    "authorperm" character varying(300) NOT NULL,
    "author" character varying(16) NOT NULL,
    "voter" character varying(16) NOT NULL,
    "timestamp" timestamp NOT NULL,
    "vote_weight" real NOT NULL,
    "vote_delay_min" real NOT NULL,
    "voted_after_min" real NOT NULL,
    "vp" real NOT NULL,
    "vote_when_vp_reached" boolean NOT NULL,
    "performance" real,
    "last_update" timestamp DEFAULT '1970-01-01 00:00:00' NOT NULL,
    CONSTRAINT "vote_log_authorperm_voter" PRIMARY KEY ("authorperm", "voter")
) WITH (oids = false);

CREATE INDEX "ix_vote_log_75a831de789ee9f6" ON "public"."vote_log" USING btree ("authorperm", "voter");

CREATE INDEX "vote_log_timestamp_voter_author" ON "public"."vote_log" USING btree ("timestamp", "voter", "author");


DROP TABLE IF EXISTS "vote_rules";
CREATE TABLE "public"."vote_rules" (
    "voter" character varying(16) NOT NULL,
    "author" character varying(16) NOT NULL,
    "main_post" boolean DEFAULT true NOT NULL,
    "vote_delay_min" real DEFAULT '15' NOT NULL,
    "vote_weight" real DEFAULT '100' NOT NULL,
    "enabled" boolean DEFAULT true NOT NULL,
    "vote_sbd" real DEFAULT '0' NOT NULL,
    "max_votes_per_day" integer DEFAULT '-1' NOT NULL,
    "max_votes_per_week" integer DEFAULT '-1' NOT NULL,
    "include_tags" character varying(256),
    "exclude_tags" character varying(256),
    "vote_when_vp_reached" boolean DEFAULT false NOT NULL,
    "min_vp" real DEFAULT '90' NOT NULL,
    "vp_scaler" real DEFAULT '0' NOT NULL,
    "leave_comment" boolean DEFAULT false NOT NULL,
    "minimum_word_count" integer DEFAULT '0' NOT NULL,
    "include_apps" character varying(256),
    "exclude_apps" character varying(256),
    "exclude_declined_payout" boolean DEFAULT true NOT NULL,
    "vp_reached_order" smallint DEFAULT '1' NOT NULL,
    "max_net_votes" integer DEFAULT '-1' NOT NULL,
    "max_pending_payout" real DEFAULT '-1' NOT NULL,
    "include_text" character varying(256),
    "exclude_text" character varying(256),
    "maximum_vote_delay_min" real DEFAULT '-1' NOT NULL,
    CONSTRAINT "vote_rules_voter_author_main_post" PRIMARY KEY ("voter", "author", "main_post")
) WITH (oids = false);

CREATE INDEX "ix_vote_rules_71ebba0ac0022ce7" ON "public"."vote_rules" USING btree ("voter", "author", "main_post");

CREATE INDEX "vote_rules_author_main_post" ON "public"."vote_rules" USING btree ("author", "main_post");

CREATE INDEX "vote_rules_voter" ON "public"."vote_rules" USING btree ("voter");


DROP TABLE IF EXISTS "votes";
CREATE TABLE "public"."votes" (
    "authorperm" character varying(300) NOT NULL,
    "voter" character varying(16) NOT NULL,
    "block" integer NOT NULL,
    "timestamp" timestamp NOT NULL,
    "weight" real NOT NULL,
    CONSTRAINT "votes_authorperm_voter" PRIMARY KEY ("authorperm", "voter")
) WITH (oids = false);

CREATE INDEX "ix_votes_75a831de789ee9f6" ON "public"."votes" USING btree ("authorperm", "voter");


-- 2019-02-05 12:55:23.496746+01