ALTER TABLE public.sessions
  ADD COLUMN processing_started_at timestamptz;

CREATE INDEX sessions_processing_timeout_idx
  ON public.sessions (processing_started_at)
  WHERE status = 'processing';

CREATE INDEX sessions_comprehension_timeout_idx
  ON public.sessions (processing_started_at)
  WHERE status = 'comprehension';

-- Serialize assignment requests per learner and passage grade. This makes
-- React StrictMode's duplicate page-load requests return the same assigned
-- session even when both requests reach Postgres at the same time.
CREATE OR REPLACE FUNCTION public.assign_learner_session(
  p_learner_id uuid,
  p_passage_grade_id smallint,
  p_assignment_policy_version text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  learner_grade_id smallint;
  result jsonb;
  chosen_passage public.passages%ROWTYPE;
  created_session public.sessions%ROWTYPE;
BEGIN
  PERFORM pg_advisory_xact_lock(
    hashtextextended(p_learner_id::text || ':' || p_passage_grade_id::text, 0)
  );

  SELECT current_grade_id INTO learner_grade_id
    FROM public.learners
   WHERE user_id = p_learner_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'learner profile not found';
  END IF;

  SELECT jsonb_build_object(
    'session_id', s.session_id,
    'passage_id', p.passage_id,
    'title', p.title,
    'content', p.content,
    'status', s.status
  ) INTO result
    FROM public.sessions s
    JOIN public.passages p ON p.passage_id = s.passage_id
   WHERE s.learner_id = p_learner_id
     AND s.status = 'assigned'
     AND p.difficulty_grade_id = p_passage_grade_id
   ORDER BY s.assigned_at DESC
   LIMIT 1;
  IF result IS NOT NULL THEN
    RETURN result;
  END IF;

  SELECT p.* INTO chosen_passage
    FROM public.passages p
   WHERE p.difficulty_grade_id = p_passage_grade_id
     AND p.status = 'published'
   ORDER BY EXISTS (
     SELECT 1
       FROM public.sessions prior
      WHERE prior.learner_id = p_learner_id
        AND prior.passage_id = p.passage_id
        AND prior.session_timestamp IS NOT NULL
   ), random()
   LIMIT 1;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'no published passage for grade';
  END IF;

  INSERT INTO public.sessions (
    learner_id,
    grade_at_assessment_id,
    passage_id,
    assignment_policy_version,
    status
  ) VALUES (
    p_learner_id,
    learner_grade_id,
    chosen_passage.passage_id,
    p_assignment_policy_version,
    'assigned'
  ) RETURNING * INTO created_session;

  RETURN jsonb_build_object(
    'session_id', created_session.session_id,
    'passage_id', chosen_passage.passage_id,
    'title', chosen_passage.title,
    'content', chosen_passage.content,
    'status', created_session.status
  );
END;
$$;

-- Resolve frontend option positions and score answers in one transaction.
-- The caller supplies choice IDs only after translating the zero-based option
-- position against the same ordered choice list returned to the browser.
CREATE OR REPLACE FUNCTION public.submit_learner_comprehension(
  p_session_id uuid,
  p_learner_id uuid,
  p_answers jsonb
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  passage_id uuid;
  target_attempt public.comprehension_attempts%ROWTYPE;
  answer_item jsonb;
  target_question public.comprehension_questions%ROWTYPE;
  selected_choice_id uuid;
  selected_is_correct boolean;
  question_count integer;
  distinct_answer_count integer;
  earned numeric(8, 2) := 0;
  possible numeric(8, 2) := 0;
BEGIN
  SELECT s.passage_id INTO passage_id
    FROM public.sessions s
   WHERE s.session_id = p_session_id
     AND s.learner_id = p_learner_id
   FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'session not found';
  END IF;

  SELECT count(*)::integer INTO question_count
    FROM public.comprehension_questions q
   WHERE q.passage_id = passage_id;
  IF question_count = 0 OR jsonb_typeof(p_answers) <> 'array'
     OR jsonb_array_length(p_answers) <> question_count THEN
    RAISE EXCEPTION 'answer count does not match passage questions';
  END IF;

  SELECT count(DISTINCT value->>'question_id')::integer INTO distinct_answer_count
    FROM jsonb_array_elements(p_answers) AS answers(value);
  IF distinct_answer_count <> question_count THEN
    RAISE EXCEPTION 'answers must contain each passage question exactly once';
  END IF;

  SELECT * INTO target_attempt
    FROM public.comprehension_attempts
   WHERE session_id = p_session_id AND attempt_number = 1
   FOR UPDATE;
  IF FOUND AND target_attempt.status = 'submitted' THEN
    RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'attempt already submitted';
  END IF;
  IF FOUND AND target_attempt.status <> 'in_progress' THEN
    RAISE EXCEPTION 'comprehension attempt is not editable';
  END IF;
  IF NOT FOUND THEN
    INSERT INTO public.comprehension_attempts (session_id, attempt_number)
    VALUES (p_session_id, 1)
    RETURNING * INTO target_attempt;
  ELSE
    DELETE FROM public.comprehension_answers
     WHERE attempt_id = target_attempt.attempt_id;
  END IF;

  FOR answer_item IN
    SELECT value FROM jsonb_array_elements(p_answers) AS answers(value)
  LOOP
    SELECT * INTO target_question
      FROM public.comprehension_questions q
     WHERE q.question_id = (answer_item->>'question_id')::uuid
       AND q.passage_id = passage_id;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'question does not belong to session passage';
    END IF;

    possible := possible + target_question.points_possible;
    selected_choice_id := NULLIF(answer_item->>'selected_choice_id', '')::uuid;
    selected_is_correct := false;
    IF selected_choice_id IS NOT NULL THEN
      SELECT c.is_correct INTO selected_is_correct
        FROM public.question_choices c
       WHERE c.question_id = target_question.question_id
         AND c.choice_id = selected_choice_id;
      IF NOT FOUND THEN
        RAISE EXCEPTION 'selected choice does not belong to question';
      END IF;
      IF selected_is_correct THEN
        earned := earned + target_question.points_possible;
      END IF;
    END IF;

    INSERT INTO public.comprehension_answers (
      attempt_id, question_id, selected_choice_id, answered_at
    ) VALUES (
      target_attempt.attempt_id,
      target_question.question_id,
      selected_choice_id,
      CASE WHEN selected_choice_id IS NULL THEN NULL ELSE now() END
    );
  END LOOP;

  UPDATE public.comprehension_attempts
     SET status = 'submitted',
         submitted_at = now(),
         score_earned = earned,
         score_possible = possible
   WHERE attempt_id = target_attempt.attempt_id;

  RETURN jsonb_build_object(
    'score_earned', earned,
    'score_possible', possible
  );
END;
$$;

REVOKE ALL ON FUNCTION public.assign_learner_session(uuid, smallint, text)
  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.submit_learner_comprehension(uuid, uuid, jsonb)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.assign_learner_session(uuid, smallint, text)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.submit_learner_comprehension(uuid, uuid, jsonb)
  TO service_role;

CREATE OR REPLACE FUNCTION public.expire_stuck_reading_sessions(
  p_cutoff timestamptz
) RETURNS TABLE(session_id uuid)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  RETURN QUERY
  UPDATE public.sessions s
     SET status = 'failed'
   WHERE s.status IN ('processing', 'comprehension')
     AND s.processing_started_at < p_cutoff
     AND NOT EXISTS (
       SELECT 1
         FROM public.reading_analyses a
        WHERE a.session_id = s.session_id
          AND a.status IN ('partial', 'completed')
     )
  RETURNING s.session_id;
END;
$$;

REVOKE ALL ON FUNCTION public.expire_stuck_reading_sessions(timestamptz)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.expire_stuck_reading_sessions(timestamptz)
  TO service_role;
