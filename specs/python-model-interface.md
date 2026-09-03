# Python Model Interface (`openjd.model`)

Rust-backed implementation of the Open Job Description model library.
Handles template parsing, validation, job creation, and task iteration.
No Pydantic dependency.

## Architecture

The `openjd.model._v1` namespace mirrors the underlying
[`openjd-model`][openjd-model] Rust crate's two-layer architecture:

1. **Revision-neutral types** — there is exactly one `JobTemplate`
   pyclass (under `openjd.model._v1.template.JobTemplate`), one
   `EnvironmentTemplate`, one `Action`, one `StepTemplate`, and so
   on. The set of pyclasses does **not** vary by specification
   revision.
2. **Revision-specific validation** — the
   `specificationVersion` field of the decoded template is read at
   parse time and used to dispatch the correct revision's
   validation pass on the parsed structure. The validation pass
   enforces revision-specific constraints (allowed extensions,
   field shapes, value bounds, etc.) but the resulting Python
   objects are the same revision-neutral types regardless of
   revision.

This is a deliberate divergence from the v0 (`openjd.model`)
architecture, which used Pydantic's discriminated-union machinery
to produce per-revision class hierarchies (e.g.
`v2023_09.JobTemplate`, with siblings under
`OpenJDModel_v2023_09`). v0 has ~85 per-revision classes under
`openjd.model.v2023_09`; the v1 surface has none. This is **not**
a regression — it is the v1 architecture by design:

* The Rust crate has no per-revision types either. The revision
  version is just a string field on the parsed template; the
  parsed type is identical regardless of revision.
* Future spec revisions that don't change the Python-level shape
  of decoded objects need *no* new pyclass at all — only a new
  validation arm in
  [`openjd_model::template::validation::validate_job_template`][validate].
* Future revisions that *do* change shape will be addressed when
  they ship; the most likely choice is to extend the existing
  pyclass surface with optional new fields rather than introduce
  parallel revision-typed classes.

If a v0 caller writes `isinstance(t, v2023_09.JobTemplate)`, the
v1 equivalent is `isinstance(t, template.JobTemplate)`. To
discriminate by revision, read
`t.specification_version` (returns a `TemplateSpecificationVersion`
enum value).

[openjd-model]: https://github.com/OpenJobDescription/openjd-rs/tree/main/crates/openjd-model
[validate]: https://github.com/OpenJobDescription/openjd-rs/blob/main/crates/openjd-model/src/template/validation/mod.rs

## Module Layout

The `openjd.model._v1` package is split into four submodules that
mirror the underlying Rust crate's organization. The top-level
`openjd.model._v1` re-exports the *entry points* (decode/create
functions, the `SpecificationRevision` and
`TemplateSpecificationVersion` enums, and the cross-cutting types
`ModelProfile`, `CallerLimits`, `DocumentType`), but **does not**
re-export the structural pyclasses — those live in their respective
submodules. Examples in this spec import each symbol from its
canonical location.

| Submodule | Contents |
|---|---|
| `openjd.model._v1` (top level) | Entry-point functions (`decode_job_template`, `decode_job_template_str`, `decode_environment_template`, `decode_environment_template_str`, `create_job`, `preprocess_job_parameters`, `merge_job_parameter_definitions`, `evaluate_let_bindings`), the `CallerLimits` and `ModelProfile` cross-cutting types, `DocumentType` (also in `.types`), the Rust pyclass enums `SpecificationRevision` and `TemplateSpecificationVersion` (re-exported from `openjd._openjd_rs`; behave like `str`-Enums with lowercase variant names — see their dedicated sections below), and the capability-validation helpers (`validate_amount_capability_name`, `validate_attribute_capability_name`, `standard_amount_capability_names`, `standard_attribute_capability_names`, `standard_attribute_capabilities`). **Explicitly NOT exposed at v1**: the v0 names `ParameterValue`, `ParameterValueType`, `ValueReferenceConstants`, `CancelationMethodTerminate`, `CancelationMethodNotifyThenTerminate`, `CompatibilityError`, `CommandString`, `ArgString`, `EmbeddedFileText`, `EmbeddedFiles`, `StepDependencyGraphNode`, `StepDependencyGraphStepToStepEdge`, `FormatStringError`, `RevisionExtensions`, and the legacy `openjd.expr` re-exports (`SymbolTable`, `FormatString`, `RangeExpr`, `ExpressionError`). Use the canonical locations: `openjd.model._v1.types` (parameter types/values, `JobParameterValue`/`TaskParameterValue`, `JobParameterType`/`TaskParameterType`); `openjd.model._v1.template` / `openjd.model._v1.job` (structural pyclasses, `EmbeddedFile`, `StepDependencyEdge`); `openjd.model._v1.errors` (`DecodeValidationError`, `ModelValidationError`, `UnsupportedSchema`); and `openjd.expr` (expression-layer types). For revision/extensions information, use `ModelProfile.from_strings(revision, extensions)` directly — `RevisionExtensions` was a v0 wrapper that no longer has a v1 counterpart. The `openjd.model._v1.v2023_09` submodule is also gone — it was a v0-shaped per-revision compat shim with no Rust-API counterpart; structural pyclasses live in their canonical submodules (`_v1.template`, `_v1.job`, `_v1.types`, `_v1.errors`) and revision is a property of types, not a namespace. |
| `openjd.model._v1.template` | Template-time pyclasses returned by `decode_*_template`: `JobTemplate`, `EnvironmentTemplate`, `StepTemplate`, `Action`, `EmbeddedFile`, the 12 typed job-parameter-definition variants (`JobStringParameterDefinition`, `JobIntParameterDefinition`, `JobFloatParameterDefinition`, `JobPathParameterDefinition`, `JobBoolParameterDefinition`, `JobRangeExprParameterDefinition`, `JobListStringParameterDefinition`, `JobListPathParameterDefinition`, `JobListIntParameterDefinition`, `JobListFloatParameterDefinition`, `JobListBoolParameterDefinition`, `JobListListIntParameterDefinition`), the typed task-parameter-definition variants, and the `*UserInterface` pyclasses. |
| `openjd.model._v1.job` | Job-time pyclasses returned by `create_job`: `Job`, `Step`, `StepScript`, `StepActions`, `Action`, `Environment`, `StepParameterSpace`, `StepParameterSpaceIterator`, `StepDependencyGraph`, the typed task-parameter pyclasses, and the job-time `EmbeddedFile`. |
| `openjd.model._v1.types` | Cross-cutting types: `JobParameterType`, `JobParameterValue`, `TaskParameterType`, `TaskParameterValue`, `DocumentType`, `ModelProfile`, `ModelExtension`, `SpecificationRevision`, `TemplateSpecificationVersion`, `CallerLimits`, `ValidationContext`. |
| `openjd.model._v1.errors` | Exception classes raised by decode/create paths: `DecodeValidationError`, `ModelValidationError`, `UnsupportedSchema`. |

## Functions

### Decode

> **Implementation note — Python-dict input.** The four
> `decode_*_template{,_str}` functions all share a Python→Rust
> conversion shim. The dict-shaped variants (`decode_job_template`
> / `decode_environment_template`) convert the Python dict to
> `serde_json::Value` via `json.dumps` + `serde_json::from_str`
> before handing off to the upstream Rust validator. This detour
> looks wasteful but the alternatives are not actually faster:
> a `pythonize::depythonize` prototype (against `pyo3 = 0.28`)
> regressed end-to-end decode time by 12% on small templates and
> 5% on medium templates (20 steps × 20 parameter definitions),
> because CPython's C-level `json.dumps` plus
> `serde_json::from_str` together are faster than `pythonize`'s
> PyO3-driven recursive walk. The conversion step is also only
> ~0.6% of end-to-end cost — template validation in
> [`openjd_model::decode_*_template`][openjd-model] dominates —
> so even a notionally faster shim wouldn't be visible to
> callers. As a side effect, both paths reject non-JSON-
> serialisable values (`Decimal`, `Path`, custom objects) with
> the same `unsupported type` error: `pythonize` would not
> have changed that.
>
> If decode performance ever matters for a workload, the
> productive optimisation lives in the upstream Rust validator,
> not in the conversion shim.

#### `decode_job_template`

Decode and validate a job template from a Python dict. Mirrors the
Rust `openjd_model::decode_job_template` signature: takes a list of
extension *strings* as the caller's allowlist, plus optional
`CallerLimits`.

```python
from openjd.model._v1 import decode_job_template

template = decode_job_template(
    template={
        "specificationVersion": "jobtemplate-2023-09",
        "name": "MyRenderJob",
        "extensions": ["EXPR"],
        "parameterDefinitions": [
            {"name": "Frames", "type": "STRING", "default": "1-10"},
        ],
        "steps": [{
            "name": "Render",
            "parameterSpace": {
                "taskParameterDefinitions": [
                    {"name": "Frame", "type": "INT", "range": "{{Param.Frames}}"}
                ]
            },
            "script": {
                "actions": {
                    "onRun": {
                        "command": "render",
                        "args": ["--frame", "{{Task.Param.Frame}}"]
                    }
                }
            }
        }],
    },
    supported_extensions=["EXPR"],
)
template.name        # "MyRenderJob"
template.profile     # ModelProfile from the *template's* declared extensions:
                     # ModelProfile(revision=V2023_09, extensions=[EXPR])
```

Argument semantics (matching the Rust API):

* `supported_extensions` — the caller's *allowlist*. The template's
  `extensions:` field is validated against this list; any name in the
  template that is not both a recognized `ModelExtension` AND in this
  list is rejected with `Unsupported extension names: ...`. Pass
  `None` (the default) for an empty allowlist.
* `caller_limits` — optional `CallerLimits` to tighten spec-defined
  limits (max steps, max envs, max task count, max template size, …).

The `ModelProfile` type is used as an *output* of decoding (via
`JobTemplate.profile`) and as an *input* to other functions
(`create_job(validation_context=...)`, `ModelProfile.to_expr_profile(host)`).
It is not an input to `decode_*_template` itself — that function takes
a flat list of strings, mirroring the Rust crate.

#### `decode_job_template_str`

Decode directly from a YAML or JSON string — no intermediate dict.
Convenience wrapper around the dict-shaped entry point above.

```python
from openjd.model._v1 import decode_job_template_str, DocumentType

yaml_str = """
specificationVersion: jobtemplate-2023-09
name: SimpleJob
steps:
  - name: Step1
    script:
      actions:
        onRun:
          command: echo
          args: ["hello"]
"""
template = decode_job_template_str(yaml_str, DocumentType.YAML)
```

The ``format`` argument defaults to ``DocumentType.YAML``, which is
also a superset of JSON, so most callers can omit it. Pass
``DocumentType.JSON`` to force strict JSON parsing — useful when
the source is known to be JSON and the caller wants JSON-only
diagnostics on parse failures.

``decode_job_template_str`` accepts the same ``supported_extensions``
and ``caller_limits`` kwargs as :func:`decode_job_template`.

#### `decode_environment_template`

Decode and validate an environment template from a Python dict.

```python
from openjd.model._v1 import decode_environment_template

env_template = decode_environment_template(template={
    "specificationVersion": "environment-2023-09",
    "environment": {
        "name": "PythonVenv",
        "script": {
            "actions": {
                "onEnter": {"command": "python", "args": ["-m", "venv", ".venv"]},
                "onExit": {"command": "rm", "args": ["-rf", ".venv"]},
            }
        }
    }
})
```

``decode_environment_template`` accepts ``supported_extensions``
with the same semantics as :func:`decode_job_template`. Environment
templates do not accept ``caller_limits``.

#### `decode_environment_template_str`

Decode an environment template directly from a YAML or JSON string.

```python
from openjd.model._v1 import decode_environment_template_str, DocumentType

yaml_str = """
specificationVersion: environment-2023-09
environment:
  name: PythonVenv
  script:
    actions:
      onEnter: {command: python, args: ["-m", "venv", ".venv"]}
      onExit:  {command: rm, args: ["-rf", ".venv"]}
"""
env_template = decode_environment_template_str(yaml_str)
```

Same defaults as :func:`decode_job_template_str`: ``format``
defaults to ``DocumentType.YAML``. Accepts ``supported_extensions``;
environment templates do not accept ``caller_limits``.

### Job Creation

#### `create_job`

Create a fully resolved job from a template and parameter values.

```python
from openjd.model._v1 import decode_job_template, create_job

template = decode_job_template(template={
    "specificationVersion": "jobtemplate-2023-09",
    "name": "{{Param.JobName}}",
    "parameterDefinitions": [
        {"name": "JobName", "type": "STRING"},
    ],
    "steps": [{
        "name": "Render",
        "script": {"actions": {"onRun": {"command": "render"}}}
    }]
})

job = create_job(
    job_template=template,
    job_parameter_values={"JobName": {"type": "STRING", "value": "MyJob"}},
)
job.name                          # "MyJob"
job.steps[0].name                 # "Render"
str(job.steps[0].script.actions.onRun.command)  # "render"
```

#### `preprocess_job_parameters`

Validate and coerce job parameter values. Accepts `str` or `pathlib.Path`
for directory arguments.

```python
from openjd.model._v1 import decode_job_template, preprocess_job_parameters
from pathlib import Path

template = decode_job_template(template={
    "specificationVersion": "jobtemplate-2023-09",
    "name": "Test",
    "parameterDefinitions": [
        {"name": "Count", "type": "INT", "default": "10"},
    ],
    "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
})

params = preprocess_job_parameters(
    job_template=template,
    job_parameter_values={"Count": "5"},
    job_template_dir=Path("."),
    current_working_dir=Path("."),
)
# Returns validated parameter dict
```

#### `merge_job_parameter_definitions`

Merge parameter definitions from a job template and a list of
environment templates into a single deduplicated, conflict-checked
list. Used by callers (notably ``openjd-cli``) that need to
present the union of every parameter the user might be asked to
supply across a job and its attached environments.

```python
from openjd.model._v1 import decode_job_template, merge_job_parameter_definitions

template = decode_job_template(template={...})
merged = merge_job_parameter_definitions(job_template=template)
```

**Return shape — `list[dict]`, not typed pyclasses.** Each entry
in the returned list is a plain Python ``dict`` with the
following keys:

* ``name`` (``str``) — the parameter name.
* ``type`` (``str``) — the parameter's spec-form type name
  (``"INT"``, ``"PATH"``, ``"STRING"``, …).
* ``source`` (``str``) — the name of the template the
  definition came from (the job template's name, or the name of
  the environment template that contributed the definition).
* ``default`` (present only if the source template provided a
  default) — the default value, in its native Python type
  (``int`` / ``float`` / ``str`` / ``list`` / …) per the
  parameter's type.
* ``description`` (``str``, present only if at least one
  contributing template provided one) — the human-readable
  description copied from the originating template. When more
  than one contributing template defines a description for the
  same parameter, the description from the template walked last
  wins (environment templates are walked in order, then the job
  template), mirroring how ``default`` is tracked.
* ``objectType`` (``str``, present only for ``PATH`` parameters
  with an ``objectType`` declared) — ``"FILE"`` or
  ``"DIRECTORY"``.
* ``dataFlow`` (``str``, present only for ``PATH`` parameters
  with a ``dataFlow`` declared) — ``"NONE"``, ``"IN"``,
  ``"OUT"``, or ``"INOUT"``.

This is a deliberate divergence from the v0 reference, which
returns a ``list[JobParameterDefinition]`` (typed pyclass per
variant). The dict shape is consistent with the binding's other
parameter-shaped outputs (``preprocess_job_parameters`` also
returns a dict-keyed payload) and avoids the cost of
re-materialising 12 typed pyclass variants for what is most
commonly a quick "show the user every parameter and ask for
values" pass. The underlying Rust crate's
``openjd_model::merge_job_parameter_definitions`` returns a
struct with ``source`` / ``name`` / ``param_type`` / ``default`` /
``object_type`` / ``data_flow`` fields; the binding flattens
that struct into the dict above and additionally recovers
``description`` by walking the same template sources the merge
walked (the upstream struct does not carry a description field).

#### `evaluate_let_bindings`

Evaluate a list of let-binding strings against a symbol table and
return a new symbol table containing both the original input symbols
and the new bound names.

The function lives under ``openjd.model._v1`` rather than
``openjd.expr`` because the binding implementation is in the
``openjd-model`` Rust crate (``openjd_model::evaluate_let_bindings``)
— it raises a model-layer ``ExpressionError`` and is consumed by
the model crate's job-creation runtime (and by the sessions runtime
when a step's ``script.let`` bindings need to be resolved against
the current task-scope symbols before ``Session.run_task``).

```python
from openjd.expr import SymbolTable
from openjd.model._v1 import evaluate_let_bindings

symtab = SymbolTable({"Param.Start": 1, "Param.Count": 10})
resolved = evaluate_let_bindings(
    ["end = Param.Start + Param.Count - 1"],
    symtab,
)
resolved["end"].item()         # 10
resolved["Param.Start"].item() # 1 — input symbols are preserved
```

Each binding is parsed and evaluated in left-to-right order against
the running symbol table, so a later binding may reference names
introduced by earlier ones:

```python
result = evaluate_let_bindings(
    [
        "a = Param.X + 1",
        "b = a * 2",
        "c = a + b",
    ],
    SymbolTable({"Param.X": 10}),
)
result["a"].item(), result["b"].item(), result["c"].item()  # (11, 22, 33)
```

The full signature is
``evaluate_let_bindings(bindings, symtab, *, profile=None) -> SymbolTable``.
``profile`` accepts an [``ExprProfile``][profile] when the caller
needs a non-default revision / extension set or a configured
``HostContext``; omitting it uses the current profile.

[profile]: ./python-expr-interface.md#exprrevision--exprextension--hostcontext--exprprofile

A binding without ``=`` raises ``ExpressionError`` with the
offending text in the message
(``"Missing '=' in let binding: <text>"``); a binding whose
right-hand side fails to parse or evaluate raises
``ExpressionError`` with a diagnostic that names the offending
binding (``"Error evaluating let binding '<name>': ..."``).

### Utility

#### `model_to_object` — v0-only, not implemented in v1

`model_to_object(*, model)` is a pure-Python helper from
`openjd.model` (the v0 / pydantic-based reference) that walks a
`BaseModel.model_dump()` result and converts nested `Decimal`
instances back to strings so the resulting dict is JSON/YAML-
serializable. It is **not** part of the v1 (Rust-backed)
interface — the v1 model pyclasses (`JobTemplate`,
`EnvironmentTemplate`, the various `*ParameterDefinition`s, etc.)
do not have a general "serialize this whole model back to a
JSON-shaped dict" method, and there are no plans to add one.

If specific use cases surface that need similar functionality
(e.g. round-tripping a job template back to YAML for diffing,
or extracting a particular sub-model as a dict), they will be
addressed as targeted helpers on the relevant pyclass(es) — not
as a single `model_to_object` umbrella API. Reach out with the
concrete use case and we'll decide what shape that helper takes.

The v0 module retains `from openjd.model import model_to_object`
unchanged; it works on v0 / pydantic models only, and importing
it through `openjd.model._v1` is intentionally not supported.

### Capability validation

Capability *names* (the string identifiers like `amount.worker.vcpu`
or `attr.worker.os.family`) follow a constrained lexical shape:
optional vendor prefix (`vendor:`), required first segment of
`amount` or `attr`, then one or more dot-separated identifier
segments. The OpenJD specification reserves a small set of
"standard" capabilities under the reserved scopes `worker`, `job`,
`step`, and `task` — only spec-defined capabilities may use those
scopes. Vendor-prefixed names and non-reserved-scope unprefixed
names are accepted unconditionally.

`openjd.model._v1` exposes both the validators and the standard-
capability lookups directly:

```python
from openjd.model._v1 import (
    validate_amount_capability_name,
    validate_attribute_capability_name,
    standard_amount_capability_names,
    standard_attribute_capability_names,
    standard_attribute_capabilities,
)
```

#### `validate_amount_capability_name` / `validate_attribute_capability_name`

```python
validate_amount_capability_name(
    *,
    capability_name: str | FormatString,
    profile: ModelProfile | None = None,
) -> None
```

Returns `None` on success and raises `ValueError` on a malformed
name. Checks (in order):

1. Length must be ≤ 100 characters.
2. Must match the capability-name regex (vendor prefix optional;
   required first segment is `amount.` or `attr.`).
3. Names without a vendor prefix that match a spec-defined
   standard capability (e.g. `amount.worker.vcpu`) are accepted.
4. Names whose second dot-segment is one of the reserved scopes
   (`worker`, `job`, `step`, `task`) are rejected unless they
   appear in (3) — those scopes are reserved for OpenJD-defined
   capabilities.

`profile` defaults to a profile equivalent to `ModelProfile()`.
Pass an explicit profile to validate against a different
revision/extensions combination's standard-capability set.

`capability_name` accepts either a plain `str` or a `FormatString`.
A `FormatString` containing unresolved expressions short-circuits
— validation is deferred to expression-resolution time. A literal
`FormatString` falls through to the same checks as a plain string.

`validate_attribute_capability_name` has the same shape and
semantics, with `attr.` rather than `amount.` as the required
first segment.

#### `standard_amount_capability_names` / `standard_attribute_capability_names`

```python
standard_amount_capability_names(*, profile: ModelProfile | None = None) -> list[str]
standard_attribute_capability_names(*, profile: ModelProfile | None = None) -> list[str]
```

Return the names of the spec-defined amount/attribute capabilities
for the given profile. For example, with `profile=None` (current
default revision):

```python
>>> standard_amount_capability_names()
['amount.worker.vcpu', 'amount.worker.memory', 'amount.worker.gpu',
 'amount.worker.gpu.memory', 'amount.worker.disk.scratch']
>>> standard_attribute_capability_names()
['attr.worker.os.family', 'attr.worker.cpu.arch']
```

#### `standard_attribute_capabilities`

```python
standard_attribute_capabilities(
    *, profile: ModelProfile | None = None
) -> list[tuple[str, list[str]]]
```

Returns the spec-defined attribute capabilities along with each
capability's allowed values:

```python
>>> standard_attribute_capabilities()
[('attr.worker.os.family', ['linux', 'windows', 'macos']),
 ('attr.worker.cpu.arch', ['x86_64', 'arm64'])]
```

There is no equivalent function for amount capabilities — amount
values are unconstrained non-negative numbers, so there is nothing
to enumerate per name.

## Output Types (from Rust)

Both snake_case and camelCase property accessors are provided.
Constructors that take template-shape kwargs (e.g. ``StepActions``,
``EnvironmentActions``, ``StepScript``, ``EnvironmentScript``,
``EmbeddedFile``) accept either the snake-case form or the
camelCase alias used by v0 (Pydantic) and the JSON template
schema. If both flavours of the same field are passed, the
snake-case form wins.

### `Job`

The fully resolved job, produced by `create_job`.

```python
job.name                    # "MyRenderJob"
job.description             # Optional[str]
job.revision                # "2023-09"
job.extensions              # Optional[list[str]], e.g. ["EXPR"]
job.steps                   # list[Step]
job.parameters              # dict[str, JobParameter]
job.job_environments        # Optional[list[Environment]]
job.jobEnvironments         # same (camelCase alias)
```

### `Step`

A step within a job.

```python
step = job.steps[0]
step.name                   # "Render"
step.description            # Optional[str]
step.script                 # StepScript
step.parameterSpace         # Optional[StepParameterSpace]
step.stepEnvironments       # Optional[list[Environment]]
step.dependencies           # Optional[list[StepDependency]]
step.host_requirements      # Optional[HostRequirements] (alias: hostRequirements)
step.resolvedBindings       # Optional[list[str]] — let binding strings
step.resolved_symtab        # Optional[SymbolTable] — resolved at step scope
```

`Step` defines `__eq__` and `__hash__` by **name only** — two
``Step`` instances with the same ``name`` compare equal and hash
identically, regardless of script/parameter-space/etc. content.
This matches how `StepDependencyGraph` and the worker agent
identify steps for graph operations and runtime correlation.

### `StepScript`

```python
script = step.script
script.revision             # "2023-09"
script.actions              # StepActions
script.let                  # Optional[list[str]], e.g. ["end = Param.Start + Param.Count - 1"]
script.embeddedFiles        # Optional[list[EmbeddedFile]]
```

### `StepActions` / `Action`

```python
action = step.script.actions.onRun
action.command              # FormatString — resolve at runtime with .resolve(symtab, library)
action.args                 # Optional[list[FormatString]]
action.timeout              # Optional[FormatString] — resolve at runtime to
                            # get the integer-string form, or call .raw()
                            # to read the unresolved template form
action.cancelation          # Optional[CancelationMode]

# At runtime (in sessions):
from openjd.expr import SymbolTable, FunctionLibrary
symtab = SymbolTable({"Param.Frame": 42})
library = FunctionLibrary()
command_str = str(action.command.resolve(symtab, library))
```

### `Environment`

```python
env = job.job_environments[0]
env.name                    # "PythonVenv"
env.description             # Optional[str]
env.script                  # Optional[EnvironmentScript]
env.variables               # Optional[dict[str, str]]
```

### `EnvironmentScript` / `EnvironmentActions`

```python
env.script.actions.onEnter  # Optional[Action]
env.script.actions.onExit   # Optional[Action]
env.script.embeddedFiles    # Optional[list[EmbeddedFile]]
```

### `EmbeddedFile`

```python
ef = step.script.embeddedFiles[0]
ef.name                     # "run.sh"
ef.type                     # "TEXT"
ef.filename                 # Optional[str]
ef.data                     # Optional[str] — file content
ef.runnable                 # Optional[bool] — set the executable bit
                            # when materialising the file
ef.end_of_line              # Optional[str] — "LF" / "CRLF" / "AUTO"
                            # (alias: endOfLine)
```

### `JobParameter`

```python
param = job.parameters["Count"]
param.name                  # "Count"
param.type                  # JobParameterType.INT (enum, not str)
str(param.type)             # "INT"
param.type.as_str()         # "INT"
param.value                 # ExprValue — use .item() to get native value
param.value.item()          # 5
```

`JobParameter.type` returns a :class:`JobParameterType` enum,
mirroring the v0 reference's ``JobParameter.type`` field type and
the underlying Rust ``job::JobParameter.param_type`` field. Like
``TypeCode`` and ``PathFormat``, the enum is a pyo3 enum without a
``str`` mixin, so equality against a string literal returns
``False`` — ``param.type == "INT"`` is **not** the same as
``param.type == JobParameterType.INT``. Compare against the enum
(``param.type is JobParameterType.INT``), or call
``str(param.type)`` / ``param.type.as_str()`` when you need the
spec-form string.

**No ``description`` field.** The v0 reference's
``JobParameter`` carried a ``description: Optional[str]`` field
copied from the parameter definition into the materialised
``JobParameter`` at job-creation time. The Rust crate's
``job::JobParameter`` struct deliberately does **not** carry
``description`` — a job-time parameter is the resolved
``(name, type, value)`` triple, and the description belongs to
the *definition* on the template. Callers that need the
description should read it from the corresponding
``JobParameterDefinition`` on ``JobTemplate.parameter_definitions``
instead. The binding mirrors the Rust struct and intentionally
does not expose ``description``.

### `StepParameterSpace`

```python
space = step.parameterSpace
space.taskParameterDefinitions  # dict[str, IntTaskParameter | FloatTaskParameter |
                                #            StringTaskParameter | PathTaskParameter |
                                #            ChunkIntTaskParameter]
space.combination               # Optional[str]
```

Each value in `taskParameterDefinitions` is one of five typed
pyclasses, mirroring the underlying Rust `TaskParameter` runtime enum
1:1. Discriminate by `isinstance` or by the `type` getter.

### `IntTaskParameter` / `FloatTaskParameter` / `StringTaskParameter` / `PathTaskParameter`

```python
F = step.parameterSpace.taskParameterDefinitions["F"]
isinstance(F, IntTaskParameter)         # True for INT
F.type                                  # TaskParameterType.INT
F.range                                 # list[int] | RangeExpr  (INT only)
                                        # list[float]            (FLOAT)
                                        # list[str]              (STRING / PATH)
```

| Class | `type` | `range` element type |
|---|---|---|
| `IntTaskParameter` | `TaskParameterType.INT` | `list[int]` or `RangeExpr` |
| `FloatTaskParameter` | `TaskParameterType.FLOAT` | `list[float]` |
| `StringTaskParameter` | `TaskParameterType.STRING` | `list[str]` |
| `PathTaskParameter` | `TaskParameterType.PATH` | `list[str]` |

None of these four carry a `chunks` field — only `ChunkIntTaskParameter`
does. (The underlying Rust struct has `chunks: Option<ResolvedChunks>`
on the `Int` variant for shape reasons, but no resolver path ever
populates it; the binding mirrors the runtime *behaviour*.)

### `ChunkIntTaskParameter`

Available only when the `TASK_CHUNKING` extension is enabled.

```python
F = step.parameterSpace.taskParameterDefinitions["F"]
F.type                                  # TaskParameterType.CHUNK_INT
F.range                                 # list[int] | RangeExpr
F.chunks                                # TaskChunksDefinition (always set)
```

### `TaskChunksDefinition`

```python
chunks = chunk_int_param.chunks
chunks.default_task_count               # int
chunks.target_runtime_seconds           # Optional[int]
chunks.range_constraint                 # "CONTIGUOUS" or "NONCONTIGUOUS"
```

`range_constraint` is exposed as a string rather than a separate enum
class because it has only two values; future revisions may promote it
to a typed enum if a third variant is added.

### `StepDependency`

```python
dep = step.dependencies[0]
dep.dependsOn               # "PreviousStep"
```

### `CancelationMode`

```python
cancel = action.cancelation
cancel.mode                 # "TERMINATE" or "NOTIFY_THEN_TERMINATE"
cancel.notify_period_in_seconds  # Optional[int]
```

### `HostRequirements` / `AmountRequirement` / `AttributeRequirement`

Job-time host requirements. Distinct from the template-time
``HostRequirements`` / ``AmountRequirement`` / ``AttributeRequirement``
(see `openjd.model._v1.template`): the template-time variants carry
unresolved ``FormatString`` values for ``min`` / ``max`` / ``anyOf`` /
``allOf``, while these job-time variants carry the post-``create_job``
resolved ``f64`` (amounts) and ``str`` (attributes) values.

```python
hr = step.host_requirements        # alias: step.hostRequirements
hr.amounts                         # Optional[list[AmountRequirement]]
hr.attributes                      # Optional[list[AttributeRequirement]]

amount = hr.amounts[0]
amount.name                        # "amount.worker.vcpu"
amount.min                         # Optional[float]
amount.max                         # Optional[float]

attr = hr.attributes[0]
attr.name                          # "attr.worker.os.family"
attr.any_of                        # Optional[list[str]]  (alias: anyOf)
attr.all_of                        # Optional[list[str]]  (alias: allOf)
```

The classes are exposed under ``openjd.model._v1.job``. Use
``isinstance(hr, openjd.model._v1.job.HostRequirements)`` to
discriminate from the template-time class of the same short name.

## Template Types (from Rust, opaque)

Templates are produced by `decode_*` functions and passed to `create_job`.

```python
template = decode_job_template(template={...})
template.name                    # raw format string, e.g. "{{Param.JobName}}"
template.specification_version   # TemplateSpecificationVersion enum
template.specificationVersion    # camelCase alias for specification_version
template.description             # Optional[str]
template.steps                   # list[StepTemplate]
template.job_environments        # Optional[list[Environment]]
template.jobEnvironments         # camelCase alias

env_template = decode_environment_template(template={...})
env_template.environment         # Environment
env_template.specification_version
env_template.specificationVersion
```

The structural pyclasses for template-time types live under
``openjd.model._v1.template`` and mirror ``openjd_model::template``
in the Rust crate 1:1.

```python
from openjd.model._v1.template import (
    StepTemplate, Environment, Action,
    EnvironmentScript, EnvironmentActions,
    StepScript, StepActions, EmbeddedFile,
    HostRequirements, AmountRequirement, AttributeRequirement,
    StepDependency, CancelationMode, SimpleAction,
)
```

The classes whose names collide with their job-time counterparts at
``openjd.model._v1.job`` (``Action``, ``AmountRequirement``,
``AttributeRequirement``, ``CancelationMode``, ``EmbeddedFile``,
``Environment``, ``EnvironmentActions``, ``EnvironmentScript``,
``HostRequirements``, ``StepActions``, ``StepDependency``,
``StepScript``) are exposed under both their short name and a
``Template``-prefixed alias (e.g. ``Action`` and ``TemplateAction``
are the same class). On the job-time side under
``openjd.model._v1.job`` the unprefixed name resolves to a
**different** Rust pyclass — for example, the template-time
``HostRequirements`` carries ``FormatString`` fields while the
job-time ``HostRequirements`` carries the post-``create_job``
resolved ``f64`` / ``str`` values. Use ``isinstance`` checks
against the import path that matches the lifecycle stage you
care about.

### `StepTemplate`

```python
step = job_template.steps[0]
step.name                       # str
step.description                # Optional[str]
step.let_bindings               # Optional[list[str]] (alias: step.let)
step.dependencies               # Optional[list[StepDependency]]
step.step_environments          # Optional[list[Environment]] (alias: stepEnvironments)
step.host_requirements          # Optional[HostRequirements] (alias: hostRequirements)
step.parameter_space            # Optional[StepParameterSpaceDefinition]
                                #   (alias: parameterSpace)
step.script                     # Optional[StepScript]
# SimpleAction sugar (FEATURE_BUNDLE_1):
step.bash                       # Optional[SimpleAction]
step.python                     # Optional[SimpleAction]
step.cmd                        # Optional[SimpleAction]
step.powershell                 # Optional[SimpleAction]
step.node                       # Optional[SimpleAction]
```

### `Environment`

```python
env = job_template.job_environments[0]  # or env_template.environment
env.name                        # str
env.description                 # Optional[str]
env.script                      # Optional[EnvironmentScript]
env.variables                   # Optional[dict[str, FormatString]]
```

### `EnvironmentScript` / `StepScript`

```python
script = step.script  # or env.script
script.actions                  # StepActions or EnvironmentActions
script.let_bindings             # Optional[list[str]] (alias: script.let)
script.embedded_files           # Optional[list[EmbeddedFile]] (alias: embeddedFiles)
```

### `StepActions` / `EnvironmentActions`

```python
script.actions.on_run           # Action  (StepActions; alias: onRun)
script.actions.on_enter         # Optional[Action]  (EnvironmentActions; alias: onEnter)
script.actions.on_exit          # Optional[Action]  (EnvironmentActions; alias: onExit)
```

### `Action`

```python
action = step.script.actions.on_run
action.command                  # FormatString
action.args                     # Optional[list[FormatString]]
action.timeout                  # Optional[FormatString]
action.cancelation              # Optional[CancelationMode]
```

### `CancelationMode`

```python
cm = action.cancelation
cm.mode                         # "TERMINATE" or "NOTIFY_THEN_TERMINATE"
cm.notify_period_in_seconds     # Optional[FormatString] (alias: notifyPeriodInSeconds)
```

### `EmbeddedFile`

```python
ef = step.script.embedded_files[0]
ef.name                         # str
ef.type                         # "TEXT"
ef.filename                     # Optional[FormatString]
ef.data                         # Optional[FormatString]
ef.runnable                     # Optional[bool]
ef.end_of_line                  # Optional["LF" | "CRLF" | "AUTO"] (alias: endOfLine)
```

### `HostRequirements` / `AmountRequirement` / `AttributeRequirement`

```python
hr = step.host_requirements
hr.amounts                      # Optional[list[AmountRequirement]]
hr.attributes                   # Optional[list[AttributeRequirement]]

amt = hr.amounts[0]
amt.name                        # str
amt.min                         # Optional[FormatString]
amt.max                         # Optional[FormatString]

attr = hr.attributes[0]
attr.name                       # str
attr.any_of                     # Optional[list[FormatString]] (alias: anyOf)
attr.all_of                     # Optional[list[FormatString]] (alias: allOf)
```

### `StepDependency`

```python
dep = step.dependencies[0]
dep.depends_on                  # str (alias: dependsOn)
```

### `SimpleAction` (FEATURE_BUNDLE_1)

```python
sa = step.bash  # or .python, .cmd, .powershell, .node
sa.script                       # str
sa.let_bindings                 # Optional[list[str]] (alias: let)
sa.args                         # Optional[list[FormatString]]
sa.timeout                      # Optional[FormatString]
sa.cancelation                  # Optional[CancelationMode]
```

### `StepParameterSpaceDefinition` (5 typed task-parameter variants)

`StepTemplate.parameter_space` returns
`Optional[StepParameterSpaceDefinition]`. The `task_parameter_definitions`
list contains one of five typed pyclasses per element, mirroring the
underlying `template::TaskParameterDefinition` enum 1:1:

| Variant | Pyclass | `range` element type |
|---|---|---|
| `INT` | `IntTaskParameterDefinition` | `list[int]` or `FormatString` |
| `FLOAT` | `FloatTaskParameterDefinition` | `list[float \| FormatString]` or `FormatString` |
| `STRING` | `StringTaskParameterDefinition` | `list[FormatString]` or `FormatString` |
| `PATH` | `PathTaskParameterDefinition` | `list[FormatString]` or `FormatString` |
| `CHUNK[INT]` | `ChunkIntTaskParameterDefinition` | `list[int]` or `FormatString` |

Common attributes on every variant:

```python
defs = step.parameter_space.task_parameter_definitions  # list[...]
d = defs[0]
d.type                          # "INT" | "FLOAT" | "STRING" | "PATH" | "CHUNK[INT]"
d.name                          # str — the parameter name
d.range                         # see table above
```

For lists where the element type is `int`/`float`/`FormatString`, the
list-form vs format-string-form is dispatched by the binding: the
`.range` getter returns either a Python list (literal range) or a
`FormatString` (e.g. `"1-10:2"`, possibly carrying a
`{{Param.X}}` interpolation under the EXPR extension). Only `INT` and
`CHUNK[INT]` accept the list-form `[1, 2, 3]`; the others always carry
`FormatString` elements (which may themselves be literal or
interpolating).

The `CHUNK[INT]` variant additionally exposes:

```python
chunks = chunk_int_def.chunks   # ChunksDefinition
chunks.default_task_count       # int | FormatString  (alias: defaultTaskCount)
chunks.target_runtime_seconds   # Optional[int | FormatString] (alias: targetRuntimeSeconds)
chunks.range_constraint         # "CONTIGUOUS" or "NONCONTIGUOUS" (alias: rangeConstraint)
```

The combination expression on the parameter space is exposed as a raw
string (no AST):

```python
ps = step.parameter_space
ps.combination                  # Optional[str], e.g. "Param1 * (Param2, Param3)"
```

When the field is absent, `combination` is `None` and the resolver
defaults to a left-to-right product over the
`task_parameter_definitions` list.

### `JobParameterDefinition` (12 typed variants)

`JobTemplate.parameter_definitions` and
`EnvironmentTemplate.parameter_definitions` return
`Optional[list[JobParameterDefinition]]`, where each element is one
of twelve typed pyclasses, mirroring the runtime
`JobParameterDefinition` Rust enum 1:1:

| Variant | Pyclass | `default` type |
|---|---|---|
| `STRING` | `JobStringParameterDefinition` | `Optional[str]` |
| `INT` | `JobIntParameterDefinition` | `Optional[int]` |
| `FLOAT` | `JobFloatParameterDefinition` | `Optional[float]` |
| `PATH` | `JobPathParameterDefinition` | `Optional[str]` |
| `BOOL` (EXPR) | `JobBoolParameterDefinition` | `Optional[bool]` |
| `RANGE_EXPR` (EXPR) | `JobRangeExprParameterDefinition` | `Optional[str]` |
| `LIST[STRING]` (EXPR) | `JobListStringParameterDefinition` | `Optional[list[str]]` |
| `LIST[PATH]` (EXPR) | `JobListPathParameterDefinition` | `Optional[list[str]]` |
| `LIST[INT]` (EXPR) | `JobListIntParameterDefinition` | `Optional[list[int]]` |
| `LIST[FLOAT]` (EXPR) | `JobListFloatParameterDefinition` | `Optional[list[float]]` |
| `LIST[BOOL]` (EXPR) | `JobListBoolParameterDefinition` | `Optional[list[bool]]` |
| `LIST[LIST[INT]]` (EXPR) | `JobListListIntParameterDefinition` | `Optional[list[list[int]]]` |

Common attributes:

```python
d = template.parameter_definitions[0]
d.type                          # JobParameterType enum
d.name                          # str
d.description                   # Optional[str]
d.default                       # see table above
```

Type-specific attributes:

```python
# STRING / PATH variants:
d.allowed_values                # Optional[list[str]] (alias: allowedValues)
d.min_length                    # Optional[int]      (alias: minLength)
d.max_length                    # Optional[int]      (alias: maxLength)
# PATH only:
d.object_type                   # Optional["FILE" | "DIRECTORY"]  (alias: objectType)
d.data_flow                     # Optional["NONE" | "IN" | "OUT" | "INOUT"]  (alias: dataFlow)

# INT / FLOAT variants:
d.allowed_values                # Optional[list[int|float]]
d.min_value                     # Optional[int|float]  (alias: minValue)
d.max_value                     # Optional[int|float]  (alias: maxValue)

# LIST[*] variants (all): min_length / max_length
# LIST[PATH] variant: also object_type / data_flow
# RANGE_EXPR variant: min_length / max_length
# BOOL variant: only the common attributes
```

### `userInterface` types

Each `Job*ParameterDefinition` exposes a `user_interface` getter
(camelCase alias `userInterface`) that returns
`Optional[<TypedUserInterface>]`. The pyclass type returned is
specific to the parameter variant — see the table below. All UI
pyclasses share three common fields: `control: Optional[str]`,
`label: Optional[str]`, `group_label: Optional[str]` (camelCase
alias `groupLabel`).

| Job parameter variant | UI pyclass | Type-specific fields |
|---|---|---|
| `STRING` | `StringUserInterface` | (none) |
| `INT` | `IntUserInterface` | `single_step_delta: Optional[int]` |
| `FLOAT` | `FloatUserInterface` | `decimals: Optional[int]`, `single_step_delta: Optional[float]` |
| `PATH` | `PathUserInterface` | `file_filters: Optional[list[FileFilter]]`, `file_filter_default: Optional[FileFilter]` |
| `BOOL` (EXPR) | `BoolUserInterface` | (none) |
| `RANGE_EXPR` (EXPR) | `RangeExprUserInterface` | (none) |
| `LIST[STRING]`, `LIST[BOOL]` (EXPR) | `ListSimpleUserInterface` | (none) |
| `LIST[PATH]` (EXPR) | `ListPathUserInterface` | `file_filters`, `file_filter_default` (same as `PathUserInterface`) |
| `LIST[INT]` (EXPR) | `ListIntUserInterface` | `single_step_delta: Optional[int]` |
| `LIST[FLOAT]` (EXPR) | `ListFloatUserInterface` | `decimals`, `single_step_delta` (same as `FloatUserInterface`) |
| `LIST[LIST[INT]]` (EXPR) | `HiddenOnlyUserInterface` | (none) |

Multi-word getters have camelCase aliases:
`groupLabel`/`singleStepDelta`/`fileFilters`/`fileFilterDefault`.

Example:

```python
from openjd.model._v1.template import (
    JobIntParameterDefinition, IntUserInterface,
)
d = template.parameter_definitions[0]
if isinstance(d, JobIntParameterDefinition) and d.user_interface is not None:
    ui: IntUserInterface = d.user_interface
    ui.control                  # e.g. "SPIN_BOX" or "DROPDOWN_LIST"
    ui.label                    # Optional[str]
    ui.group_label              # Optional[str] (alias: groupLabel)
    ui.single_step_delta        # Optional[int] (alias: singleStepDelta)
```

The `control` field is preserved as a free-form `Optional[str]`;
the spec defines per-variant validation (e.g. `INT` accepts
`SPIN_BOX`/`DROPDOWN_LIST`/`HIDDEN`, `LIST[INT]` accepts
`SPIN_BOX_LIST`/`HIDDEN`, etc.) that the decoder enforces at
template-decode time.

### `FileFilter`

```python
ff = path_ui.file_filters[0]
ff.label                        # str
ff.patterns                     # list[str], e.g. ["*.png", "*.jpg"]
```

## Iteration Types (from Rust)

### `StepParameterSpaceIterator`

Iterate over task parameter combinations for a step.

```python
from openjd.model._v1.job import StepParameterSpaceIterator

it = StepParameterSpaceIterator(step=job.steps[0])
# or: it = StepParameterSpaceIterator(space=step.parameterSpace)
# or, to walk a chunked space one task at a time:
#     it = StepParameterSpaceIterator(space=..., chunks_task_count_override=1)

len(it)                     # total task count, e.g. 10
it[0]                       # {"Frame": 1}
it[-1]                      # {"Frame": 10}
for params in it:
    print(params["Frame"])  # 1, 2, 3, ...

it.names                    # {"Frame"} — property, not callable
it.chunks_adaptive          # bool
it.chunks_parameter_name    # Optional[str]
it.chunks_default_task_count  # Optional[int]

it.reset_iter()             # rewind to position 0; subsequent
                            # for/next iteration yields the first
                            # combination again
```

`reset_iter()` is useful for callers that want to re-walk the same
parameter space without rebuilding the iterator (the iterator caches
non-trivial state for chunked spaces). Indexing (``it[i]``) is
unaffected by iteration position; ``__contains__`` is also
non-mutating.

`chunks_task_count_override` replaces the `defaultTaskCount` of a
`CHUNK[INT]` parameter and turns adaptive chunking off, so a chunked
space can be walked at a granularity the caller picks. Pass `1` to
iterate individual tasks — a `1-20` range chunked five at a time then
yields `1-1`, `2-2`, … instead of `1-5`, `6-10`, …. It is ignored when
the space has no chunked parameter, matching the pure-Python reference,
although a non-positive value is still rejected in that case.
Iteration observes it, and `len()` counts the overridden granularity.

The rendered form of a chunk depends on `rangeConstraint`, which matters
because these are strings a consumer parses and may feed back through
`__contains__`. A single-task chunk is `"1-1"` under `CONTIGUOUS` and a
bare `"1"` under `NONCONTIGUOUS`.

It is currently the only way to change the chunk size of a *static*
chunked space: the `chunks_default_task_count` setter accepts adaptive
spaces only, and raises `ValueError` otherwise.

Any non-positive value raises `ValueError`, so one `except ValueError`
covers `0` and negatives alike. The Rust layer clamps the override to at
least 1, so 0 would otherwise silently mean 1, and the
`chunks_default_task_count` setter already rejects it. The pure-Python
reference does not validate this argument.

Indexing observes the override. `openjd-model` 0.6.0 gave a `CONTIGUOUS`
chunked space random access, so `it[i]` answers there as it does for a
`NONCONTIGUOUS` one, and reports the overridden granularity rather than
the template's.

One current-implementation limitation remains. An *adaptive* space has no
knowable count until it is walked, so `len(it)` raises `ValueError` and
every index — including `-1` — raises `IndexError`. Iteration still
yields, which is what distinguishes an unknown count from an empty space.
Supplying the override makes the space static and lifts both.

### `StepDependencyGraph`

Step dependency graph for topological ordering.

```python
from openjd.model._v1.job import StepDependencyGraph

graph = StepDependencyGraph(job=job)
graph.topo_sorted()         # [Step(name="Render"), Step(name="Composite")] — dependency order
graph.step_names()          # ["Render", "Composite"]
```

`topo_sorted()` returns the actual ``Step`` pyclass objects (so callers
can read parameters, dependency lists, etc. without re-indexing).
``step_names()`` is a convenience that returns just the names.

## Enums

### `DocumentType` (Rust)

```python
from openjd.model._v1.types import DocumentType
DocumentType.JSON
DocumentType.YAML
```

### `TemplateSpecificationVersion` (Rust pyclass, str-Enum-like)

A Rust pyclass enum exposed at `openjd._openjd_rs` (re-exported from
`openjd.model._v1`). The variant naming and behaviour match the v0
Python `str`-Enum: lowercase variant names, `.value` returns the
spec form, equality with the spec-form string works, and the
constructor accepts either the spec form or the variant name.
The class is *not* a `str` subclass — `isinstance(tsv, str)` is
`False`. For string operations call `str(tsv)` or `tsv.value`.

```python
from openjd.model._v1 import TemplateSpecificationVersion as TSV

TSV.JOBTEMPLATE_v2023_09                # repr: TemplateSpecificationVersion.JOBTEMPLATE_v2023_09
TSV.JOBTEMPLATE_v2023_09.value          # "jobtemplate-2023-09"
TSV.JOBTEMPLATE_v2023_09.name           # "JOBTEMPLATE_v2023_09"
str(TSV.JOBTEMPLATE_v2023_09)           # "jobtemplate-2023-09"
TSV.JOBTEMPLATE_v2023_09 == "jobtemplate-2023-09"  # True
TSV("jobtemplate-2023-09")              # TSV.JOBTEMPLATE_v2023_09
TSV("JOBTEMPLATE_v2023_09")             # TSV.JOBTEMPLATE_v2023_09
TSV.JOBTEMPLATE_v2023_09.is_job_template()       # True
TSV.JOBTEMPLATE_v2023_09.is_environment_template()  # False
```

### `JobParameterType` (Rust)

```python
from openjd.model._v1.types import JobParameterType
JobParameterType.STRING     # STRING, INT, FLOAT, PATH, BOOL, RANGE_EXPR
JobParameterType.LIST_INT   # LIST_STRING, LIST_INT, LIST_FLOAT, LIST_PATH, LIST_BOOL, LIST_LIST_INT
```

### `TaskParameterType` (Rust)

```python
from openjd.model._v1.types import TaskParameterType
TaskParameterType.INT       # INT, FLOAT, STRING, PATH, CHUNK_INT
```

### `SpecificationRevision` (Rust pyclass, str-Enum-like)

A Rust pyclass enum exposed at `openjd._openjd_rs` (re-exported from
`openjd.model._v1`). The variant naming and behaviour match the v0
Python `str`-Enum: lowercase variant names, `.value` returns the
spec form, and equality with the spec-form string works. The class
is *not* a `str` subclass — `isinstance(rev, str)` is `False`. For
string operations call `str(rev)` or `rev.value`.

```python
from openjd.model._v1 import SpecificationRevision

SpecificationRevision.v2023_09          # repr: SpecificationRevision.v2023_09
SpecificationRevision.v2023_09.value    # "2023-09"
SpecificationRevision.v2023_09.name     # "v2023_09"
str(SpecificationRevision.v2023_09)     # "2023-09"
SpecificationRevision.v2023_09 == "2023-09"  # True
hash(SpecificationRevision.v2023_09) == hash("2023-09")  # True (set/dict membership works)
```

## Simple Types (Python)

Parameter values are represented by the Rust pyclasses
`JobParameterValue` and `TaskParameterValue` (see `openjd.model._v1.types`).
Both have the same shape: kw-only ``type=`` and ``value=`` constructors,
plus ``__eq__`` / ``__hash__`` / ``__repr__`` / pickle support.

```python
from openjd.model._v1.types import (
    JobParameterType, JobParameterValue,
    TaskParameterType, TaskParameterValue,
)

# A job parameter value with its type
jpv = JobParameterValue(type=JobParameterType.STRING, value="hello")

# A task parameter value (note: only TaskParameterType has CHUNK_INT)
tpv = TaskParameterValue(type=TaskParameterType.INT, value="5")
```

The v0 names ``ParameterValue`` and ``ParameterValueType`` are
**not** part of the v1 API. ``ParameterValueType`` was a bare alias
for ``JobParameterType``, and ``ParameterValue`` was a Python class
with no built-in distinction between job- and task-parameter contexts —
both have been removed in favor of the typed Rust pyclasses above.

## Profile

### `ModelProfile` / `ModelExtension` / `SpecificationRevision` / `CallerLimits` / `ValidationContext`

Profile types that describe what features a template or job uses.
Mirror the equivalent types in the underlying `openjd-model` Rust crate.

`decode_*_template` does **not** take a `ModelProfile` — it takes a
`supported_extensions: list[str]` allowlist (see [Decode](#decode)
above), matching the Rust API. `ModelProfile` is an *output* of
decoding (read it off `JobTemplate.profile`) and an *input* to
`create_job(validation_context=...)` and to the bridge to the
expression engine.

```python
from openjd.model._v1 import (
    ModelProfile, SpecificationRevision,
    CallerLimits,
    decode_job_template, create_job,
)
from openjd.model._v1.types import ModelExtension, ValidationContext

# 1. Decode a template using the string-list allowlist (Rust-aligned).
template = decode_job_template(template={...}, supported_extensions=["EXPR"])

# 2. Read the template's declared profile back out.
profile = template.profile        # ModelProfile(revision=V2023_09, extensions=[EXPR])
profile.revision                  # SpecificationRevision.V2023_09
profile.extensions                # [ModelExtension.EXPR]
profile.has_extension(ModelExtension.EXPR)  # True

# 3. Build it manually if needed (e.g. when validating against a different
#    policy than the template declared).
manual = ModelProfile(extensions=[ModelExtension.EXPR, ModelExtension.TASK_CHUNKING])
ModelProfile.from_strings(SpecificationRevision.V2023_09, ["EXPR"])

# 4. Pass to create_job through a ValidationContext if you want to
#    override the template's default validation context.
limits = CallerLimits(max_step_count=100, max_task_count=10_000)
ctx = ValidationContext(profile, caller_limits=limits)
job = create_job(
    job_template=template,
    job_parameter_values={...},
    validation_context=ctx,   # optional; defaults to template.default_validation_context()
)

# 5. Bridge to the expression engine.
from openjd.expr import HostContext
expr_profile = profile.to_expr_profile(HostContext.unresolved())
```

`ModelExtension` members:

| Member | String form | Notes |
|---|---|---|
| `TASK_CHUNKING` | `"TASK_CHUNKING"` | RFC 0001 |
| `REDACTED_ENV_VARS` | `"REDACTED_ENV_VARS"` | RFC 0003 |
| `FEATURE_BUNDLE_1` | `"FEATURE_BUNDLE_1"` | RFC 0004 |
| `EXPR` | `"EXPR"` | RFC 0005 |

## Names removed from v0

> **Note.** v0 (`openjd.model`) exposed a number of names that are
> deliberately not carried forward into v1: the structural classes
> `CancelationMethodTerminate`, `CancelationMethodNotifyThenTerminate`,
> `CompatibilityError`, `CommandString`, `ArgString`,
> `EmbeddedFileText`, `EmbeddedFiles`, `StepDependencyGraphNode`,
> `StepDependencyGraphStepToStepEdge`, `ValueReferenceConstants`,
> `FormatStringError`, `IntRangeExpr`, the `openjd.expr` re-exports
> `SymbolTable`, `FormatString`, `RangeExpr`, `ExpressionError`,
> and a set of opaque type aliases (`JobParameterValues`,
> `JobParameterInputValues`, `TaskParameterSet`,
> `JobParameterDefinition`, `OpenJDModel`). v0 callers should
> remain on `openjd.model`; v1 callers should import structural
> pyclasses from their canonical submodules (`_v1.template`,
> `_v1.job`, `_v1.types`, `_v1.errors`) and expression-layer types
> from `openjd.expr` directly. Where v0 callers used the opaque
> type aliases, v1 callers should use the concrete typed forms
> instead — e.g. `dict[str, JobParameterValue]` in place of
> `JobParameterValues`, `dict[str, str]` in place of
> `JobParameterInputValues`, `dict[str, TaskParameterValue]` in
> place of `TaskParameterSet`, and the specific concrete pyclass
> (`JobStringParameterDefinition`, `JobIntParameterDefinition`,
> etc.) in place of `JobParameterDefinition`. There is no v1
> equivalent of `OpenJDModel`: `JobTemplate` and
> `EnvironmentTemplate` are independent PyO3 pyclasses with no
> shared base class.

### Behavior change: `RangeExpr` iteration is always ascending

`openjd.expr.RangeExpr` always presents its values as an **increasing
list of integers**, regardless of how the source expression was
written. Iteration, indexing, and `__str__` all operate on the
canonical ascending form; the input's direction is not retained.

```python
from openjd.expr import RangeExpr

r = RangeExpr("-1 - -2 : -1")
list(r)   # [-2, -1]   (ascending)
r[0]      # -2
r[-1]     # -1

r = RangeExpr("10-1:-1")
list(r)   # [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  (ascending)
```

This differs from the v0 pure-Python reference implementation
(`openjd.model._range_expr.IntRangeExpr`), which preserves the
user-supplied direction so that `IntRangeExpr.from_str("-1 - -2 : -1")`
iterates as `[-1, -2]`. The Rust-backed binding intentionally drops
that direction-preserving behavior because every consumer of
`RangeExpr` in the model layer treats a range as an unordered set of
integers, and the canonical form eliminates a class of edge cases
from indexing and length arithmetic. See
`openjd-rs/specs/expr/range-expr.md` ("Internal Representation") for
the underlying design rationale.

Practical consequences:

- Code that constructs a descending range expression and depends on
  iteration yielding values in descending order must sort the result
  itself, or build the expected ordering from the parsed `(start, end,
  step)` tuples.
- INT and CHUNK[INT] task parameters defined with a descending range
  (e.g. `"10-1:-1"`) iterate frames in ascending order under the Rust
  bindings.
- `__contains__`, `__len__`, and equality (`==`) are unaffected:
  `RangeExpr` equality is set-based.

## Exceptions

```python
from openjd.model._v1 import decode_job_template
from openjd.model._v1.errors import DecodeValidationError, ModelValidationError

# Invalid template — schema-level failure (missing required top-level
# key) raises DecodeValidationError. These are the failures the
# binding can detect before the dict is reshaped into the typed
# model, so they don't need to run through the model validator.
try:
    decode_job_template(template={"bad": "template"})
except DecodeValidationError as e:
    str(e)  # "Template is missing Open Job Description schema version key: specificationVersion"

# Empty steps — model-level structural failure raises
# ModelValidationError. The shape parses successfully but the
# decoded JobTemplate fails the "at least one step" invariant when
# the model validator runs, so the failure surfaces under
# ModelValidationError rather than DecodeValidationError. See the
# divergence note below.
try:
    decode_job_template(template={
        "specificationVersion": "jobtemplate-2023-09",
        "name": "Test",
        "steps": [],
    })
except ModelValidationError as e:
    str(e)  # "1 validation error for JobTemplate\nJobTemplate: must have at least one step."
```

| Exception | Base |
|---|---|
| `DecodeValidationError` | `ValueError` |
| `ModelValidationError` | `ValueError` |
| `UnsupportedSchema` | `ValueError` |
| `ExpressionError` | `ValueError` |

**`DecodeValidationError` vs `ModelValidationError` divergence from v0.**
The v0 (Pydantic) reference raised ``DecodeValidationError`` for *every*
template-decode failure — including model-level structural invariants
like "must have at least one step" — because pydantic's discriminated-
union dispatch ran the field validators inside the decode call. The v1
binding splits the two phases: ``DecodeValidationError`` is raised
strictly for schema-level failures the binding can detect before
constructing the typed model (missing/unknown ``specificationVersion``,
unknown fields under strict mode, unparseable JSON/YAML, etc.), and
``ModelValidationError`` is raised for everything caught by the model
validator that runs once the decoded shape is in hand (the at-least-one-
step rule, parameter-definition invariants, step-name uniqueness, etc.).
Both classes inherit ``ValueError``, so callers that catch ``ValueError``
are unaffected — only callers that distinguish between the two classes
need to be aware of the split. The v1 binding **deliberately** does not
remap empty-steps to ``DecodeValidationError`` for v0 byte-parity: the
v1 model validator is the right home for the check (it surfaces with the
same path-prefixed message shape as every other model-level invariant),
and callers wanting to catch every decode-time failure should catch
``ValueError`` or both classes by tuple (``except (DecodeValidationError,
ModelValidationError)``).

**`UnsupportedSchema` constructor divergence from v0.** The v0
reference defines ``UnsupportedSchema(version_str)`` such that
``str(e) == "Unsupported schema version: {version_str}"`` and the
instance carries a private ``_version`` attribute. The v1 binding
treats the constructor argument as the message itself —
``UnsupportedSchema(msg)`` produces ``str(e) == msg`` and no
``_version`` attribute is exposed. The exception class identity
and the ``ValueError`` base are preserved, so any v0 caller that
catches ``UnsupportedSchema`` (or its base) still catches v1's
``UnsupportedSchema``; only callers that introspect the message
or read ``_version`` will see the difference. The Rust
``openjd_model::ModelError::UnsupportedSchema`` already crafts a
human-readable message at the source — re-wrapping it in the
v0 template would be redundant.

**Validation error messages are not byte-identical to v0.** The
v0 reference's ``ModelValidationError`` /
``DecodeValidationError`` messages are derived from Pydantic and
inherit Pydantic's phrasing — including the well-known
pluralisation typo (``"1 validation errors for ..."`` for the
single-error case), template strings like ``"Parameter 'X':
value Y exceeds maximum Z"``, and Pydantic's loc-tuple
formatting for the field path. The v1 binding produces messages
from the Rust crate's own validator, which uses a stricter and
more concise phrasing — correct singular/plural agreement
(``"1 validation error for ..."``), and shorter operator-anchored
phrasings like ``"Value (Y) for parameter X must be at most Z."``.

Match by exception class and the field path inside the message
(both bindings emit the path-prefix shape
``steps[0] -> script -> actions -> onRun -> command:\\n\\tmust not be empty.``)
rather than by literal message bytes. Downstream tooling that
greps the entire message for v0 wording will need to update its
patterns; tooling that catches the exception class and reads
``e.field`` / ``e.location`` (where exposed) will continue to
work.

## Pickle Support

The following value types are pickleable. Pickled state round-trips
through ``pickle.dumps`` / ``pickle.loads`` and compares equal to the
original.

| Type | Reduces through |
|---|---|
| ``DocumentType`` | variant name (``YAML`` / ``JSON``) |
| ``JobParameterType`` | variant name (``INT``, ``LIST_PATH``, …) |
| ``TaskParameterType`` | variant name (``INT``, ``CHUNK_INT``, …) |
| ``ModelExtension`` | variant name (``EXPR``, ``TASK_CHUNKING``, …) |
| ``ModelProfile`` | constructor arguments (``revision``, ``extensions``) |
| ``CallerLimits`` | constructor arguments (six optional fields) |
| ``ValidationContext`` | constructor arguments (``profile``, ``caller_limits``) |
| ``JobParameterValue`` | constructor arguments (``type``, ``value``) |
| ``TaskParameterValue`` | constructor arguments (``type``, ``value``) |
| ``IntTaskParameter`` | constructor argument (``range``) |
| ``FloatTaskParameter`` | constructor argument (``range``) |
| ``StringTaskParameter`` | constructor argument (``range``) |
| ``PathTaskParameter`` | constructor argument (``range``) |
| ``ChunkIntTaskParameter`` | constructor arguments (``range``, ``chunks``) |
| ``TaskChunksDefinition`` | constructor arguments (three fields) |
| ``SpecificationRevision`` | variant name (``v2023_09``) |
| ``TemplateSpecificationVersion`` | variant name (``JOBTEMPLATE_v2023_09``, ``ENVIRONMENT_v2023_09``) |
| ``DecodeValidationError``, ``ModelValidationError``, ``UnsupportedSchema`` | standard exception pickle, under their canonical ``openjd.model._v1`` module path |

``SpecificationRevision`` and ``TemplateSpecificationVersion`` are Rust
pyclass enums whose canonical home is ``openjd._openjd_rs``; they are
re-exported from ``openjd.model._v1`` (identity-preserving — there is
exactly one class in each case). Pickled instances round-trip through
the variant name via the module-level ``_reconstruct_enum`` helper.

The decoded model containers (``JobTemplate``, ``EnvironmentTemplate``,
``Job``, ``Step``, etc.) and the live ``StepParameterSpaceIterator`` /
``StepDependencyGraph`` types are **not pickleable**, and there are no
plans to add pickle support to them. The intended round-trip path for a
decoded template is to keep the source document around (or its parsed
``dict``) and re-decode it on the other side; the decoded model object
is not designed to act as a wire format.

If a specific sub-model needs to cross a process boundary or be cached
to disk, the recommendation is to pickle (or otherwise serialise) the
inputs that produced it — the template ``dict`` and the
``job_parameter_values`` for ``Job``, etc. — rather than the model
itself. Targeted helpers will be considered case-by-case if a concrete
serialisation need arises that cannot be met by re-decoding.


## Bindings-internal helpers

The following functions are exposed by the underlying Rust extension
module ``openjd._openjd_rs`` but are **not** re-exported through the
``openjd.model._v1`` wrapper. They exist to support the openjd-sessions
runtime and the Deadline Cloud worker agent's wire-protocol decode
path; ordinary template/job consumers should not need them. They are
"subject to change" — signatures and semantics may evolve as the
runtime layer matures.

### `_openjd_rs.create_environment`

Convert a template-time ``EnvironmentTemplate`` into a job-time
``Environment``. Used by the sessions runtime when a session attaches
an externally-defined environment (queue environment, host
environment) to the job it's about to run.

```python
from openjd._openjd_rs import create_environment

env = create_environment(env_template)  # template-time → job-time
```

### `_openjd_rs.deserialize_step`

Reconstruct a job-side ``Step`` from the wire-protocol dict shape
that the Deadline Cloud service's ``GetStepDetails`` /
``BatchGetJobEntity`` API returns in the ``template`` field. The
payload is a serialised ``openjd_model::job::Step`` (i.e. a
*resolved* step, not a template-time ``StepTemplate``).

```python
from openjd._openjd_rs import deserialize_step

step = deserialize_step(step_dict_from_service)
session.run_task(step.script, ...)
```
