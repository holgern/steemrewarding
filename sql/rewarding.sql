-- Adminer 4.7.0 PostgreSQL dump

DROP TABLE IF EXISTS "accounts";
CREATE TABLE "public"."accounts" (
    "name" character varying(16) NOT NULL,
    "upvote_comment" character varying(2048) NOT NULL,
    CONSTRAINT "accounts_name" PRIMARY KEY ("name")
) WITH (oids = false);


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
    "last_processed_timestamp" timestamp
) WITH (oids = false);


DROP TABLE IF EXISTS "pending_votes";
CREATE TABLE "public"."pending_votes" (
    "authorperm" character varying(300) NOT NULL,
    "voter" character varying(16) NOT NULL,
    "vote_weight" real NOT NULL,
    "comment_timestamp" timestamp NOT NULL,
    "vote_delay_min" real NOT NULL,
    "created" timestamp NOT NULL,
    "min_vp" real NOT NULL,
    "vote_when_vp_reached" boolean NOT NULL,
    "vp_reached_order" smallint NOT NULL,
    "max_net_votes" smallint NOT NULL,
    "max_pending_payout" smallint NOT NULL,
    "max_votes_per_day" smallint NOT NULL,
    "max_votes_per_week" smallint NOT NULL,
    "vp_scaler" real NOT NULL,
    "leave_comment" boolean NOT NULL,
    CONSTRAINT "pending_votes_authorperm_voter_vote_when_vp_reached" PRIMARY KEY ("authorperm", "voter", "vote_when_vp_reached")
) WITH (oids = false);

CREATE INDEX "ix_pending_votes_75a831de789ee9f6" ON "public"."pending_votes" USING btree ("authorperm", "voter");

CREATE INDEX "pending_votes_vote_when_vp_reached" ON "public"."pending_votes" USING btree ("vote_when_vp_reached");


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
    CONSTRAINT "vote_log_authorperm_voter" PRIMARY KEY ("authorperm", "voter")
) WITH (oids = false);

CREATE INDEX "ix_vote_log_75a831de789ee9f6" ON "public"."vote_log" USING btree ("authorperm", "voter");


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
    CONSTRAINT "vote_rules_voter_author_main_post" PRIMARY KEY ("voter", "author", "main_post")
) WITH (oids = false);

CREATE INDEX "vote_rules_author_main_post" ON "public"."vote_rules" USING btree ("author", "main_post");


DROP TABLE IF EXISTS "votes";
CREATE TABLE "public"."votes" (
    "authorperm" character varying(300) NOT NULL,
    "voter" character varying(16) NOT NULL,
    "block" integer NOT NULL,
    "timestamp" timestamp NOT NULL,
    "weight" real NOT NULL,
    CONSTRAINT "votes_authorperm_voter" PRIMARY KEY ("authorperm", "voter")
) WITH (oids = false);


-- 2019-01-23 17:15:28.846529+01
