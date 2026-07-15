# MySQL Security Guide

## Database account

Use a dedicated account with `SELECT` only on explicit reporting views. Do not grant schema-wide
permissions, write privileges, administrative roles, or access to base tables. Database permissions
remain mandatory even when application validation is enabled.

## Application validation

Only one MySQL `SELECT` statement is accepted. Comments, multiple statements, MySQL variables,
assignments, file functions, locking clauses, write-capable constructs, and unsafe parameter styles
are rejected before a provider is opened. Values are converted by declared type and driver-bound;
they are never interpolated into SQL.

## Runtime limits

Keep connection/query timeouts, unbuffered cursors, row limits, output limits, and cancellation
enabled. A read-only session must be configured and verified. Always close streams, cursors, and
connections through context managers.

## Credentials and output

Persist only `passwordRef`. Resolve secrets at runtime, avoid request/report logging, and rotate the
underlying credential without changing templates. Escape database text as plain text, sandbox live
preview, set `Cache-Control: no-store`, and never persist rows or preview HTML.
