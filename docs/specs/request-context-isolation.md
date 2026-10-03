# Capability: Request context isolation on the shared request executor

<!-- Durable spec: it outlives the run. One capability per file; MyFlow injects the requirements a task
     references into the WorkOrder and the review pack. Format is OpenSpec-compatible. -->

Sync pipeline work for `/api/ask` and `/api/ask/stream` runs on one
process-wide thread pool (`utils/request_executor.py`). The request deadline
(`utils/request_deadline.py`) and the LLM request budget
(`llm/request_budget.py`) are context variables, and a context variable set on
a pooled thread stays on that thread after the callable returns. The stream
path binds both on the worker thread. Before this capability the next request
served by that thread inherited them: once the old deadline had passed, a sync
`/api/ask` answered HTTP 200 with the timeout apology, route `timeout`, and no
trace. Found on 2026-10-03 as the flaky `trace not found` failures of the
Python 3.13 CI leg, and reproduced locally on a one-worker executor.

## Requirement: a callable on the request executor leaves no context behind

Every callable the shared request executor runs SHALL run in a context of its
own, whichever way it was submitted: `submit_request`,
`run_on_request_executor`, `submit` on the object `get_request_executor()`
returns, or `loop.run_in_executor` with that object. A value the callable binds
to a context variable SHALL NOT be visible to a later callable on the same
worker thread. The callable SHALL start from the worker thread's own unmodified
context: the submitting thread's context is not copied in, so handing a value
over stays an explicit act of the caller, as it was before.

### Scenario: one worker, two callables
- **GIVEN** a request executor with one worker thread
- **WHEN** a first callable binds a context variable and returns, and a second
  callable then reads that variable on the same thread
- **THEN** the second callable sees the variable's default

### Scenario: the same through the event loop
- **GIVEN** the same one-worker executor
- **WHEN** both callables are submitted with `loop.run_in_executor`
- **THEN** the second callable sees the variable's default

### Scenario: the submitter's context is not copied in
- **GIVEN** a thread that has bound a context variable
- **WHEN** it submits a callable to the request executor
- **THEN** the callable sees the variable's default

## Requirement: a request's deadline and LLM budget end with the request

A request deadline or an LLM request budget bound while serving one `/api/ask`
or `/api/ask/stream` request SHALL NOT apply to a later request, whichever
worker thread serves it.

### Scenario: sync ask after a stream request whose deadline has passed
- **GIVEN** a one-worker request executor, streaming parity on, and a completed
  `/api/ask/stream` request
- **WHEN** that request's deadline has passed and `/api/ask` is called
- **THEN** the response carries the pipeline's answer and not the timeout
  apology, its route is not `timeout`, and the Evidence of its trace id is
  readable (HTTP 200)

### Scenario: the worker thread is clean after a stream request
- **GIVEN** the same completed stream request
- **WHEN** a probe callable runs on the request executor
- **THEN** it sees no request deadline and no LLM request budget
