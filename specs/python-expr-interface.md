# Python Expression Language Interface (`openjd.expr`)

Rust-backed implementation of the Open Job Description expression language
([EXPR extension](https://github.com/OpenJobDescription/openjd-specifications/wiki/2026-02-Expression-Language)).

## Functions

### `evaluate_expression`

Evaluate an expression string and return the result.

```python
from openjd.expr import evaluate_expression, SymbolTable, ExprType, PathFormat

# Simple arithmetic
evaluate_expression("1 + 2").item()  # 3

# With variables
st = SymbolTable({"Param.Frame": 42, "Param.Name": "render"})
evaluate_expression("Param.Frame * 2", values=st).item()  # 84
evaluate_expression("Param.Name.upper()", values=st).item()  # "RENDER"

# Conditional
evaluate_expression("'high' if Param.Frame > 100 else 'low'", values=st).item()  # "low"

# List comprehension
evaluate_expression("[x * 2 for x in range(5)]").item()  # [0, 2, 4, 6, 8]

# With target type coercion
evaluate_expression("[1, 2, 3]", target_type=ExprType("list[string]")).item()  # ["1", "2", "3"]

# With resource limits
evaluate_expression("sum(range(100))", operation_limit=50)  # raises ExpressionError

# With path format
evaluate_expression("path('/a/b').name", path_format=PathFormat.POSIX).item()  # "b"
```

### `parse_expression`

Parse an expression without evaluating it. Inspect symbol references and function calls.

```python
from openjd.expr import parse_expression

parsed = parse_expression("Param.Start + len(Param.Items)")
parsed.accessed_symbols   # {"Param.Start", "Param.Items"}
parsed.called_functions   # {"len"}
parsed.local_bindings     # set()

# Evaluate later with different values
result = parsed.evaluate(values={"Param.Start": 10, "Param.Items": [1, 2, 3]})
result.item()  # 13

# Or, inspect resource usage of a single evaluation by calling
# `evaluate_with_metrics` instead — it returns an `EvalResult` that
# bundles the value with the per-call peak-memory and operation-count
# counters.
metered = parsed.evaluate_with_metrics(values={"Param.Start": 10, "Param.Items": [1, 2, 3]})
metered.value.item()       # 13
metered.peak_memory        # bytes used (>= 0)
metered.operation_count    # operations performed (>= 0)
```

### `escape_format_string`

Escape `{{` and `}}` in a string for use as a literal in a format string.

```python
from openjd.expr import escape_format_string

escape_format_string("use {{braces}}")  # 'use {{ "{{" }}braces{{ "}" + "}" }}'
```

## Types

### `ExprType`

Represents a type in the expression language. The type system includes
primitives (`int`, `float`, `string`, `bool`, `path`), compound types
(`list[T]`, `range_expr`), unions (`int | string`), nullable (`int?`),
and type variables (`T`, `T1`, `T2`, `T3`) for generic function signatures.

`ExprType` instances are constructed from the spec-form string
(`ExprType("bool")`, `ExprType("list[int]")`, `ExprType("int | string")`)
or from a `(TypeCode, type_params)` tuple
(`ExprType(TypeCode.LIST, [ExprType("int")])`). The binding deliberately
**does not** expose class-level shortcut constants such as
`ExprType.BOOL` or `ExprType.LIST_INT`; the string form is the single
canonical way to refer to a type and round-trips through
`str(t)` / `ExprType(str(t))`.

```python
from openjd.expr import ExprType, TypeCode

# Construction from string
ExprType("int")                           # int
ExprType("list[int]")                     # list[int]
ExprType("int?")                          # int | nulltype (nullable)
ExprType("int | string")                  # union
ExprType("list[list[int]]")               # nested list

# Construction from TypeCode
ExprType(TypeCode.LIST, [ExprType("int")])  # list[int]

# Properties
t = ExprType("list[int]")
t.type_code                               # TypeCode.LIST
t.type_params                             # [ExprType("int")]
str(t)                                    # "list[int]"

# Methods
ExprType("int").nullable()                # ExprType("int | nulltype")
ExprType("int?").is_nullable()            # True
ExprType("int").is_concrete()             # True
ExprType("T").is_symbolic()               # True

# Static constructors
ExprType.list(ExprType("int"))            # list[int]
ExprType.union([ExprType("int"), ExprType("string")])  # int | string

# Generic type matching (for function signature dispatch).
# Named `match_type` rather than `match` to mirror the underlying
# Rust API (where `match` is a reserved keyword). The pure-Python
# v0 reference called this `match`; consumers porting from v0 must
# rename their call site.
generic = ExprType(TypeCode.LIST, [ExprType("T")])
concrete = ExprType("list[int]")
bindings = generic.match_type(concrete)   # {TypeCode.TYPEVAR_T: ExprType("int")}
generic.substitute(bindings)              # ExprType("list[int]")
```

### `TypeCode`

Enum identifying the kind of an `ExprType`.

```python
from openjd.expr import TypeCode

TypeCode.INT          # integer type
TypeCode.LIST         # list type (parameterized)
TypeCode.UNRESOLVED   # placeholder for unknown values during type checking
```

**Members:** `NULLTYPE`, `BOOL`, `INT`, `FLOAT`, `STRING`, `PATH`, `LIST`,
`RANGE_EXPR`, `ANY`, `UNION`, `NORETURN`, `UNRESOLVED`, `TYPEVAR_T`,
`TYPEVAR_T1`, `TYPEVAR_T2`, `TYPEVAR_T3`

> **Not an `IntEnum` subclass.** The pure-Python reference declares
> `class TypeCode(IntEnum)`; the Rust-backed binding is a pyo3 enum
> that compares equal to its integer discriminant
> (`TypeCode.INT == 2`) and converts cleanly via `int(TypeCode.INT)`,
> but it is **not** an `int` subclass. `isinstance(TypeCode.INT, int)`
> returns `False`. Code that ducks-types a `TypeCode` as an integer
> via `isinstance(..., int)` checks should switch to
> `isinstance(..., TypeCode)` or to value comparison
> (`code == TypeCode.INT`).
>
> **Iteration and value-lookup operations from `IntEnum` are not
> supported.** `list(TypeCode)`, `for tc in TypeCode: ...`,
> `TypeCode["INT"]`, and `TypeCode(2)` (look up by discriminant)
> all raise `TypeError` on the Rust-backed binding — the pyo3 enum
> protocol exposes the variants as class attributes only. Use
> direct attribute access (`TypeCode.INT`, `TypeCode.LIST`, …) and,
> where a stable ordered iteration is needed, an explicit tuple of
> the members defined above.

### `ExprValue`

A typed value during expression evaluation. Wraps Rust `ExprValue`.

```python
from openjd.expr import ExprValue, PathFormat
from decimal import Decimal

# Construction from Python values
ExprValue(42)                             # Int
ExprValue(3.14)                           # Float
ExprValue("hello")                        # String
ExprValue(True)                           # Bool
ExprValue(None)                           # Null
ExprValue([1, 2, 3])                      # list[int]
ExprValue(Decimal("3.140"))               # Float preserving "3.140"

# Type coercion
ExprValue("42", type="int")               # Int(42)
ExprValue("/tmp", type="path", path_format=PathFormat.POSIX)  # Path
ExprValue("1-5", type="range_expr")       # RangeExpr

# Special constructors
ExprValue.from_float(3.14)                # Float (canonical Display form: "3.14")
ExprValue.from_float(3.14, "3.140")       # Float preserving original string
ExprValue.from_float(Decimal("1.00"))     # Float; auto-captures the Decimal's
                                          # string form, so str() shows "1.00"
                                          # (matches ExprValue(Decimal(...)))
ExprValue.unresolved("int")               # Unresolved placeholder for type checking

# Properties
v = ExprValue(42)
v.type                                    # ExprType("int")
v.type.type_code                          # TypeCode.INT
v.is_null                                 # False
v.item()                                  # 42 (native Python value)
v.memory_size()                           # bytes used (Rust ExprValue + heap)
str(v)                                    # "42"
bool(v)                                   # True

# Sequence protocols for list and range_expr values
v = ExprValue([10, 20, 30])
len(v)                                    # 3
v[0].item()                               # 10
v[-1].item()                              # 30
[e.item() for e in v]                     # [10, 20, 30]
```

**Null values.** `ExprValue(None)` is the canonical way to construct
a null-typed value. The binding does **not** expose a separate
`ExprValue.null()` classmethod — the v0 reference's `.null()`
helper is replaced by passing `None` to the main constructor:

```python
v = ExprValue(None)
v.type                                    # ExprType("nulltype")
v.type.type_code                          # TypeCode.NULLTYPE
v.is_null                                 # True
v.item()                                  # None
str(v)                                    # "null"
bool(v)                                   # False
```

Callers porting from the pure-Python reference should rewrite
`ExprValue.null()` to `ExprValue(None)`. The two produce the same
shape (NullType, ``is_null=True``, ``item()`` returns ``None``); the
classmethod was a stylistic alias the binding deliberately omitted to
keep the constructor surface narrow.

**Unresolved values.** `ExprValue.unresolved(T)` constructs a typed
placeholder used during static type checking when a symbol's
concrete value isn't yet known. The placeholder participates in
type checking but has no extractable Python value:

```python
v = ExprValue.unresolved("int")
v.type                                    # ExprType("unresolved[int]")
v.item()                                  # raises ExpressionTypeError
str(v)                                    # raises ExpressionTypeError
repr(v)                                   # 'ExprValue.unresolved(ExprType("int"))'
                                          # (repr is for debugging — never raises)
```

`item()` and `str()` raise `ExpressionTypeError` on an unresolved
value because there's no real value to extract or render. `repr()`
is the documented exception: it returns a debug-friendly string and
never raises (Python convention). This makes unresolved values
safe to inspect in debuggers and tracebacks while still failing
loudly anywhere a real value is expected.

### `SymbolTable`

Hierarchical key-value store providing variable bindings for expression
evaluation. Supports dotted paths that create nested tables automatically.

```python
from openjd.expr import SymbolTable, ExprValue

# Construction
st = SymbolTable({"Param.Frame": 42, "Param.Name": "test"})
st = SymbolTable({"Param": {"Frame": 42}})       # nested dict
st = SymbolTable(source=other_symtab)             # copy

# Access
"Param.Frame" in st                               # True
st["Param.Frame"].item()                          # 42
st["Param"]                                       # SymbolTable (subtable)
st.get("Missing")                                 # None
st.keys                                           # {"Param"} — top-level keys
st.symbols                                        # {"Param.Frame", "Param.Name"} — every dotted leaf path
repr(st)                                          # SymbolTable({...})

# Mutation
st["Task.Index"] = 5

# Combine with other tables / dicts (returns a new table; later
# arguments win on key collision).
combined = st.union(other_symtab, {"Extra": 1})
```

Auto-converts Python values: `int`, `float`, `str`, `bool`, `None`, `list`,
`Decimal`, `ExprValue`, `ExprType` (→ unresolved), `RangeExpr`.

`keys` returns the top-level namespaces; `symbols` returns every
fully-qualified dotted leaf path. Both are sets and are documented
alongside the Pydantic-based v0 reference whose contract this binding
preserves.

**Equality.** Two `SymbolTable`s compare equal when they contain the
same set of dotted-path → value mappings. Insertion order in the
underlying `HashMap` does not affect equality, and equality is
recursive through nested subtables. `dict` is **not** auto-coerced
for comparison — wrap it in `SymbolTable(...)` first if you want
that.

**Hashability.** `SymbolTable` is intentionally **not** hashable.
`__setitem__` is supported, so the type is mutable; Python's hash/eq
contract requires hashable types to be effectively immutable.

`union(*others)` mirrors the v0 reference's combine-tables convenience.
The Rust crate's underlying primitive is `SymbolTable::merge_from`,
which mutates in place; `union` is the immutable equivalent built on
top of it for Python ergonomics.

### `ExprRevision` / `ExprExtension` / `HostContext` / `ExprProfile`

Profile types that select which functions, operators, and types are
available for a given evaluation. Mirror the equivalent types in the
underlying `openjd-expr` Rust crate.

```python
from openjd.expr import (
    ExprProfile, ExprRevision, ExprExtension, HostContext,
    PathMappingRule, PathFormat,
)

# Empty profile: current revision, no extensions, no host context.
ExprProfile()  # same as ExprProfile.current()
ExprProfile.current()
ExprProfile.latest()  # current revision + every known extension (intentionally
                      # unstable across crate versions; use ExprProfile.current()
                      # if you want stable parse behavior)

# Builder-style — every with_* method returns a new profile.
profile = ExprProfile().with_host_context(HostContext.unresolved())

# Three host-context states, mirroring openjd_expr::HostContext:
HostContext.none()                      # default — apply_path_mapping is not registered
HostContext.unresolved()                # template-validation time — returns unresolved[T]
HostContext.with_rules([rule, ...])     # runtime — real apply_path_mapping with rules

# Predicates on a HostContext (no-arg, return bool):
HostContext.none().is_enabled()         # False — no host functions registered
HostContext.unresolved().is_enabled()   # True
HostContext.unresolved().is_unresolved()  # True — uses stub implementations
HostContext.with_rules([]).is_enabled()   # True — empty rules ≠ no host context
HostContext.with_rules([]).is_unresolved()  # False — uses real implementations

# Inspecting a profile
profile.revision      # ExprRevision.V2026_02
profile.extensions    # [] today
profile.host_context  # HostContext.unresolved()
profile.has_extension(ext)  # False today

# `ExprRevision.CURRENT` is the canonical handle for the current
# revision and tracks the upstream `ExprRevision::CURRENT` constant
# in `openjd_expr`. Today it equals `ExprRevision.V2026_02`; it
# rolls forward as new revisions ship.
ExprRevision.CURRENT                    # ExprRevision.V2026_02
ExprRevision.CURRENT == ExprRevision.V2026_02  # True
str(ExprRevision.CURRENT)               # "2026-02"
ExprRevision.CURRENT.name               # "V2026_02"
```

`ExprExtension` is empty today — no expression-level extensions exist
yet — but the type is reserved for the first one. `ExprExtension.ALL`
returns `[]` today and will grow as new variants land.

### Path-mapping in evaluation

Path-mapping rules are *part of the profile*, not a per-call kwarg. To
evaluate `apply_path_mapping(...)` against a real rule set:

```python
from openjd.expr import (
    ExprProfile, HostContext, PathFormat, PathMappingRule,
    evaluate_expression,
)

rules = [PathMappingRule(
    source_path_format=PathFormat.POSIX,
    source_path="/mnt/shared",
    destination_path="/local/cache",
)]

# Build the profile once; every entry point accepts profile=.
profile = ExprProfile().with_host_context(HostContext.with_rules(rules))

evaluate_expression(
    "apply_path_mapping('/mnt/shared/file.exr')",
    profile=profile,
).item()  # "/local/cache/file.exr"
```

For template-validation type-checking (where rules aren't known yet but
function signatures need to be) use `HostContext.unresolved()`:

```python
profile = ExprProfile().with_host_context(HostContext.unresolved())
evaluate_expression("apply_path_mapping('/p')", profile=profile)
# returns ExprValue.unresolved("path")
```

**Equality and hashability.** Both `HostContext` and `ExprProfile`
implement `__eq__` and `__hash__`.

* `HostContext` compares variant-by-variant; `with_rules` carries a
  list of `PathMappingRule`s and is compared by value (rule-by-rule
  in order, not as a set — order is meaningful for path-mapping
  resolution). Two distinct `with_rules` constructions with
  identical rule lists are equal and hash equal.
* `ExprProfile` compares on revision, extension set
  (insertion-order independent), and host context. Profiles built
  from the same arguments are equal and hash equal regardless of
  construction path. The extension set is canonicalised (sorted
  by debug repr) when hashing so set-equal extensions hash equal.

### Migration from the pure-Python reference

The Rust-backed ``openjd.expr`` deliberately drops three function-library
APIs that the pure-Python reference (``mwiebe/openjd-model-for-python``
``expr`` branch) exposed:

| Removed | Replaced by |
|---|---|
| ``FunctionLibrary`` | ``ExprProfile`` |
| ``FunctionSignature`` | (no replacement — implementation detail) |
| ``get_default_library()`` | ``ExprProfile.current()`` |

In the reference, callers built a ``FunctionLibrary`` (a mapping from
function names to ``FunctionSignature`` objects) to scope which
functions an expression could call, and passed that library plus a
``HostContext`` to every entry point — for example:

```python
# v0 reference (pure-Python): NOT how the v1 binding works.
from openjd.expr import (
    FunctionLibrary, get_default_library, HostContext, evaluate_expression,
)
library = get_default_library().with_host_context(HostContext.unresolved())
evaluate_expression("apply_path_mapping(...)", library=library)
```

The Rust-backed binding folds all three concerns — revision, extension
set, and host context — into ``ExprProfile``. The library is selected
internally from the revision + extension axes; ``FunctionSignature``
objects are no longer materialised on the Python side; and the
``library=`` kwarg is replaced by ``profile=``:

```python
# v1 binding: the only supported shape.
from openjd.expr import ExprProfile, HostContext, evaluate_expression

profile = ExprProfile().with_host_context(HostContext.unresolved())
evaluate_expression("apply_path_mapping(...)", profile=profile)
```

This is the single most visible divergence from the reference. It
trades the introspection surface (``library.signatures``,
``library.function_names``, etc.) for a smaller, builder-shaped API
whose state is fully determined by the
``(revision, extensions, host_context)`` triple. Callers that
previously relied on ``FunctionLibrary`` introspection should treat
the function set as opaque and work in terms of profile axes
instead.

### `ParsedExpression`

A parsed expression that can be inspected for symbol references and
evaluated multiple times with different values.

```python
from openjd.expr import parse_expression

parsed = parse_expression("[x.upper() for x in Param.Items if len(x) > 2]")
parsed.expr                # "[x.upper() for x in Param.Items if len(x) > 2]"
parsed.accessed_symbols    # {"Param.Items"}
parsed.called_functions    # {"upper", "len"}
parsed.local_bindings      # {"x"}

# Lightweight evaluation — returns just the value.
value = parsed.evaluate(values={"Param.Items": ["hi", "hello", "yo"]})
value.item()               # ["HELLO"]
```

`ParsedExpression` exposes two evaluation methods, mirroring the
`evaluate` / `evaluate_with_metrics` split on the underlying
`openjd_expr::ParsedExpression` Rust type:

* `evaluate(...)` returns an [`ExprValue`](#exprvalue) directly. Use this
  when you don't need resource-usage metrics — it skips the
  metric-tracking overhead.
* `evaluate_with_metrics(...)` returns an [`EvalResult`](#evalresult)
  that bundles the evaluated `ExprValue` with the per-call resource
  counters (`peak_memory` in bytes, `operation_count`).

Both methods accept the same keyword-only arguments: `values`,
`profile`, `target_type`, `path_format`, `memory_limit`,
`operation_limit`. See the [`evaluate_expression`](#evaluate_expression)
documentation for argument semantics — `ParsedExpression.evaluate` /
`evaluate_with_metrics` differ from the top-level entry point only in
that they reuse a single parse for many evaluations.

```python
from openjd.expr import parse_expression

parsed = parse_expression("sum(range(Param.N))")

# When metrics matter, use evaluate_with_metrics. The returned
# EvalResult is local to this call — concurrent or sequential calls
# do not affect each other.
r1 = parsed.evaluate_with_metrics(values={"Param.N": 1000})
r1.value.item()           # 499500
r1.peak_memory            # bytes
r1.operation_count        # ops

r2 = parsed.evaluate_with_metrics(values={"Param.N": 5})
# r1 is unchanged — its peak_memory and operation_count still reflect
# the earlier large evaluation.
r1.operation_count > r2.operation_count
```

### `EvalResult`

The structured return type of
[`ParsedExpression.evaluate_with_metrics`](#parsedexpression). Mirrors
the `EvalResult` struct in the underlying `openjd_expr` Rust crate.

```python
from openjd.expr import EvalResult, ExprValue, parse_expression

# Construction is rarely needed in user code (the binding produces the
# instance); the constructor is exposed primarily for pickle round-trip.
r = EvalResult(value=ExprValue(42), peak_memory=128, operation_count=7)

r.value             # ExprValue — the evaluation result
r.peak_memory       # int — peak bytes consumed by the evaluator
r.operation_count   # int — operations performed by the evaluator
```

`EvalResult` is a frozen value class:

* The three fields are read-only and set once at construction.
* `__eq__` compares all three fields. Value-field equality defers to
  `ExprValue.equals`, so two `EvalResult`s differing only by
  int-vs-float on the value field compare equal (consistent with
  `ExprValue(1) == ExprValue(1.0)`).
* `__hash__` is **not** implemented — `EvalResult` is unhashable. The
  `value` field can hold list / path / range values that aren't
  themselves hashable, so pinning a hash on the wrapper would diverge
  from `ExprValue` (which deliberately omits `__hash__`).
* `__reduce__` round-trips through the constructor, so `EvalResult`
  pickles cleanly.
* `__repr__` is parseable and includes all three fields:
  `EvalResult(value=ExprValue(42), peak_memory=128, operation_count=7)`.

The previous `ParsedExpression.peak_memory_usage` and
`ParsedExpression.operation_count` attributes have been **removed**.
They were stored in atomics that were overwritten on every `evaluate()`
call — concurrent or sequential evaluations of the same instance
produced last-writer-wins values, which made them unsafe to read across
threads and surprising to read sequentially. `EvalResult` replaces them
with a per-call value bundle that is local to its caller.

### `PathFormat`

Path format enum controlling how `path` values behave.

```python
from openjd.expr import PathFormat

PathFormat.POSIX     # Unix-style paths (/)
PathFormat.WINDOWS   # Windows-style paths (\)
PathFormat.URI       # URI paths (s3://, https://)

PathFormat.POSIX.name  # "POSIX"
```

> **Not a `str` mixin Enum.** The pure-Python reference declares
> `class PathFormat(str, Enum)`, so reference values *are* strings —
> `PathFormat.POSIX == "POSIX"` is `True` and
> `isinstance(PathFormat.POSIX, str)` is `True`. The Rust-backed
> binding is a pyo3 enum that compares equal to its integer
> discriminant only; on this binding both expressions are `False`.
> Code that ducks-types a `PathFormat` as a string via
> `isinstance(..., str)` checks or via `==` against a string literal
> should switch to `fmt is PathFormat.POSIX` /
> `fmt == PathFormat.POSIX`, or read `fmt.name` when a string is
> genuinely needed.
>
> Iteration and value-lookup operations from `Enum` are also not
> supported — `list(PathFormat)`, `for fmt in PathFormat: ...`, and
> `PathFormat["POSIX"]` all raise `TypeError`. Use direct attribute
> access (`PathFormat.POSIX`, …) and an explicit tuple of members
> where iteration is needed.

### `PathMappingRule`

A rule for mapping paths from one location to another, used by
`apply_path_mapping` and sessions for cross-platform path translation.

```python
from openjd.expr import PathMappingRule, PathFormat
from pathlib import PurePosixPath

# Construction
rule = PathMappingRule(
    source_path_format=PathFormat.POSIX,
    source_path="/mnt/shared",
    destination_path="/local/cache",
)

# Apply
matched, result = rule.apply(path="/mnt/shared/project/file.exr")
# matched=True, result="/local/cache/project/file.exr"

matched, result = rule.apply(path="/other/path")
# matched=False, result="/other/path"

# Serialization
d = rule.to_dict()
# {"source_path_format": "POSIX", "source_path": "/mnt/shared", "destination_path": "/local/cache"}
rule2 = PathMappingRule.from_dict(d)
```

**Equality and hashability.** `PathMappingRule` implements `__eq__`
and `__hash__` over the three fields. Two rules compare equal when
they have identical `source_path_format`, `source_path`, and
`destination_path`; equal rules hash equal so the type is suitable
as a `set` / `dict` key.

**`source_path` is always a `str`, regardless of input.** The
constructor accepts either a `str` or the matching pathlib type
(`PurePosixPath` for `PathFormat.POSIX`, `PureWindowsPath` for
`PathFormat.WINDOWS`, `str`-only for `PathFormat.URI`), but the
stored field — and the `source_path` getter — is always a
`str`. This is a deliberate divergence from the pure-Python
reference (which preserves whatever the constructor was given) so
that the rule is cheap to serialise, pickle, and round-trip
through `to_dict`/`from_dict` without needing per-format
discriminator logic on the consumer side. Callers porting from the
reference that need a `PurePath`-shaped value should re-wrap the
getter result themselves:

```python
from pathlib import PurePosixPath, PureWindowsPath

rule = PathMappingRule(
    source_path_format=PathFormat.POSIX,
    source_path=PurePosixPath("/mnt/shared"),
    destination_path="/local/cache",
)
rule.source_path                     # "/mnt/shared" (str, not PurePosixPath)
type(rule.source_path)               # <class 'str'>

# Re-wrap if needed:
if rule.source_path_format == PathFormat.POSIX:
    src = PurePosixPath(rule.source_path)
elif rule.source_path_format == PathFormat.WINDOWS:
    src = PureWindowsPath(rule.source_path)
else:
    src = rule.source_path           # URI: stays str
```

`destination_path` follows the same rule: `str` in, `str` out.

### `RangeExpr`

Integer range expression for task parameter spaces. Parses expressions
like `"1-10"`, `"1-100:10"`, `"1,5,10-20"` into sorted, non-overlapping ranges.

```python
from openjd.expr import RangeExpr

r = RangeExpr("1-10")
len(r)          # 10
3 in r          # True
r[0]            # 1
r[-1]           # 10
list(r)         # [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
r.ranges()      # [IntRange(start=1, end=10, step=1)]
r.start         # 1
r.end           # 10

r = RangeExpr("1-10:3")
list(r)         # [1, 4, 7, 10]

r = RangeExpr("1-3,10-12")
list(r)         # [1, 2, 3, 10, 11, 12]
r.ranges()
# [IntRange(start=1, end=3, step=1),
#  IntRange(start=10, end=12, step=1)]

# Build from a spec-form string. `RangeExpr.from_str(s)` is a
# `@staticmethod` that mirrors the v0 reference's `from_str`
# classmethod and is equivalent to the constructor:
RangeExpr.from_str("1-10")        # same as RangeExpr("1-10")
RangeExpr.from_str("1-10:2,15")   # same as RangeExpr("1-10:2,15")

# Build from a list of values (ints or numeric strings, mixed allowed).
# Duplicates are removed and the result is sorted ascending.
RangeExpr.from_list([1, 3, 5, 7, 9])      # 1-9:2
RangeExpr.from_list([9, 8, 7, 6])         # 6-9
RangeExpr.from_list(["1", "2", "3"])      # 1-3
```

`RangeExpr.from_list([])` raises `ValueError`. `RangeExpr("...")` and
`RangeExpr.from_str("...")` raise `RangeExprError` on a malformed
input string. Two `RangeExpr` values that compare equal also hash
equal (suitable as `set` / `dict` keys).

### `IntRange`

A single contiguous integer range — the element type returned by
``RangeExpr.ranges()``. Both ``start`` and ``end`` are always
*inclusive*, and ``step`` is always positive (descending input ranges
are normalised to ascending form upstream).

```python
from openjd.expr import IntRange

ir = IntRange(1, 10, 2)
ir.start        # 1
ir.end          # 9 — last value reached by stepping from start
ir.step         # 2
len(ir)         # 5
3 in ir         # True
4 in ir         # False
list(ir)        # [1, 3, 5, 7, 9]

# Constructor accepts a descending range with a negative step and
# normalises it to ascending form — matches the upstream IntRange
# constructor and the v0 IntRange shape.
IntRange(10, 1, -1)        # IntRange(start=1, end=10, step=1)
IntRange(1, 10, 0)         # raises RangeExprError
IntRange(1, 10, -1)        # raises (ascending range needs positive step)

# Equality and hashing — IntRange instances are usable as set/dict keys.
IntRange(1, 10, 1) == IntRange(1, 10, 1)   # True
IntRange(1, 10, 1) == IntRange(1, 10, 2)   # False (different step)
hash(IntRange(1, 10, 1))                    # stable within a process

# Pickleable via the standard constructor round-trip.
import pickle
loaded = pickle.loads(pickle.dumps(IntRange(1, 10, 1)))
assert loaded == IntRange(1, 10, 1)
```

### `FormatString`

Template format string with `{{interpolation}}` syntax. Used in template
fields like command, args, job name, and embedded file data. Interpolations
contain expressions that are resolved against a symbol table at runtime.

```python
from openjd.expr import FormatString, SymbolTable

# Literal (no interpolations)
fs = FormatString("hello world")
fs.is_literal()           # True
fs.raw()                  # "hello world"

# With interpolation
fs = FormatString("render --frame {{Param.Frame}}")
fs.is_literal()           # False
fs.expression_names()     # ["Param.Frame"]
fs.has_complex_expressions()  # False (simple name reference)

# Resolve
st = SymbolTable({"Param.Frame": 42})
fs.resolve_string(st)     # "render --frame 42"

# Single-expression format string returns typed value
fs = FormatString("{{Param.Frame + 1}}")
fs.has_complex_expressions()  # True
result = fs.resolve(st)
result.item()             # 43
result.type.type_code     # TypeCode.INT
```

**Static validation.** ``validate_expressions(symtab, *, profile=None)``
walks every ``{{...}}`` segment and evaluates it
against the supplied symbol table, raising
``FormatStringValidationError`` (a ``ValueError`` subclass) on the
first failure. Returns ``None`` on success.

The intended pattern is to populate the symbol table with
``ExprValue.unresolved(T)`` placeholders for symbols whose concrete
values are not yet known — the evaluator's unresolved-propagation
rules then drive type checking through the expression tree without
requiring real values:

```python
from openjd.expr import (
    FormatString, SymbolTable, ExprType, ExprValue,
    FormatStringValidationError,
)

# At template-validation time, populate the symbol table with
# typed placeholders for parameters whose values aren't bound yet.
symtab = SymbolTable({
    "Param.Name": ExprValue.unresolved(ExprType("string")),
    "Param.Frame": ExprValue.unresolved(ExprType("int")),
})

# Valid: every interpolation resolves under the placeholder types.
FormatString("hello {{Param.Name}}").validate_expressions(symtab)

# Invalid: missing symbol — raises with a caret-anchored diagnostic.
try:
    FormatString("hello {{Param.Missing}}").validate_expressions(symtab)
except FormatStringValidationError as e:
    str(e)  # "Failed to parse interpolation expression at [6, 24].
            #  Undefined variable: 'Param.Missing'.
            #    Param.Missing
            #    ~~~~~~^~~~~~~"
```

The error message embeds the ``[start, end]`` byte offsets of the
failing ``{{...}}`` pair so callers can produce structured
diagnostics or syntax-highlight the failing segment. Mirrors the
Rust crate's ``FormatString::validate_expressions(symtab, lib)``.

**Equality and hashability.** `FormatString` implements `__eq__` and
`__hash__` on the raw source string. Two format strings compare equal
iff `a.raw() == b.raw()`; lexically distinct inputs that would
resolve to the same value (e.g. `"{{ Param.X }}"` vs `"{{Param.X}}"`)
compare unequal — this preserves source identity rather than
canonicalising whitespace. Equal format strings hash equal, so the
type is suitable as a `set` / `dict` key.

**Copying referenced symbol values.**
``copy_used_symtab_values(source, dest)`` walks every ``{{...}}``
interpolation in this format string and copies the symbol-table
entries the expressions reference from ``source`` into ``dest``.

The copy stops at the symbol value — it does **not** descend into
property or method access on that value. So for
``"{{Param.Path.stem.upper()}}"`` the copy includes ``Param.Path``
but not ``Param.Path.stem``: the value is a path, and ``.stem`` is
evaluated by the expression engine at resolve time. Symbols
referenced by the format string but absent from ``source`` are
silently skipped — partial misses are not an error here, on the
assumption that the caller is staging values for a later
``resolve`` / ``resolve_string`` that will surface any real gaps.

Mirrors the Rust crate's
``FormatString::copy_used_symtab_values(source, dest)``. The
``openjd-model`` crate uses it to build the filtered
``resolved_symtab`` it stores on resolved environment templates so
that downstream re-evaluation only sees the symbols the template
actually referenced.

```python
from openjd.expr import FormatString, SymbolTable

src = SymbolTable({
    "Param": {"Frame": 42, "Name": "shot01", "Unused": 99},
})
dest = SymbolTable()

FormatString("render --frame {{Param.Frame}} --name {{Param.Name}}") \
    .copy_used_symtab_values(src, dest)

dest["Param.Frame"].item()   # 42
dest["Param.Name"].item()    # "shot01"
"Param.Unused" in dest       # False — not referenced

# .upper() is a method call, so the copy stops at Param.Name —
# Param.Name.upper is *not* a symbol, it's a value-side method.
dest2 = SymbolTable()
FormatString("{{Param.Name.upper()}}").copy_used_symtab_values(src, dest2)
dest2["Param.Name"].item()       # "shot01"
"Param.Name.upper" in dest2      # False
```

## Exceptions

```python
from openjd.expr import ExpressionError, RangeExprError, evaluate_expression

# Syntax error
try:
    evaluate_expression("1 +")
except ExpressionError as e:
    str(e)  # "Syntax error: ...\n  1 +\n  ^~~"

# Undefined variable
try:
    evaluate_expression("Param.X")
except ExpressionError as e:
    str(e)  # "Undefined variable: 'Param.X'..."

# Range expression error
try:
    RangeExpr("not-a-range")
except RangeExprError as e:
    str(e)  # "Expected integer in 'not-a-range'"
```

| Exception | Base |
|---|---|
| `ExpressionError` | `ValueError` |
| `ExpressionTypeError` | `ExpressionError` |
| `RangeExprError` | `ValueError` |
| `FormatStringValidationError` | `ValueError` |

`ExpressionError` (and its subclass `ExpressionTypeError`) accept
optional keyword arguments for attaching expression-source context:

```python
from openjd.expr import ExpressionError

# Construction with context
err = ExpressionError(
    "bad value",
    expr="Param.X + 1",  # outer expression source
    lineno=1,
    col_offset=8,
    node=ast_node,        # opaque tagalong; not used by the binding
)
err.expr           # "Param.X + 1"
err.col_offset     # 8

# Decorate an existing error caught from `evaluate_expression`.
# Returns a new error if no context is attached, or self if there
# already is one (innermost wins).
try:
    evaluate_expression("Param.X")
except ExpressionError as inner:
    raise inner.with_context("outer source", node=outer_node)

# Render the message with a custom prefix on the source line. Useful
# for let-binding errors where the expression appears as part of
# `"name = expr"`.
err.message_with_expr_prefix("x = ")
# "bad value\n  x = Param.X + 1\n          ^"
```

## Constants

```python
from openjd.expr import DEFAULT_MEMORY_LIMIT, DEFAULT_OPERATION_LIMIT

DEFAULT_MEMORY_LIMIT      # 100_000_000 (100 MB)
DEFAULT_OPERATION_LIMIT   # 10_000_000 (10 million)
```

## Pickle Support

The following value types are pickleable. Pickled state round-trips
through ``pickle.dumps`` / ``pickle.loads`` and compares equal to the
original.

| Type | Reduces through |
|---|---|
| ``PathFormat`` | variant name (``POSIX`` / ``WINDOWS`` / ``URI``) |
| ``TypeCode`` | variant name (``INT``, ``LIST``, ``RANGE_EXPR``, …) |
| ``ExprRevision`` | variant name (e.g. ``V2026_02``) |
| ``ExprType`` | spec-form string (``str(t)``) |
| ``ExprValue`` | constructor arguments (``item``, ``type``, ``path_format``) |
| ``RangeExpr`` | spec-form string (``str(r)``) |
| ``FormatString`` | raw input string (``fs.raw()``) |
| ``SymbolTable`` | flat ``dict[str, ExprValue]`` of all dotted leaf paths |
| ``PathMappingRule`` | ``to_dict()`` / ``from_dict()`` |
| ``HostContext`` | one of three classmethods (``none``, ``unresolved``, ``with_rules``) |
| ``ExprProfile`` | constructor arguments (``revision``, ``extensions``, ``host_context``) |
| ``EvalResult`` | constructor arguments (``value``, ``peak_memory``, ``operation_count``) |
| ``ExpressionError``, ``ExpressionTypeError``, ``RangeExprError``, ``FormatStringValidationError`` | standard exception pickle, under their canonical ``openjd.expr`` module path |

The runtime type ``ParsedExpression`` is not pickleable — it holds
transient evaluation state that is not meaningful to serialize.
Re-construct it via ``parse_expression`` after loading the inputs.
