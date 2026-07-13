alter table persons
add column if not exists offboarded_at date;

alter table persons
add column if not exists offboarding_note text;
