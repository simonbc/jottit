drop table drafts;
drop table revisions;
drop table pages;
drop table designs;
drop table sites;

create table sites (
    id serial primary key,
    secret_url text not null,
    public_url text,
    title text,
    subtitle text,
    email text,
    password text,
    change_pwd_token text,
    security text, -- private | public | open
    show_primer boolean not null default true,
    deleted boolean not null default false,
    created timestamp not null default (current_timestamp at time zone 'utc'),
    partner text
);

create table designs (
    id serial primary key,
    site_id int not null references sites(id),
    header_color text,
    title_color text,
    title_font text,
    title_size int default 100,
    subtitle_color text,
    subtitle_font text,
    subtitle_size int default 100,
    content_font text,
    content_size int default 100,
    headings_font text,
    headings_size int default 100,
    hue text,
    brightness text
);

create table pages (
    id serial primary key,
    site_id int not null references sites(id),
    name text not null,
    caret_pos int not null default 0,
    scroll_pos int not null default 0,
    deleted boolean not null default false,
    unique (site_id, name),
    created timestamp not null default (current_timestamp at time zone 'utc')
);

create table revisions (
    id serial primary key,
    page_id int not null references pages(id),
    revision int not null,
    content text not null,
    changes text,
    ip text,
    created timestamp not null default (current_timestamp at time zone 'utc')
);

create table drafts (
    id serial primary key,
    page_id int not null references pages(id),
    content text not null,
    created timestamp not null default (current_timestamp at time zone 'utc')
);

create index sites_secret_url_idx on sites (secret_url);
create index sites_public_url_idx on sites (public_url);
create index pages_site_id_idx on pages (site_id);
create index revision_page_id_idx on revisions (page_id);
create index designs_site_id_idx on designs (site_id);
