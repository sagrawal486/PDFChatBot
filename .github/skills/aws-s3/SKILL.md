---
name: aws-s3
description: "Use when implementing, reviewing, or debugging secure AWS S3 file storage for this FastAPI AI PDF Chatbot, including uploads, downloads, private objects, presigned URLs, local emulation, IAM, and storage tests."
---

# Secure AWS S3 File Storage

Use this skill for S3 work in the AI PDF Chatbot. The current application stores
uploads locally through `app/services/file_storage.py`; keep storage behind that
service boundary so callers do not depend directly on an S3 client. Follow the
project dependency flow:

```text
API/Router -> Service -> Repository -> Database
```

The document service owns authorization and upload business rules. A storage
adapter owns object operations. Repositories persist document metadata such as
the object key, not file bytes or credentials.

## S3 Model

- A bucket is a regional, globally unique container with its own policy,
	encryption, lifecycle, versioning, and access settings.
- An object is addressed by `bucket + key`; folders are only key prefixes.
- Store private PDF objects by default. Do not make the bucket public and do not
	expose long-lived object URLs from API responses.
- Store metadata needed by the application in PostgreSQL. S3 metadata and tags
	are supplementary and must not replace authorization data in the database.
- Keep AWS region and bucket name in environment-backed settings, never in code
	or committed configuration.

## Credentials and IAM

- Never hardcode access keys, secret keys, session tokens, or signed URLs.
- Prefer the standard AWS credential provider chain through the SDK's default
	session. On AWS, use an IAM role attached to the workload (ECS task role,
	EKS service account, Lambda execution role, or EC2 instance profile).
- Use access keys only for local or external workloads that cannot assume a
	role. Keep them in environment variables or a local secret manager and rotate
	them; never commit `.env`.
- Grant least privilege. The application role should be limited to the target
	bucket and required prefixes, for example `s3:PutObject`, `s3:GetObject`, and
	optionally `s3:DeleteObject`; bucket administration belongs to infrastructure.
- Do not grant `s3:*`, `s3:ListAllMyBuckets`, or public access unless a narrowly
	justified operation requires it.
- Keep S3 Block Public Access enabled. Require TLS with a bucket policy and use
	server-side encryption, preferably SSE-KMS when the compliance boundary needs
	customer-managed keys.

If the SDK supports explicit credentials for tests, inject a client or factory.
Do not make production code require `AWS_ACCESS_KEY` or `AWS_SECRET_KEY` when an
IAM role can supply credentials. This project currently has AWS setting fields;
normalize names and add an `S3_BUCKET` setting only as part of an intentional
configuration change. The current `requirements.txt` does not include an S3
SDK, so choose and add a maintained SDK dependency only when implementing the
adapter, rather than documenting an undeclared import.

## Object Keys

Generate keys on the server. Never use `UploadFile.filename` as a path or key.
Client filenames can contain traversal sequences, misleading extensions,
Unicode surprises, or collisions.

Prefer a stable, opaque layout such as:

```text
users/{user_id}/documents/{document_id}/{random_token}.pdf
```

- Use a database document ID plus cryptographically secure randomness.
- Restrict key components to validated identifiers and a controlled extension.
- Keep the original filename only as sanitized display metadata.
- Do not put email addresses, JWTs, secrets, or sensitive document titles in a
	key; keys can appear in logs and operational tooling.
- Save the exact key and bucket reference with the document record so retries,
	downloads, and deletion address the same object.

## Upload Validation and Strategy

Validation must happen before accepting the object as a usable document:

1. Require an authenticated user and verify the user owns the target document.
2. Enforce the configured size limit (`MAX_UPLOAD_SIZE_MB`) while streaming;
	 do not read an unbounded upload into memory.
3. Treat `Content-Type` as a hint, not proof. Require `application/pdf`, inspect
	 the initial PDF magic bytes (`%PDF-`), and use a PDF parser or malware scan
	 appropriate to the deployment before processing untrusted content.
4. Generate the object key server-side and set `ContentType` to the validated
	 value. Do not trust client-provided metadata, ACLs, or cache directives.
5. Stream to S3 using multipart upload for large files; configure bounded
	 timeouts, retry behavior, and abort incomplete multipart uploads.
6. Persist metadata only after a successful upload, or use an explicit
	 `pending`/`failed` state and cleanup workflow if the database write fails.

Keep the storage adapter interface small, for example `put`, `get_stream` or
`download`, `delete`, and `create_download_url`. The document service should
translate storage failures into application behavior and should not import SDK
exception classes throughout the API layer.

## Downloads and Presigned URLs

- Check authentication and document ownership before generating or performing a
	download. A presigned URL is not an authorization substitute.
- Prefer a short-lived presigned `GET` URL for large PDFs when the client can
	download directly. Set a short expiry appropriate to the workflow and avoid
	logging the URL.
- For sensitive or small responses, stream the object through the API after
	authorization and set a safe download filename from sanitized metadata.
- If clients upload directly to S3, issue a short-lived presigned `PUT` or
	multipart-upload request for one server-generated key, fixed content type,
	and bounded size. Verify the resulting object before marking it complete.
- Do not return bucket names, AWS credentials, internal storage errors, or
	permanent public URLs to clients.

## Error Handling

Handle expected failures at the adapter boundary and preserve useful context in
structured logs without secrets or document contents:

- Invalid type, size, or ownership: return the appropriate validation or
	authorization response before calling S3.
- `NoSuchKey` or missing metadata: return a controlled not-found response;
	avoid revealing whether another user's object exists.
- Access denied: log the operation and request ID server-side, then return a
	generic service response.
- Timeout, throttling, or transient network errors: use bounded SDK retries,
	return a retryable service error, and do not blindly duplicate non-idempotent
	writes.
- Failed upload after a key is allocated: remove the partial object when safe,
	or mark it failed for cleanup. Do not create a database record that claims a
	missing object is ready.
- Never expose raw boto/SDK exception text, credentials, signed URLs, or bucket
	policy details in HTTP errors.

Use request correlation IDs and capture AWS request IDs where available. Add
metrics for upload/download counts, bytes, latency, failures, and abandoned
multipart uploads.

## Testing Strategy

Keep tests deterministic and independent of real AWS:

- Unit-test the storage adapter with a mocked/injected S3 client, including key
	generation, content type, size boundaries, retries, and error translation.
- Test the document service for ownership checks, invalid MIME/magic bytes,
	maximum size, metadata persistence ordering, and storage failure behavior.
- Test API responses without asserting provider-specific exception text.
- Use a local S3-compatible emulator such as LocalStack or MinIO for focused
	integration tests when mocking cannot validate multipart or presigning
	behavior. Keep emulator tests optional and clearly separated from the normal
	test suite.
- Add an AWS integration test only in an isolated account with a dedicated
	bucket/prefix, short-lived credentials or a role, cleanup, and spend limits.
- Never use production buckets or real customer documents in tests.

## Local Development

The existing Docker Compose file runs PostgreSQL only. Preserve local file
storage as the default for fast development unless the task specifically tests
the S3 adapter. For S3-oriented work, add a separate opt-in emulator service or
run LocalStack/MinIO outside the default stack, with dummy credentials and a
local endpoint supplied through environment-backed settings.

- Use a dedicated local bucket and prefix; never point local code at production.
- Configure path-style addressing if required by the emulator.
- Keep `.env` untracked and provide a safe `.env.example` only if the project
	adopts one; examples must contain placeholders, not credentials.
- Make emulator startup and cleanup part of integration-test instructions, not a
	hidden requirement for ordinary unit tests.

## Production AWS Strategy

- Create buckets through infrastructure as code, with Block Public Access,
	default encryption, versioning where recovery requires it, lifecycle rules,
	access logging or CloudTrail as appropriate, and restrictive bucket policies.
- Use an application IAM role and separate roles for migrations, operations,
	and CI/CD. Scope permissions to environment-specific bucket prefixes.
- Keep the bucket private and use CloudFront or short-lived presigned URLs only
	when their security and caching behavior is understood.
- Scan and validate PDFs before downstream extraction or AI ingestion. Treat
	extracted text and embedded content as untrusted input too.
- Plan deletion, retention, legal hold, backup, and disaster-recovery behavior
	before enabling versioning or replication; document who can permanently purge
	data.
- Use AWS region-specific endpoints and explicit timeouts. Monitor failures,
	latency, storage growth, egress, and lifecycle effectiveness.

## Cost Considerations

- S3 charges for storage, requests, retrieval in some storage classes, and data
	transfer; API downloads can also incur compute and egress costs.
- Avoid needless copy/list operations and repeated downloads. Use multipart
	uploads only when file size justifies their request overhead.
- Configure lifecycle expiration for abandoned uploads and temporary objects.
- Choose storage classes from measured access patterns; do not move frequently
	accessed PDFs to archival classes without accounting for retrieval latency and
	minimum storage durations.
- Presigned URLs can reduce API bandwidth and compute, but monitor public
	distribution, egress, and cache behavior so cost savings do not weaken access
	control.

## Implementation Checklist

Before merging S3 work, verify:

- [ ] The adapter is behind the file-storage service boundary.
- [ ] Credentials come from IAM roles or the SDK provider chain.
- [ ] Bucket, region, and limits are environment-backed settings.
- [ ] Keys are server-generated and do not contain sensitive data.
- [ ] MIME, magic bytes, size, ownership, and PDF safety checks are enforced.
- [ ] Objects are private and encrypted; presigned URLs are short-lived.
- [ ] Upload state and database metadata cannot silently diverge.
- [ ] SDK failures are translated to controlled application errors.
- [ ] Unit tests cover validation and failure paths; integration tests are opt-in.
- [ ] Lifecycle, monitoring, retention, and cost behavior are defined for AWS.
