# Learner recording storage

The SAM template creates a private media bucket in the deployment Region. For
Philippine learners, deploy the first production stack in `ap-southeast-1`
(Singapore); the current Sydney `readright-bucket` is not imported or modified.
CloudFormation generates a unique bucket name, returns it as the
`MediaBucketName` stack output, and passes it to the API Lambda.

The bucket has all four S3 Block Public Access settings enabled, bucket-owner
enforced object ownership, and SSE-S3 default encryption. Its CORS rule permits
the origins in `AllowedOrigins` to `POST` uploads. Set this parameter to the
comma-separated frontend origins before deploying.

The backend signs browser uploads for up to 150 MiB (configurable with
`MaxUploadBytes`) and 10 minutes. The policy signs the exact `Content-Type`
value supplied by the browser, including codec parameters. The API Lambda role
can read and write only the `recordings/` prefix. Its `GetObject` grant supports
`HeadObject` verification and the one-hour download link sent to the analysis
service.

The `expire-leftover-videos` lifecycle rule applies only to `recordings/` and
expires videos after 30 days. It also aborts incomplete multipart uploads after
one day. S3 lifecycle expiration is asynchronous, so 30 days is a retention
target rather than a deletion deadline to the minute. The rule does not delete
objects under `audio/`.

The analysis service runs outside this SAM template. Grant its execution role
the following permissions for the `MediaBucketName` output; do not create AWS
access keys for the service or put them in the browser:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::<MediaBucketName>/recordings/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": "arn:aws:s3:::<MediaBucketName>/audio/*"
    }
  ]
}
```

When the analysis service writes database rows, `reading_analyses.source_recording_id`
must reference the extracted **audio** recording row. The database enforces this
constraint. Keep the original video recording ID as `service_jobs.input_recording_id`
for jobs that process the video; the video row remains the provenance record even
after its S3 object is deleted.

The retained WAV audio has no lifecycle expiration yet because the team has not
set its retention period. Confirm parental consent and retention before launch;
S3 storage and request costs continue for every retained audio object. A
different Region requires a new bucket and a stack deployed in that Region;
S3 buckets cannot be moved between Regions. The existing Sydney bucket remains
untouched.
