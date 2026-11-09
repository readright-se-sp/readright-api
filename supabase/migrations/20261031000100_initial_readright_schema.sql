create type public.passage_status as enum ('draft', 'published', 'retired');
create type public.session_status as enum (
  'assigned', 'reading', 'processing', 'comprehension', 'completed', 'failed'
);
create type public.media_kind as enum ('audio', 'video');
create type public.analysis_status as enum (
  'pending', 'running', 'partial', 'completed', 'failed'
);
create type public.reading_event_type as enum (
  'correct', 'mispronunciation', 'substitution', 'omission', 'insertion',
  'repetition', 'refusal_to_pronounce', 'unassessable'
);
create type public.behavior_type as enum (
  'finger_pointing', 'loss_of_place', 'monotone_reading',
  'word_by_word_reading', 'inaudible_reading'
);
create type public.behavior_outcome as enum (
  'detected', 'not_detected', 'not_assessable'
);
create type public.attempt_status as enum ('in_progress', 'submitted', 'abandoned');
create type public.service_kind as enum ('asr', 'vision', 'prosody', 'pronunciation');
create type public.service_job_status as enum (
  'pending', 'dispatching', 'running', 'succeeded', 'failed', 'timed_out', 'cancelled'
);
create type public.phoneme_outcome as enum (
  'correct', 'substitution', 'omission', 'insertion', 'unassessable'
);

-- auth.users is managed by Supabase Auth.
create table public.grade_levels (
  grade_id smallint primary key,
  label text not null unique,
  sequence smallint not null unique check (sequence > 0)
);

create table public.learners (
  user_id uuid primary key references auth.users(id) on delete cascade,
  current_grade_id smallint not null references public.grade_levels(grade_id),
  display_name text,
  created_at timestamptz not null default now()
);

create table public.passages (
  passage_id uuid primary key default gen_random_uuid(),
  title text not null,
  difficulty_grade_id smallint not null references public.grade_levels(grade_id),
  language_code text not null,
  content text not null,
  status public.passage_status not null default 'draft',
  created_at timestamptz not null default now(),
  published_at timestamptz,
  constraint passages_publication_time_check check (
    (status = 'draft' and published_at is null)
    or (status in ('published', 'retired') and published_at is not null)
  )
);
create index passages_grade_status_idx
  on public.passages (difficulty_grade_id, status);

create table public.passage_tokens (
  token_id uuid primary key default gen_random_uuid(),
  passage_id uuid not null references public.passages(passage_id) on delete cascade,
  position integer not null check (position > 0),
  token_text text not null,
  is_proper_noun boolean not null default false,
  unique (passage_id, position),
  unique (passage_id, token_id)
);

create table public.sessions (
  session_id uuid primary key default gen_random_uuid(),
  learner_id uuid not null references public.learners(user_id) on delete cascade,
  grade_at_assessment_id smallint not null references public.grade_levels(grade_id),
  passage_id uuid not null references public.passages(passage_id),
  assignment_policy_version text not null,
  status public.session_status not null default 'assigned',
  assigned_at timestamptz not null default now(),
  reading_started_at timestamptz,
  completed_at timestamptz,
  unique (session_id, passage_id),
  constraint sessions_completion_time_check check (
    (status = 'completed' and completed_at is not null)
    or (status <> 'completed' and completed_at is null)
  )
);
create index sessions_learner_assigned_idx
  on public.sessions (learner_id, assigned_at desc);
create index sessions_passage_idx on public.sessions (passage_id);

create table public.recordings (
  recording_id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(session_id) on delete cascade,
  kind public.media_kind not null,
  derived_from_recording_id uuid,
  storage_bucket text not null,
  storage_path text not null,
  content_type text not null,
  size_bytes bigint,
  sha256 text,
  duration_seconds numeric(10, 3),
  created_at timestamptz not null default now(),
  unique (storage_bucket, storage_path),
  unique (session_id, recording_id),
  constraint recordings_positive_metadata_check check (
    (size_bytes is null or size_bytes > 0)
    and (duration_seconds is null or duration_seconds > 0)
    and (sha256 is null or sha256 ~ '^[0-9a-f]{64}$')
  ),
  constraint recordings_source_same_session_fk
    foreign key (session_id, derived_from_recording_id)
    references public.recordings(session_id, recording_id)
);
create index recordings_session_idx on public.recordings (session_id);

create function public.validate_recording_derivation() returns trigger
language plpgsql as $$
declare
  source_kind public.media_kind;
begin
  if new.derived_from_recording_id is null then return new; end if;
  if new.recording_id = new.derived_from_recording_id then
    raise exception 'a recording cannot be derived from itself';
  end if;
  select kind into source_kind from public.recordings
    where session_id = new.session_id
      and recording_id = new.derived_from_recording_id;
  if new.kind <> 'audio' or source_kind <> 'video' then
    raise exception 'derived audio must reference a video recording in the same session';
  end if;
  return new;
end;
$$;
create trigger recordings_derivation_guard
  before insert or update on public.recordings
  for each row execute function public.validate_recording_derivation();

create table public.reading_analyses (
  analysis_id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(session_id) on delete cascade,
  source_recording_id uuid not null,
  run_number integer not null check (run_number > 0),
  status public.analysis_status not null default 'pending',
  is_selected boolean not null default false,
  pipeline_version text not null,
  scoring_policy_version text not null,
  transcript text,
  reading_duration_seconds numeric(10, 3),
  wpm numeric(7, 2),
  word_recognition_pct numeric(5, 2),
  reading_level text,
  failure_code text,
  created_at timestamptz not null default now(),
  finished_at timestamptz,
  unique (session_id, run_number),
  unique (session_id, analysis_id),
  constraint analyses_selected_status_check check (
    not is_selected or status in ('partial', 'completed')
  ),
  constraint analyses_source_same_session_fk
    foreign key (session_id, source_recording_id)
    references public.recordings(session_id, recording_id),
  constraint analyses_score_range_check check (
    (reading_duration_seconds is null or reading_duration_seconds > 0)
    and (wpm is null or wpm >= 0)
    and (word_recognition_pct is null or word_recognition_pct between 0 and 100)
  )
);
create unique index reading_analyses_one_selected_per_session_idx
  on public.reading_analyses (session_id) where is_selected;
create index reading_analyses_source_recording_idx
  on public.reading_analyses (source_recording_id);

create function public.validate_analysis_source() returns trigger
language plpgsql as $$
declare
  source_kind public.media_kind;
begin
  select kind into source_kind from public.recordings
    where session_id = new.session_id and recording_id = new.source_recording_id;
  if source_kind <> 'audio' then
    raise exception 'reading analysis source recording must be audio';
  end if;
  return new;
end;
$$;
create trigger reading_analyses_audio_source_guard
  before insert or update of session_id, source_recording_id on public.reading_analyses
  for each row execute function public.validate_analysis_source();

create table public.service_jobs (
  service_job_id uuid primary key default gen_random_uuid(),
  session_id uuid not null,
  analysis_id uuid not null,
  input_recording_id uuid not null,
  kind public.service_kind not null,
  service_name text not null,
  attempt_number integer not null check (attempt_number > 0),
  is_current boolean not null default true,
  required_for_completion boolean not null,
  status public.service_job_status not null default 'pending',
  idempotency_key uuid not null unique default gen_random_uuid(),
  external_job_id text,
  request_schema_version text not null,
  result_schema_version text,
  model_version text,
  request_sha256 text not null check (request_sha256 ~ '^[0-9a-f]{64}$'),
  response_payload jsonb,
  failure_code text,
  failure_message text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  deadline_at timestamptz,
  lease_expires_at timestamptz,
  finished_at timestamptz,
  unique (analysis_id, kind, attempt_number),
  unique (analysis_id, service_job_id),
  unique (session_id, service_job_id),
  foreign key (session_id, analysis_id)
    references public.reading_analyses(session_id, analysis_id) on delete cascade,
  foreign key (session_id, input_recording_id)
    references public.recordings(session_id, recording_id),
  constraint service_job_finished_at_check check (
    (status in ('succeeded', 'failed', 'timed_out', 'cancelled') and finished_at is not null)
    or (status not in ('succeeded', 'failed', 'timed_out', 'cancelled'))
  )
);
create unique index service_jobs_one_current_per_kind_idx
  on public.service_jobs (analysis_id, kind) where is_current;
create unique index service_jobs_external_id_idx
  on public.service_jobs (service_name, external_job_id) where external_job_id is not null;
create index service_jobs_status_lease_idx
  on public.service_jobs (status, lease_expires_at);
create index service_jobs_input_recording_idx
  on public.service_jobs (input_recording_id);

create table public.reading_events (
  event_id uuid primary key default gen_random_uuid(),
  analysis_id uuid not null references public.reading_analyses(analysis_id) on delete cascade,
  source_service_job_id uuid,
  event_order integer not null check (event_order > 0),
  detected_type public.reading_event_type not null,
  expected_start_token_id uuid,
  expected_end_token_id uuid,
  heard_text text,
  audio_start_seconds numeric(10, 3),
  audio_end_seconds numeric(10, 3),
  confidence numeric(5, 4),
  reviewed_type public.reading_event_type,
  reviewer_id uuid references auth.users(id) on delete set null,
  reviewed_at timestamptz,
  review_note text,
  unique (analysis_id, event_order),
  unique (analysis_id, event_id),
  foreign key (analysis_id, source_service_job_id)
    references public.service_jobs(analysis_id, service_job_id),
  foreign key (expected_start_token_id)
    references public.passage_tokens(token_id),
  foreign key (expected_end_token_id)
    references public.passage_tokens(token_id),
  constraint reading_event_evidence_check check (
    (audio_start_seconds is null or audio_start_seconds >= 0)
    and (audio_end_seconds is null or audio_end_seconds >= 0)
    and (audio_start_seconds is null or audio_end_seconds is null
      or audio_end_seconds >= audio_start_seconds)
    and (confidence is null or confidence between 0 and 1)
  )
);
create index reading_events_start_token_idx
  on public.reading_events (expected_start_token_id);
create index reading_events_end_token_idx
  on public.reading_events (expected_end_token_id);
create index reading_events_reviewer_idx on public.reading_events (reviewer_id);
create index reading_events_service_job_idx
  on public.reading_events (source_service_job_id);

create function public.validate_reading_event_context() returns trigger
language plpgsql as $$
declare
  target_passage_id uuid;
  start_position integer;
  end_position integer;
begin
  select s.passage_id into target_passage_id
    from public.reading_analyses a
    join public.sessions s on s.session_id = a.session_id
    where a.analysis_id = new.analysis_id;

  if new.expected_start_token_id is not null then
    select position into start_position from public.passage_tokens
      where token_id = new.expected_start_token_id
        and passage_id = target_passage_id;
    if start_position is null then
      raise exception 'start token must belong to the analysis passage';
    end if;
  end if;
  if new.expected_end_token_id is not null then
    select position into end_position from public.passage_tokens
      where token_id = new.expected_end_token_id
        and passage_id = target_passage_id;
    if end_position is null then
      raise exception 'end token must belong to the analysis passage';
    end if;
  end if;
  if start_position is not null and end_position is not null
    and end_position < start_position then
    raise exception 'reading event end token must not precede its start token';
  end if;
  return new;
end;
$$;
create trigger reading_events_context_guard
  before insert or update on public.reading_events
  for each row execute function public.validate_reading_event_context();

create table public.behavior_observations (
  observation_id uuid primary key default gen_random_uuid(),
  analysis_id uuid not null references public.reading_analyses(analysis_id) on delete cascade,
  source_service_job_id uuid not null,
  type public.behavior_type not null,
  outcome public.behavior_outcome not null,
  confidence numeric(5, 4),
  evidence_note text,
  unique (analysis_id, type),
  foreign key (analysis_id, source_service_job_id)
    references public.service_jobs(analysis_id, service_job_id),
  constraint behavior_confidence_check check (
    confidence is null or confidence between 0 and 1
  )
);
create index behavior_observations_service_job_idx
  on public.behavior_observations (source_service_job_id);

create table public.phoneme_events (
  phoneme_event_id uuid primary key default gen_random_uuid(),
  analysis_id uuid not null,
  reading_event_id uuid not null,
  source_service_job_id uuid not null,
  alignment_position integer not null check (alignment_position > 0),
  expected_phoneme text,
  actual_phoneme text,
  notation text not null,
  outcome public.phoneme_outcome not null,
  audio_start_seconds numeric(10, 3),
  audio_end_seconds numeric(10, 3),
  confidence numeric(5, 4),
  unique (reading_event_id, alignment_position),
  foreign key (analysis_id, reading_event_id)
    references public.reading_events(analysis_id, event_id) on delete cascade,
  foreign key (analysis_id, source_service_job_id)
    references public.service_jobs(analysis_id, service_job_id),
  constraint phoneme_evidence_check check (
    (audio_start_seconds is null or audio_start_seconds >= 0)
    and (audio_end_seconds is null or audio_end_seconds >= 0)
    and (audio_start_seconds is null or audio_end_seconds is null
      or audio_end_seconds >= audio_start_seconds)
    and (confidence is null or confidence between 0 and 1)
  )
);
create index phoneme_events_service_job_idx
  on public.phoneme_events (source_service_job_id);

create table public.comprehension_questions (
  question_id uuid primary key default gen_random_uuid(),
  passage_id uuid not null references public.passages(passage_id) on delete cascade,
  question_order integer not null check (question_order > 0),
  prompt text not null,
  points_possible numeric(7, 2) not null default 1 check (points_possible > 0),
  unique (passage_id, question_order),
  unique (passage_id, question_id)
);

create table public.question_choices (
  choice_id uuid primary key default gen_random_uuid(),
  question_id uuid not null
    references public.comprehension_questions(question_id) on delete cascade,
  choice_order integer not null check (choice_order > 0),
  choice_text text not null,
  is_correct boolean not null default false,
  unique (question_id, choice_order),
  unique (question_id, choice_id)
);

create table public.comprehension_attempts (
  attempt_id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(session_id) on delete cascade,
  attempt_number integer not null check (attempt_number > 0),
  status public.attempt_status not null default 'in_progress',
  started_at timestamptz not null default now(),
  submitted_at timestamptz,
  score_earned numeric(8, 2),
  score_possible numeric(8, 2),
  unique (session_id, attempt_number),
  unique (session_id, attempt_id),
  constraint comprehension_attempt_score_check check (
    (score_earned is null and score_possible is null)
    or (score_earned >= 0 and score_possible > 0 and score_earned <= score_possible)
  ),
  constraint comprehension_attempt_submission_check check (
    (status = 'submitted' and submitted_at is not null
      and score_earned is not null and score_possible is not null)
    or (status <> 'submitted' and submitted_at is null)
  )
);
create unique index comprehension_attempts_one_active_idx
  on public.comprehension_attempts (session_id) where status = 'in_progress';

create table public.comprehension_answers (
  answer_id uuid primary key default gen_random_uuid(),
  attempt_id uuid not null references public.comprehension_attempts(attempt_id) on delete cascade,
  question_id uuid not null
    references public.comprehension_questions(question_id) on delete cascade,
  selected_choice_id uuid,
  answered_at timestamptz,
  unique (attempt_id, question_id),
  foreign key (question_id, selected_choice_id)
    references public.question_choices(question_id, choice_id),
  constraint comprehension_answer_time_check check (
    (selected_choice_id is null and answered_at is null)
    or (selected_choice_id is not null and answered_at is not null)
  )
);
create index comprehension_answers_question_idx
  on public.comprehension_answers (question_id);
create index comprehension_answers_choice_idx
  on public.comprehension_answers (selected_choice_id);

-- Published passage content and its assessment items are immutable. Build in draft,
-- then publish after inserting tokens, questions, and choices.
create function public.guard_passage_update() returns trigger
language plpgsql as $$
begin
  if old.status in ('published', 'retired') and (
    (old.status = 'published' and new.status not in ('published', 'retired'))
    or (old.status = 'retired' and new.status <> 'retired')
    or new.title is distinct from old.title
    or new.difficulty_grade_id is distinct from old.difficulty_grade_id
    or new.language_code is distinct from old.language_code
    or new.content is distinct from old.content
    or new.published_at is distinct from old.published_at
    or new.created_at is distinct from old.created_at
  ) then
    raise exception 'published or retired passage content is immutable';
  end if;
  return new;
end;
$$;
create trigger passages_update_guard
  before update on public.passages
  for each row execute function public.guard_passage_update();

create function public.guard_passage_delete() returns trigger
language plpgsql as $$
begin
  if old.status in ('published', 'retired') then
    raise exception 'published or retired passages cannot be deleted';
  end if;
  return old;
end;
$$;
create trigger passages_delete_guard
  before delete on public.passages
  for each row execute function public.guard_passage_delete();

create function public.guard_published_passage_children() returns trigger
language plpgsql as $$
declare
  old_passage_id uuid;
  new_passage_id uuid;
  target_passage_id uuid;
  target_status public.passage_status;
begin
  if tg_op in ('UPDATE', 'DELETE') then
    if tg_table_name = 'question_choices' then
      select passage_id into old_passage_id
        from public.comprehension_questions where question_id = old.question_id;
    else
      old_passage_id := old.passage_id;
    end if;
  end if;
  if tg_op in ('INSERT', 'UPDATE') then
    if tg_table_name = 'question_choices' then
      select passage_id into new_passage_id
        from public.comprehension_questions where question_id = new.question_id;
    else
      new_passage_id := new.passage_id;
    end if;
  end if;

  foreach target_passage_id in array array[old_passage_id, new_passage_id] loop
    if target_passage_id is not null then
      select status into target_status
        from public.passages where passage_id = target_passage_id;
      if target_status in ('published', 'retired') then
        raise exception 'published passage assessment content is immutable';
      end if;
    end if;
  end loop;

  if tg_op = 'DELETE' then return old; end if;
  return new;
end;
$$;
create trigger passage_tokens_update_guard
  before insert or update or delete on public.passage_tokens
  for each row execute function public.guard_published_passage_children();
create trigger comprehension_questions_update_guard
  before insert or update or delete on public.comprehension_questions
  for each row execute function public.guard_published_passage_children();
create trigger question_choices_update_guard
  before insert or update or delete on public.question_choices
  for each row execute function public.guard_published_passage_children();

create function public.validate_passage_before_publish() returns trigger
language plpgsql as $$
declare
  question_row record;
  choice_count integer;
  correct_count integer;
begin
  if new.status <> 'published' or (tg_op = 'UPDATE' and old.status = 'published') then
    return new;
  end if;
  if not exists (
    select 1 from public.passage_tokens where passage_id = new.passage_id
  ) then
    raise exception 'a published passage must have tokens';
  end if;
  if not exists (
    select 1 from public.comprehension_questions where passage_id = new.passage_id
  ) then
    raise exception 'a published passage must have questions';
  end if;

  for question_row in
    select question_id from public.comprehension_questions
    where passage_id = new.passage_id
  loop
    select count(*), count(*) filter (where is_correct)
      into choice_count, correct_count
      from public.question_choices where question_id = question_row.question_id;
    if choice_count < 2 or correct_count <> 1 then
      raise exception 'each published question needs two choices and one correct answer';
    end if;
  end loop;
  return new;
end;
$$;
create trigger passages_publish_validation
  before insert or update of status on public.passages
  for each row execute function public.validate_passage_before_publish();

create function public.guard_comprehension_attempt_transition() returns trigger
language plpgsql as $$
begin
  if old.status in ('submitted', 'abandoned') then
    raise exception 'submitted or abandoned attempts are immutable';
  end if;
  if old.status = 'in_progress'
    and new.status not in ('in_progress', 'submitted', 'abandoned') then
    raise exception 'invalid comprehension attempt status transition';
  end if;
  return new;
end;
$$;
create trigger comprehension_attempt_transition_guard
  before update on public.comprehension_attempts
  for each row execute function public.guard_comprehension_attempt_transition();

create function public.guard_comprehension_answer_write() returns trigger
language plpgsql as $$
declare
  target_status public.attempt_status;
  old_attempt_status public.attempt_status;
  target_passage_id uuid;
  question_passage_id uuid;
begin
  if tg_op in ('UPDATE', 'DELETE') then
    select status into old_attempt_status from public.comprehension_attempts
      where attempt_id = old.attempt_id;
    if old_attempt_status is distinct from 'in_progress' then
      raise exception 'answers can only change during an in-progress attempt';
    end if;
  end if;
  if tg_op in ('INSERT', 'UPDATE') then
    select a.status, s.passage_id into target_status, target_passage_id
      from public.comprehension_attempts a
      join public.sessions s on s.session_id = a.session_id
      where a.attempt_id = new.attempt_id;
    if target_status is distinct from 'in_progress' then
      raise exception 'answers can only change during an in-progress attempt';
    end if;
    select passage_id into question_passage_id
      from public.comprehension_questions where question_id = new.question_id;
    if question_passage_id is distinct from target_passage_id then
      raise exception 'answer question must belong to the attempt passage';
    end if;
  end if;
  if tg_op = 'DELETE' then return old; end if;
  return new;
end;
$$;
create trigger comprehension_answers_write_guard
  before insert or update or delete on public.comprehension_answers
  for each row execute function public.guard_comprehension_answer_write();

-- Dashboard aggregation is read by the authenticated backend using service_role.
create view public.learner_dashboard_summary
with (security_invoker = true) as
select
  l.user_id as learner_id,
  l.display_name,
  g.grade_id,
  g.label as grade_label,
  count(s.session_id)::integer as sessions_total,
  count(s.session_id) filter (where s.status = 'completed')::integer
    as sessions_completed,
  count(s.session_id) filter (
    where s.status in ('assigned', 'reading', 'processing', 'comprehension')
  )::integer as sessions_in_progress,
  round(avg(a.wpm) filter (where a.status = 'completed'), 2)
    as average_wpm,
  round(avg(a.word_recognition_pct) filter (where a.status = 'completed'), 2)
    as average_word_recognition_pct
from public.learners l
join public.grade_levels g on g.grade_id = l.current_grade_id
left join public.sessions s on s.learner_id = l.user_id
left join public.reading_analyses a
  on a.session_id = s.session_id and a.is_selected
group by l.user_id, l.display_name, g.grade_id, g.label;

-- The backend uses a server-only service key and scopes every request to the
-- user ID returned by Supabase Auth. Frontend tokens never receive table grants.
alter table public.grade_levels enable row level security;
alter table public.learners enable row level security;
alter table public.passages enable row level security;
alter table public.passage_tokens enable row level security;
alter table public.sessions enable row level security;
alter table public.recordings enable row level security;
alter table public.reading_analyses enable row level security;
alter table public.service_jobs enable row level security;
alter table public.reading_events enable row level security;
alter table public.behavior_observations enable row level security;
alter table public.phoneme_events enable row level security;
alter table public.comprehension_questions enable row level security;
alter table public.question_choices enable row level security;
alter table public.comprehension_attempts enable row level security;
alter table public.comprehension_answers enable row level security;

grant usage on schema public to service_role;
grant select, insert, update, delete on table
  public.grade_levels,
  public.learners,
  public.passages,
  public.passage_tokens,
  public.sessions,
  public.recordings,
  public.reading_analyses,
  public.service_jobs,
  public.reading_events,
  public.behavior_observations,
  public.phoneme_events,
  public.comprehension_questions,
  public.question_choices,
  public.comprehension_attempts,
  public.comprehension_answers
to service_role;
grant select on public.learner_dashboard_summary to service_role;
revoke all on table
  public.grade_levels,
  public.learners,
  public.passages,
  public.passage_tokens,
  public.sessions,
  public.recordings,
  public.reading_analyses,
  public.service_jobs,
  public.reading_events,
  public.behavior_observations,
  public.phoneme_events,
  public.comprehension_questions,
  public.question_choices,
  public.comprehension_attempts,
  public.comprehension_answers
from anon, authenticated;
revoke all on public.learner_dashboard_summary from anon, authenticated;
