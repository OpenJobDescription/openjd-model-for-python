
# Development

## Command Reference

```
# Build the package
hatch build

# Run tests
hatch run test

# Run linting
hatch run lint

# Run formatting
hatch run fmt

# Run a full test
hatch run all:test
```

## The Package's Public Interface

This package is a library wherein we are explicit and intentional with what we expose as public.

The standard convention in Python is to prefix things with an underscore character ('_') to
signify that the thing is private to the implementation, and is not intended to be used by
external consumers of the thing.

We use this convention in this package in two ways:

1. In filenames.
    1. Any file whose name is not prefixed with an underscore **is** a part of the public
    interface of this package. The name may not change and public symbols (classes, modules,
    functions, etc.) defined in the file may not be moved to other files or renamed without a
    major version number change.
    2. Any file whose name is prefixed with an underscore is an internal module of the package
    and is not part of the public interface. These files can be renamed, refactored, have symbols
    renamed, etc. Any symbol defined in one of these files that is intended to be part of this
    package's public interface must be imported into an appropriate `__init__.py` file.
2. Every symbol that is defined or imported in a public module and is not intended to be part
   of the module's public interface is prefixed with an underscore.

For example, a public module in this package will be defined with the following style:

```python
# The os module is not part of this file's external interface
import os as _os

# PublicClass is part of this file's external interface.
class PublicClass:
    def publicmethod(self):
        pass

    def _privatemethod(self):
        pass

# _PrivateClass is not part of this file's external interface.
class _PrivateClass:
    def publicmethod(self):
        pass

    def _privatemethod(self):
        pass
```

### On `import os as _os`

Every module/symbol that is imported into a Python module becomes a part of that module's interface.
Thus, if we have a module called `foo.py` such as:

```python
# foo.py

import os
```

Then, the `os` module becomes part of the public interface for `foo.py` and a consumer of that module
is free to do:

```python
from foo import os
```

We don't want all (generally, we don't want any) of our imports to become part of the public API for
the module, so we import modules/symbols into a public module with the following style:

```python
import os as _os
from typing import Dict as _Dict
```

## Use of Keyword-Only Arguments

Another convention that we are adopting in this package is that all functions/methods that are a
part of the package's external interface should refrain from using positional-or-keyword arguments.
All arguments should be keyword-only unless the argument name has no true external meaning (e.g.
arg1, arg2, etc. for `min`). Benefits of this convention are:

1. All uses of the public APIs of this package are forced to be self-documenting; and
2. The benefits set forth in PEP 570 ( https://www.python.org/dev/peps/pep-0570/#problems-without-positional-only-parameters ).

## Exceptions

All functions/methods that raise an exception should have a section in their docstring that states
the exception(s) they raise. e.g.

```py
def my_function(key, value):
"""Does something...

    Raises:
        KeyError: when the key is not valid
        ValueError: when the value is not valid
"""
```

All function/method calls that can raise an exception should have a comment in the line above
that states which exception(s) can be raised. e.g.

```py
try:
    # Raises: KeyError, ValueError
    my_function("key", "value")
except ValueError as e:
    # Error handling...
```

## About the data model

1. The data model is written using Pydantic. Pydantic provides the framework for parsing and validating
    input job templates.
1. We intentionally use `Decimal` in place of `float` in our data models as `Decimal` will preserve the
    precision present in the input whereas `float` will not.
1. Some classes in the model have "Definition" or "Template" version, as well as a "Target model" version.
    These exist for parts of the model where instantiating a JobTemplate into a Job changes the model in
    some way. These are not necessary for all parts of the model.

## Super verbose test output

If you find that you need much more information from a failing test (say you're debugging a
deadlocking test) then a way to get verbose output from the test is to enable Pytest
[Live Logging](https://docs.pytest.org/en/latest/how-to/logging.html#live-logs):

1. Add a `pytest.ini` to the root directory of the repository that contains (Note: for some reason,
setting `log_cli` and `log_cli_level` in `pyproject.toml` does not work, nor does setting the options
on the command-line; if you figure out how to get it to work then please update this section):
```
[pytest]
xfail_strict = False
log_cli = true
log_cli_level = 10
```
2. Modify `pyproject.toml` to set the following additional `addopts` in the `tool.pytest.ini_options` section:
```
    "-vvvvv",
    "--numprocesses=1"
```
3. Add logging statements to your tests as desired and run the test(s) that you are debugging.
