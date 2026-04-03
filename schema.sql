--
-- PostgreSQL database dump
--

\restrict v261TdTfrfn2PLWSfQV6wSZWitsLVGgpUJZ1X5jboRlSGV7GeHzK82hS0TZvbrl

-- Dumped from database version 18.3
-- Dumped by pg_dump version 18.3

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: taskstatus; Type: TYPE; Schema: public; Owner: testops-user
--

CREATE TYPE public.taskstatus AS ENUM (
    'pending',
    'in_progress',
    'done',
    'cancelled'
);


ALTER TYPE public.taskstatus OWNER TO "testops-user";

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: testops-user
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO "testops-user";

--
-- Name: categories; Type: TABLE; Schema: public; Owner: testops-user
--

CREATE TABLE public.categories (
    id integer NOT NULL,
    slug character varying(60) NOT NULL,
    name character varying(120) NOT NULL,
    is_critical boolean NOT NULL,
    display_order integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.categories OWNER TO "testops-user";

--
-- Name: categories_id_seq; Type: SEQUENCE; Schema: public; Owner: testops-user
--

CREATE SEQUENCE public.categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.categories_id_seq OWNER TO "testops-user";

--
-- Name: categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: testops-user
--

ALTER SEQUENCE public.categories_id_seq OWNED BY public.categories.id;


--
-- Name: clusters; Type: TABLE; Schema: public; Owner: testops-user
--

CREATE TABLE public.clusters (
    id integer NOT NULL,
    name character varying(60) NOT NULL,
    location_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.clusters OWNER TO "testops-user";

--
-- Name: clusters_id_seq; Type: SEQUENCE; Schema: public; Owner: testops-user
--

CREATE SEQUENCE public.clusters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.clusters_id_seq OWNER TO "testops-user";

--
-- Name: clusters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: testops-user
--

ALTER SEQUENCE public.clusters_id_seq OWNED BY public.clusters.id;


--
-- Name: environments; Type: TABLE; Schema: public; Owner: testops-user
--

CREATE TABLE public.environments (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    display_order integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.environments OWNER TO "testops-user";

--
-- Name: environments_id_seq; Type: SEQUENCE; Schema: public; Owner: testops-user
--

CREATE SEQUENCE public.environments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.environments_id_seq OWNER TO "testops-user";

--
-- Name: environments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: testops-user
--

ALTER SEQUENCE public.environments_id_seq OWNED BY public.environments.id;


--
-- Name: locations; Type: TABLE; Schema: public; Owner: testops-user
--

CREATE TABLE public.locations (
    id integer NOT NULL,
    code character varying(30) NOT NULL,
    label character varying(120) NOT NULL,
    zone character varying(30) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.locations OWNER TO "testops-user";

--
-- Name: locations_id_seq; Type: SEQUENCE; Schema: public; Owner: testops-user
--

CREATE SEQUENCE public.locations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.locations_id_seq OWNER TO "testops-user";

--
-- Name: locations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: testops-user
--

ALTER SEQUENCE public.locations_id_seq OWNED BY public.locations.id;


--
-- Name: runs; Type: TABLE; Schema: public; Owner: testops-user
--

CREATE TABLE public.runs (
    id character varying(40) NOT NULL,
    status character varying(20) NOT NULL,
    env character varying(30) NOT NULL,
    location character varying(30) NOT NULL,
    cluster character varying(60) NOT NULL,
    overall_rate double precision NOT NULL,
    verdict character varying(20) NOT NULL,
    categories json NOT NULL,
    started_at timestamp with time zone NOT NULL,
    completed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.runs OWNER TO "testops-user";

--
-- Name: tasks; Type: TABLE; Schema: public; Owner: testops-user
--

CREATE TABLE public.tasks (
    id integer NOT NULL,
    title character varying(255) NOT NULL,
    description text,
    status public.taskstatus NOT NULL,
    user_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.tasks OWNER TO "testops-user";

--
-- Name: tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: testops-user
--

CREATE SEQUENCE public.tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tasks_id_seq OWNER TO "testops-user";

--
-- Name: tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: testops-user
--

ALTER SEQUENCE public.tasks_id_seq OWNED BY public.tasks.id;


--
-- Name: test_cases; Type: TABLE; Schema: public; Owner: testops-user
--

CREATE TABLE public.test_cases (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    category_id integer NOT NULL,
    display_order integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.test_cases OWNER TO "testops-user";

--
-- Name: test_cases_id_seq; Type: SEQUENCE; Schema: public; Owner: testops-user
--

CREATE SEQUENCE public.test_cases_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.test_cases_id_seq OWNER TO "testops-user";

--
-- Name: test_cases_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: testops-user
--

ALTER SEQUENCE public.test_cases_id_seq OWNED BY public.test_cases.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: testops-user
--

CREATE TABLE public.users (
    id integer NOT NULL,
    name character varying(120) NOT NULL,
    email character varying(255) NOT NULL,
    hashed_password character varying(255) NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.users OWNER TO "testops-user";

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: testops-user
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO "testops-user";

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: testops-user
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: categories id; Type: DEFAULT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.categories ALTER COLUMN id SET DEFAULT nextval('public.categories_id_seq'::regclass);


--
-- Name: clusters id; Type: DEFAULT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.clusters ALTER COLUMN id SET DEFAULT nextval('public.clusters_id_seq'::regclass);


--
-- Name: environments id; Type: DEFAULT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.environments ALTER COLUMN id SET DEFAULT nextval('public.environments_id_seq'::regclass);


--
-- Name: locations id; Type: DEFAULT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.locations ALTER COLUMN id SET DEFAULT nextval('public.locations_id_seq'::regclass);


--
-- Name: tasks id; Type: DEFAULT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.tasks ALTER COLUMN id SET DEFAULT nextval('public.tasks_id_seq'::regclass);


--
-- Name: test_cases id; Type: DEFAULT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.test_cases ALTER COLUMN id SET DEFAULT nextval('public.test_cases_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: clusters clusters_pkey; Type: CONSTRAINT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.clusters
    ADD CONSTRAINT clusters_pkey PRIMARY KEY (id);


--
-- Name: environments environments_name_key; Type: CONSTRAINT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.environments
    ADD CONSTRAINT environments_name_key UNIQUE (name);


--
-- Name: environments environments_pkey; Type: CONSTRAINT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.environments
    ADD CONSTRAINT environments_pkey PRIMARY KEY (id);


--
-- Name: locations locations_pkey; Type: CONSTRAINT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.locations
    ADD CONSTRAINT locations_pkey PRIMARY KEY (id);


--
-- Name: runs runs_pkey; Type: CONSTRAINT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.runs
    ADD CONSTRAINT runs_pkey PRIMARY KEY (id);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);


--
-- Name: test_cases test_cases_pkey; Type: CONSTRAINT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.test_cases
    ADD CONSTRAINT test_cases_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_categories_id; Type: INDEX; Schema: public; Owner: testops-user
--

CREATE INDEX ix_categories_id ON public.categories USING btree (id);


--
-- Name: ix_categories_slug; Type: INDEX; Schema: public; Owner: testops-user
--

CREATE UNIQUE INDEX ix_categories_slug ON public.categories USING btree (slug);


--
-- Name: ix_clusters_id; Type: INDEX; Schema: public; Owner: testops-user
--

CREATE INDEX ix_clusters_id ON public.clusters USING btree (id);


--
-- Name: ix_clusters_name; Type: INDEX; Schema: public; Owner: testops-user
--

CREATE UNIQUE INDEX ix_clusters_name ON public.clusters USING btree (name);


--
-- Name: ix_environments_id; Type: INDEX; Schema: public; Owner: testops-user
--

CREATE INDEX ix_environments_id ON public.environments USING btree (id);


--
-- Name: ix_locations_code; Type: INDEX; Schema: public; Owner: testops-user
--

CREATE UNIQUE INDEX ix_locations_code ON public.locations USING btree (code);


--
-- Name: ix_locations_id; Type: INDEX; Schema: public; Owner: testops-user
--

CREATE INDEX ix_locations_id ON public.locations USING btree (id);


--
-- Name: ix_tasks_id; Type: INDEX; Schema: public; Owner: testops-user
--

CREATE INDEX ix_tasks_id ON public.tasks USING btree (id);


--
-- Name: ix_test_cases_id; Type: INDEX; Schema: public; Owner: testops-user
--

CREATE INDEX ix_test_cases_id ON public.test_cases USING btree (id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: testops-user
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_id; Type: INDEX; Schema: public; Owner: testops-user
--

CREATE INDEX ix_users_id ON public.users USING btree (id);


--
-- Name: clusters clusters_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.clusters
    ADD CONSTRAINT clusters_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.locations(id) ON DELETE CASCADE;


--
-- Name: tasks tasks_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: test_cases test_cases_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: testops-user
--

ALTER TABLE ONLY public.test_cases
    ADD CONSTRAINT test_cases_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict v261TdTfrfn2PLWSfQV6wSZWitsLVGgpUJZ1X5jboRlSGV7GeHzK82hS0TZvbrl

