ALTER TABLE public.learners
  ADD COLUMN age integer
  CHECK (age IS NULL OR age BETWEEN 5 AND 18);

-- Preserve ages already collected in Supabase Auth metadata for existing learners.
UPDATE public.learners AS learner
   SET age = CASE
     WHEN (auth_user.raw_user_meta_data ->> 'age') ~ '^(5|6|7|8|9|1[0-8])$'
       THEN (auth_user.raw_user_meta_data ->> 'age')::integer
     ELSE NULL
   END
  FROM auth.users AS auth_user
 WHERE auth_user.id = learner.user_id;
