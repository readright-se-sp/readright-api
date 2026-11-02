-- Prepare a video-backed reading analysis before invoking the MAI pipeline.
-- The recording, analysis, and session state change are one transaction.
CREATE OR REPLACE FUNCTION public.prepare_mai_reading_run(
  p_learner_id uuid,
  p_session_id uuid,
  p_storage_bucket text,
  p_storage_path text,
  p_content_type text,
  p_size_bytes bigint,
  p_duration_seconds numeric,
  p_pipeline_version text,
  p_scoring_policy_version text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  target_session public.sessions%ROWTYPE;
  passage public.passages%ROWTYPE;
  video_recording_id uuid;
  new_analysis_id uuid;
  next_run_number integer;
  started_at timestamptz := now();
BEGIN
  SELECT * INTO target_session
    FROM public.sessions
   WHERE session_id = p_session_id
     AND learner_id = p_learner_id
   FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'session not found';
  END IF;
  IF target_session.status NOT IN ('assigned', 'reading') THEN
    RAISE EXCEPTION 'session is not ready for a recording';
  END IF;
  IF p_size_bytes <= 0 OR p_duration_seconds <= 0
     OR p_storage_bucket IS NULL OR p_storage_bucket = ''
     OR p_storage_path IS NULL OR p_storage_path = ''
     OR p_content_type IS NULL OR p_content_type = '' THEN
    RAISE EXCEPTION 'recording metadata is invalid';
  END IF;

  SELECT * INTO passage
    FROM public.passages
   WHERE passage_id = target_session.passage_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'session passage not found';
  END IF;

  INSERT INTO public.recordings (
    session_id, kind, storage_bucket, storage_path, content_type,
    size_bytes, duration_seconds
  ) VALUES (
    p_session_id, 'video', p_storage_bucket, p_storage_path, p_content_type,
    p_size_bytes, p_duration_seconds
  ) RETURNING recording_id INTO video_recording_id;

  SELECT coalesce(max(run_number), 0) + 1 INTO next_run_number
    FROM public.reading_analyses
   WHERE session_id = p_session_id;

  INSERT INTO public.reading_analyses (
    session_id, source_recording_id, run_number, status, is_selected,
    pipeline_version, scoring_policy_version, reading_duration_seconds
  ) VALUES (
    p_session_id, video_recording_id, next_run_number, 'pending', false,
    p_pipeline_version, p_scoring_policy_version, p_duration_seconds
  ) RETURNING analysis_id INTO new_analysis_id;

  UPDATE public.sessions
     SET status = 'processing',
         session_timestamp = started_at - p_duration_seconds * interval '1 second',
         processing_started_at = started_at
   WHERE session_id = p_session_id;

  RETURN jsonb_build_object(
    'session_id', p_session_id,
    'passage_id', passage.passage_id,
    'passage_title', passage.title,
    'passage_content', passage.content,
    'recording_id', video_recording_id,
    'analysis_id', new_analysis_id,
    'run_number', next_run_number
  );
END;
$$;

REVOKE ALL ON FUNCTION public.prepare_mai_reading_run(
  uuid, uuid, text, text, text, bigint, numeric, text, text
) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.prepare_mai_reading_run(
  uuid, uuid, text, text, text, bigint, numeric, text, text
) TO service_role;

-- A completed MAI result is the learner-facing result for this run. Select it
-- atomically with completion so /result and the dashboard can read it.
CREATE OR REPLACE FUNCTION public.select_completed_mai_analysis()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  IF EXISTS (
    SELECT 1
      FROM public.service_jobs
     WHERE analysis_id = NEW.analysis_id
       AND kind = 'mai'
  ) THEN
    UPDATE public.reading_analyses
       SET is_selected = false
     WHERE session_id = NEW.session_id
       AND is_selected
       AND analysis_id <> NEW.analysis_id;

    UPDATE public.reading_analyses
       SET is_selected = true
     WHERE analysis_id = NEW.analysis_id
       AND NOT is_selected;
  END IF;
  RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION public.select_completed_mai_analysis()
  FROM PUBLIC, anon, authenticated;

CREATE TRIGGER reading_analyses_select_mai_after_completion
  AFTER UPDATE OF status ON public.reading_analyses
  FOR EACH ROW
  WHEN (NEW.status = 'completed')
  EXECUTE FUNCTION public.select_completed_mai_analysis();
