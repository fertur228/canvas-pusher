BEGIN;
UPDATE storage.buckets SET public=false,file_size_limit=4194304,allowed_mime_types=ARRAY['application/gzip'] WHERE id='flymind-private';
COMMIT;
