-- Persist the consolidated ReadRight MAI result without losing fields from
-- the MAI 1.1.0 contract. Keep the old service categories for existing jobs.

ALTER TYPE public.service_kind ADD VALUE IF NOT EXISTS 'mai';

ALTER TYPE public.reading_event_type ADD VALUE IF NOT EXISTS 'transposition';
ALTER TYPE public.reading_event_type ADD VALUE IF NOT EXISTS 'reversal';
ALTER TYPE public.reading_event_type ADD VALUE IF NOT EXISTS 'self_correction';

ALTER TYPE public.behavior_type ADD VALUE IF NOT EXISTS 'disregard_punctuation';
ALTER TYPE public.behavior_type ADD VALUE IF NOT EXISTS 'lack_expression';

ALTER TABLE public.reading_analyses
  ADD COLUMN reading_score numeric,
  ALTER COLUMN wpm TYPE numeric;

COMMENT ON COLUMN public.reading_analyses.reading_score IS
  'MAI overall reading score. Kept separate from word_recognition_pct; range is not constrained until the MAI scoring scale is finalized.';

ALTER TABLE public.reading_events
  ADD COLUMN actual_phrase text,
  ADD COLUMN spoken_phrase text,
  ADD COLUMN actual_phonemes text[],
  ADD COLUMN spoken_phonemes text[],
  ADD COLUMN read_start_ms integer,
  ADD COLUMN read_end_ms integer,
  ADD COLUMN audio_object_key text,
  ADD CONSTRAINT reading_events_mai_offsets_check CHECK (
    (read_start_ms IS NULL OR read_start_ms >= 0)
    AND (read_end_ms IS NULL OR read_end_ms >= 0)
    AND (read_start_ms IS NULL OR read_end_ms IS NULL OR read_end_ms >= read_start_ms)
  );

COMMENT ON COLUMN public.reading_events.actual_phrase IS
  'The expected word or phrase returned by MAI.';
COMMENT ON COLUMN public.reading_events.spoken_phrase IS
  'The word or phrase MAI reports as spoken; empty string represents an omission.';
COMMENT ON COLUMN public.reading_events.actual_phonemes IS
  'The exact ordered phoneme array returned by MAI for the expected phrase.';
COMMENT ON COLUMN public.reading_events.spoken_phonemes IS
  'The exact ordered phoneme array returned by MAI for the spoken phrase.';
COMMENT ON COLUMN public.reading_events.read_start_ms IS
  'The exact MAI miscue start offset in milliseconds.';
COMMENT ON COLUMN public.reading_events.read_end_ms IS
  'The exact MAI miscue end offset in milliseconds.';
COMMENT ON COLUMN public.reading_events.audio_object_key IS
  'S3 object key for the MAI clip belonging to this miscue; the backend stores the key but does not read the object.';

-- MAI analyzes the original webm (audio and video together). Preserve the
-- existing source-recording FK while allowing either source media kind.
CREATE OR REPLACE FUNCTION public.validate_analysis_source() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  source_kind public.media_kind;
BEGIN
  SELECT kind INTO source_kind
  FROM public.recordings
  WHERE session_id = new.session_id
    AND recording_id = new.source_recording_id;

  IF source_kind IS NULL OR source_kind NOT IN ('audio', 'video') THEN
    RAISE EXCEPTION 'reading analysis source recording must be audio or video';
  END IF;

  RETURN new;
END;
$$;

-- Claim one logical MAI request before making the network call. The request ID
-- is also the reading_analyses.analysis_id, so retries reuse one service job.
CREATE OR REPLACE FUNCTION public.start_mai_analysis(
  p_request_id uuid,
  p_request_sha256 text,
  p_request jsonb,
  p_service_name text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  analysis_row record;
  job_row public.service_jobs%ROWTYPE;
  next_attempt integer;
BEGIN
  SELECT a.session_id, a.source_recording_id, a.status, a.is_selected,
         r.kind AS recording_kind, p.title AS passage_title,
         p.content AS passage_content
    INTO analysis_row
    FROM public.reading_analyses AS a
    JOIN public.sessions AS s ON s.session_id = a.session_id
    JOIN public.passages AS p ON p.passage_id = s.passage_id
    JOIN public.recordings AS r
      ON r.session_id = a.session_id
     AND r.recording_id = a.source_recording_id
   WHERE a.analysis_id = p_request_id
   FOR UPDATE OF a;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'MAI analysis request does not match a reading analysis';
  END IF;
  IF p_request->>'request_id' IS DISTINCT FROM p_request_id::text THEN
    RAISE EXCEPTION 'MAI request_id does not match the reading analysis';
  END IF;
  IF analysis_row.recording_kind <> 'video' THEN
    RAISE EXCEPTION 'MAI requires the analysis source recording to be video';
  END IF;
  IF p_request->>'passage_title' IS DISTINCT FROM analysis_row.passage_title
     OR p_request->>'passage_content' IS DISTINCT FROM analysis_row.passage_content THEN
    RAISE EXCEPTION 'MAI request passage does not match the analysis passage';
  END IF;

  SELECT * INTO job_row
    FROM public.service_jobs
   WHERE idempotency_key = p_request_id
   FOR UPDATE;

  IF FOUND THEN
    IF job_row.analysis_id <> p_request_id
       OR job_row.kind <> 'mai'
       OR job_row.request_sha256 <> p_request_sha256 THEN
      RAISE EXCEPTION 'MAI request ID was already used for a different request';
    END IF;
    IF job_row.status = 'succeeded' AND job_row.response_payload IS NOT NULL THEN
      RETURN jsonb_build_object('state', 'completed', 'response', job_row.response_payload);
    END IF;
    IF job_row.status IN ('pending', 'dispatching', 'running')
       AND job_row.lease_expires_at > now() THEN
      RETURN jsonb_build_object('state', 'in_progress');
    END IF;

    IF analysis_row.is_selected THEN
      RAISE EXCEPTION 'selected analysis cannot be rerun through MAI';
    END IF;
    IF EXISTS (
      SELECT 1 FROM public.reading_events WHERE analysis_id = p_request_id
    ) OR EXISTS (
      SELECT 1 FROM public.behavior_observations WHERE analysis_id = p_request_id
    ) OR EXISTS (
      SELECT 1 FROM public.service_jobs
       WHERE analysis_id = p_request_id AND kind <> 'mai'
    ) THEN
      RAISE EXCEPTION 'MAI requires a fresh analysis without other service results';
    END IF;

    UPDATE public.service_jobs
       SET status = 'running',
           service_name = p_service_name,
           started_at = now(),
           deadline_at = now() + interval '120 seconds',
           lease_expires_at = now() + interval '150 seconds',
           finished_at = NULL,
           response_payload = NULL,
           failure_code = NULL,
           failure_message = NULL
     WHERE service_job_id = job_row.service_job_id;
  ELSE
    IF analysis_row.is_selected THEN
      RAISE EXCEPTION 'selected analysis cannot be rerun through MAI';
    END IF;
    IF EXISTS (
      SELECT 1 FROM public.reading_events WHERE analysis_id = p_request_id
    ) OR EXISTS (
      SELECT 1 FROM public.behavior_observations WHERE analysis_id = p_request_id
    ) OR EXISTS (
      SELECT 1 FROM public.service_jobs
       WHERE analysis_id = p_request_id AND kind <> 'mai'
    ) THEN
      RAISE EXCEPTION 'MAI requires a fresh analysis without other service results';
    END IF;

    SELECT coalesce(max(attempt_number), 0) + 1 INTO next_attempt
      FROM public.service_jobs
     WHERE analysis_id = p_request_id AND kind = 'mai';

    INSERT INTO public.service_jobs (
      session_id, analysis_id, input_recording_id, kind, service_name,
      attempt_number, required_for_completion, status, idempotency_key,
      request_schema_version, request_sha256, started_at, deadline_at,
      lease_expires_at
    ) VALUES (
      analysis_row.session_id, p_request_id, analysis_row.source_recording_id,
      'mai', p_service_name, next_attempt, true, 'running', p_request_id,
      '1.1.0', p_request_sha256, now(), now() + interval '120 seconds',
      now() + interval '150 seconds'
    ) RETURNING * INTO job_row;
  END IF;

  UPDATE public.reading_analyses
     SET status = 'running', failure_code = NULL, finished_at = NULL
   WHERE analysis_id = p_request_id AND NOT is_selected;

  RETURN jsonb_build_object(
    'state', 'started',
    'service_job_id', job_row.service_job_id,
    'session_id', analysis_row.session_id,
    'source_recording_id', analysis_row.source_recording_id
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.complete_mai_analysis(
  p_request_id uuid,
  p_response jsonb
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  job_row public.service_jobs%ROWTYPE;
  miscue jsonb;
  observation record;
  event_order integer := 0;
  reading_type text;
  actual_phones text[];
  spoken_phones text[];
  start_ms integer;
  end_ms integer;
BEGIN
  SELECT * INTO job_row
    FROM public.service_jobs
   WHERE idempotency_key = p_request_id AND kind = 'mai'
   FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'MAI service job not found';
  END IF;
  IF job_row.status = 'succeeded' AND job_row.response_payload IS NOT NULL THEN
    RETURN job_row.response_payload;
  END IF;
  IF p_response->>'request_id' IS DISTINCT FROM p_request_id::text THEN
    RAISE EXCEPTION 'MAI response request_id does not match';
  END IF;

  FOR miscue IN SELECT value FROM jsonb_array_elements(p_response->'miscues') LOOP
    event_order := event_order + 1;
    reading_type := replace(miscue->>'miscue_type', '-', '_');
    actual_phones := ARRAY(
      SELECT value FROM jsonb_array_elements_text(miscue->'actual_phoneme')
    );
    spoken_phones := ARRAY(
      SELECT value FROM jsonb_array_elements_text(miscue->'spoken_phoneme')
    );
    start_ms := (miscue->>'read_start')::integer;
    end_ms := (miscue->>'read_end')::integer;

    INSERT INTO public.reading_events (
      analysis_id, source_service_job_id, event_order, detected_type,
      actual_phrase, spoken_phrase, heard_text, actual_phonemes,
      spoken_phonemes, read_start_ms, read_end_ms, audio_start_seconds,
      audio_end_seconds, audio_object_key
    ) VALUES (
      p_request_id, job_row.service_job_id, event_order,
      reading_type::public.reading_event_type,
      miscue->>'actual_phrase', miscue->>'spoken_phrase',
      miscue->>'spoken_phrase', actual_phones, spoken_phones, start_ms, end_ms,
      start_ms::numeric / 1000, end_ms::numeric / 1000,
      miscue->>'audio_object_key'
    );
  END LOOP;

  FOR observation IN
    SELECT * FROM (VALUES
      ('finger_pointing', 'is_finger_pointing'),
      ('word_by_word_reading', 'is_word_by_word'),
      ('monotone_reading', 'is_monotonous'),
      ('disregard_punctuation', 'is_disregard_punctuation'),
      ('lack_expression', 'is_lack_expression'),
      ('inaudible_reading', 'is_hardly_audible')
    ) AS flags(type_name, response_name)
  LOOP
    INSERT INTO public.behavior_observations (
      analysis_id, source_service_job_id, type, outcome
    ) VALUES (
      p_request_id, job_row.service_job_id,
      observation.type_name::public.behavior_type,
      CASE WHEN (p_response->>observation.response_name)::boolean
        THEN 'detected'::public.behavior_outcome
        ELSE 'not_detected'::public.behavior_outcome
      END
    );
  END LOOP;

  UPDATE public.reading_analyses AS a
     SET status = 'completed',
         reading_score = (p_response->>'reading_score')::numeric,
         wpm = (p_response->>'wpm')::numeric,
         reading_duration_seconds = coalesce(
           (
             SELECT r.duration_seconds
               FROM public.recordings AS r
              WHERE r.recording_id = a.source_recording_id
           ),
           a.reading_duration_seconds
         ),
         finished_at = now(),
         failure_code = NULL
   WHERE a.analysis_id = p_request_id;

  UPDATE public.service_jobs
     SET status = 'succeeded',
         result_schema_version = '1.1.0',
         response_payload = p_response,
         finished_at = now(),
         lease_expires_at = NULL,
         failure_code = NULL,
         failure_message = NULL
   WHERE service_job_id = job_row.service_job_id;

  RETURN p_response;
END;
$$;

CREATE OR REPLACE FUNCTION public.fail_mai_analysis(
  p_request_id uuid,
  p_status public.service_job_status,
  p_failure_code text,
  p_failure_message text
) RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  IF p_status NOT IN ('failed', 'timed_out') THEN
    RAISE EXCEPTION 'invalid MAI failure status';
  END IF;

  UPDATE public.service_jobs
     SET status = p_status,
         failure_code = p_failure_code,
         failure_message = left(p_failure_message, 2000),
         finished_at = now(),
         lease_expires_at = NULL
   WHERE idempotency_key = p_request_id AND kind = 'mai';

  UPDATE public.reading_analyses
     SET status = 'failed', failure_code = p_failure_code, finished_at = now()
   WHERE analysis_id = p_request_id AND NOT is_selected;
END;
$$;

REVOKE ALL ON FUNCTION public.start_mai_analysis(uuid, text, jsonb, text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.complete_mai_analysis(uuid, jsonb) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.fail_mai_analysis(uuid, public.service_job_status, text, text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.start_mai_analysis(uuid, text, jsonb, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.complete_mai_analysis(uuid, jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION public.fail_mai_analysis(uuid, public.service_job_status, text, text) TO service_role;
