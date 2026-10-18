# Repository-scoped GitHub dispatch credential

On2026-10-18 the legacy server-side `GITHUB_PAT` returned HTTP401 for every
required GitHub API. This is an actual credential failure, not a Chrome or
Observatory issue. A temporary secret-protected diagnostic Edge Function verified
only sanitized HTTP statuses and was deleted afterwards. Its token was never
returned, printed or copied. The old secret is left intact for legacy provenance.

The separate owner-authorized local `gh` credential is not copied into Supabase.
Use a fine-grained token for **only fertur228/canvas-pusher**, with expiry and:

- Actions: Read and write (workflow dispatch).
- Variables: Read (activation gates).
- Contents: Read (trusted branch workflow verification).
- Metadata: Read (automatic).

Create it through GitHub Settings → Developer settings → Personal access tokens →
Fine-grained tokens. Then run locally:

```sh
cd /Users/almazbukayev/canvas-pusher
PYTHONPATH=. .venv/release/bin/python -m src.flymind.dispatch_setup
```

Paste only into the hidden terminal prompt. Never put it in chat, shell arguments,
Git or the frontend. The helper requires the exact linked project
`irjasmzytjeohwfpdnrl`, performs real read-only API checks, publishes only
`FLYMIND_GITHUB_PAT` using a temporary0600file, verifies the secret digest, then
removes that file. It does not start workflows or enable production. It neither
changes the owner's password nor uses a personal browser session.

Read checks cannot prove Actions write access; verify actual `/check` dispatch and
default-branch completion in the authorized test group after setup. Do not replay
an already claimed update: create one new request, persist its ID, observe the
actual cloud run and result delivery, then test duplicate suppression. Uncertain
outcomes require inspection, not blind resending.

Official contracts: [workflow dispatch](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event),
[repository variables](https://docs.github.com/en/rest/actions/variables#get-a-repository-variable).
