-- The local variable passage_id clashed with comprehension_questions.passage_id,
-- so every call failed with 'column reference "passage_id" is ambiguous'.
-- Rename it to v_passage_id. The body is otherwise unchanged.
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
  v_passage_id uuid;
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
  SELECT s.passage_id INTO v_passage_id
    FROM public.sessions s
   WHERE s.session_id = p_session_id
     AND s.learner_id = p_learner_id
   FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'session not found';
  END IF;

  SELECT count(*)::integer INTO question_count
    FROM public.comprehension_questions q
   WHERE q.passage_id = v_passage_id;
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
       AND q.passage_id = v_passage_id;
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
