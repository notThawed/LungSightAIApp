-- LungSightAI: physician laboratory orders and private supporting documents.
-- Review this migration before running against your Supabase project.
-- Assumes user_profiles, patients, examinations, hospitals, follow_ups use UUID IDs.
-- Does not modify existing examination or follow-up records.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.lab_requests (
    lab_request_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id uuid NOT NULL REFERENCES public.patients(patient_id) ON DELETE RESTRICT,
    hospital_id uuid NOT NULL REFERENCES public.hospitals(hospital_id) ON DELETE RESTRICT,
    origin_examination_id uuid NOT NULL REFERENCES public.examinations(examination_id) ON DELETE RESTRICT,
    follow_up_id uuid REFERENCES public.follow_ups(follow_up_id) ON DELETE SET NULL,
    test_type text NOT NULL CHECK (char_length(trim(test_type)) BETWEEN 2 AND 120),
    status text NOT NULL DEFAULT 'Requested'
        CHECK (status IN ('Requested', 'Result Uploaded', 'Cancelled')),
    requested_by uuid REFERENCES public.user_profiles(user_id) ON DELETE SET NULL,
    requested_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT lab_request_exam_test_unique UNIQUE (origin_examination_id, test_type)
);

CREATE TABLE IF NOT EXISTS public.lab_request_documents (
    document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    lab_request_id uuid NOT NULL REFERENCES public.lab_requests(lab_request_id) ON DELETE RESTRICT,
    follow_up_id uuid NOT NULL REFERENCES public.follow_ups(follow_up_id) ON DELETE RESTRICT,
    patient_id uuid NOT NULL REFERENCES public.patients(patient_id) ON DELETE RESTRICT,
    hospital_id uuid NOT NULL REFERENCES public.hospitals(hospital_id) ON DELETE RESTRICT,
    storage_path text NOT NULL UNIQUE,
    original_filename text NOT NULL,
    content_type text NOT NULL CHECK (content_type IN ('application/pdf','image/png','image/jpeg')),
    size_bytes integer NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 10485760),
    uploaded_by uuid REFERENCES public.user_profiles(user_id) ON DELETE SET NULL,
    uploaded_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS lab_requests_patient_idx
    ON public.lab_requests (patient_id, requested_at DESC);
CREATE INDEX IF NOT EXISTS lab_requests_hospital_idx
    ON public.lab_requests (hospital_id, status);
CREATE INDEX IF NOT EXISTS lab_requests_follow_up_idx
    ON public.lab_requests (follow_up_id);
CREATE INDEX IF NOT EXISTS lab_request_documents_request_idx
    ON public.lab_request_documents (lab_request_id, uploaded_at DESC);

-- Server-side privileged data access only. Do not create anonymous read policies.
ALTER TABLE public.lab_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lab_request_documents ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.lab_requests FROM anon, authenticated;
REVOKE ALL ON public.lab_request_documents FROM anon, authenticated;

-- Private bucket: never use get_public_url() for patient laboratory documents.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'lab-results', 'lab-results', false, 10485760,
    ARRAY['application/pdf','image/png','image/jpeg']::text[]
)
ON CONFLICT (id) DO UPDATE
SET public = false,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;

-- No public storage.objects policy is created. The Streamlit server uses
-- its service-role client after checking the actor's hospital membership.
