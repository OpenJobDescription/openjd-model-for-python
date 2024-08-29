# Development documentation

This documentation provides guidance on developer workflows for working with the code in this repository.

Table of Contents:
* [Development Environment Setup](#development-environment-setup)
* [The Development Loop](#the-development-loop)
* [Testing](#testing)
   * [Writing tests](#writing-tests)
   * [Running tests](#running-tests)
* [Things to Know](#things-to-know)
   * [Package's Public Interface](#the-packages-public-interface)
   * [Coding Style Requirements](#coding-style-requirements)

## Development Environment Setup

To develop the Python code in this repository you will need:

1. Python 3.9 or higher. We recommend [mise](https://github.com/jdx/mise) if you would like to run more than one version
   of Python on the same system. When running unit tests against all supported Python versions, for instance.
2. The [hatch](https://github.com/pypa/hatch) package installed (`pip install --upgrade hatch`) into your Python environment. 

You can develop on a Linux, MacOs, or Windows workstation, but you will find that some of the support scripting is specific to
Linux workstations.

## The Development Loop

We have configured [hatch](https://github.com/pypa/hatch) commands to support a standard development loop. You can run the following
from any directory of this repository:

* `hatch build` - To build the installable Python wheel and sdist packages into the `dist/` directory.
* `hatch run test` - To run the PyTest unit tests found in the `test/` directory. See [Testing](#testing).
* `hatch run all:test` - To run the PyTest unit tests against all available supported versions of Python.
* `hatch run lint` - To check that the package's formatting adheres to our standards.
* `hatch run fmt` - To automatically reformat all code to adhere to our formatting standards.
* `hatch shell` - Enter a shell environment where you can run the `deadline` command-line directly as it is implemented in your
  checked-out local git repository.
* `hatch env prune` - Delete all of your isolated workspace [environments](https://hatch.pypa.io/1.12/environment/) 
   for this package.

If you are not sure about how to approach development for this package, then we have some suggestions.

1. Run python within a `hatch shell` environment for interactive development. Python will import your in-development
   codebase when you `import openjd.model` from this environment. This makes it easy to use interactive python, the python
   debugger, and short test scripts to develop and test your changes. 
   * Note that if you make changes to your source and are running interactive Python then you will need to use
    [importlib.reload](https://docs.python.org/3/library/importlib.html#importlib.reload) to reload the the module(s) that
    you modified for your modifications to take effect.
2. Run the unit test suite frequently (See [Testing](#testing)), and modify/add to it as you are developing your change, rather than
   only when your change is complete. The test suite runs very quickly, and this will help surface regressions that your change may
   cause before you get too far into your implementation.

Once you are satisfied with your code, and all relevant tests pass, then run `hatch run fmt` to fix up the formatting of
your code and post your pull request.

Note: Hatch uses [environments](https://hatch.pypa.io/1.12/environment/) to isolate the Python development workspace
for this package from your system or virtual environment Python. If your build/test run is not making sense, then
sometimes pruning (`hatch env prune`) all of these environments for the package can fix the issue.

## Testing

The objective for the tests of this package are to act as regression tests to help identify unintended changes to
functionality in the package. As such, we strive to have high test coverage of the different behaviours/functionality
that the package contains. Code coverage metrics are not the goal, but rather are a guide to help identify places
where there may be gaps in testing coverage.

All tests are all located under the `test/` directory of this repository. If you are adding or modifying
functionality, then you will almost always want to be writing one or more tests to demonstrate that your
logic behaves as expected and that future changes do not accidentally break your change.

### Writing Tests

If you want assistance developing tests, then please don't hesitate to open a draft pull request and ask for help.
We'll do our best to help you out and point you in the right direction. We also suggest looking at the existing tests
for the same or similar functions for inspiration (search for calls to the function within the `test/`
subdirectories). You will also find both the official [PyTest documentation](https://docs.pytest.org/en/stable/)
and [unitest.mock documentation](https://docs.python.org/3.8/library/unittest.mock.html) very informative (we do).

Our tests are implemented using the [PyTest](https://docs.pytest.org/en/stable/) testing framework,
and unit tests occationally make use of Python's [unittest.mock](https://docs.python.org/3.8/library/unittest.mock.html)
package to avoid runtime dependencies and narrowly focus tests on a specific aspect of the implementation. 

As a rule, we aim to keep usage of `unittest.mock` to a bare minimum in this package's tests. Using a mock inherrently
encodes assumptions into the tests about how the mocked functionality functions. So, if a change is made that
violates those assumptions then the test suite will not catch it, and we may end up releasing broken code.

### Running Tests

You can run tests with:

* `hatch run test` - To run the tests with your default Python runtime.
* `hatch run all:test` - To run the tests with all of the supported Python runtime versions that you have installed.

Any arguments that you add to these commands are passed through to PyTest. So, if you want to, say, run the
[Python debugger](https://docs.python.org/3/library/pdb.html) to investigate a test failure then you can run: `hatch run test --pdb`

### Super verbose test output

If you find that you need much more information from a failing test (say you're debugging a
deadlocking test) then a way to get verbose output from the test is to enable Pytest
[Live Logging](https://docs.pytest.org/en/latest/how-to/logging.html#live-logs):

1. Add a `pytest.ini` to the root directory of the repository that contains (Note: for some reason,
setting `log_cli` and `log_cli_level` in `pyproject.toml` does not work for us, nor does setting the options
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

## Things to Know

### The Package's Public Interface

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

#### On `import os as _os`

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

### Coding Style Requirements

#### Use of Keyword-Only Arguments

A convention that we adopt in this package is that all functions/methods that are a
part of the package's external interface should refrain from using positional-or-keyword arguments.
All arguments should be keyword-only unless the argument name has no true external meaning (e.g.
arg1, arg2, etc. for `min`). Benefits of this convention are:

1. All uses of the public APIs of this package are forced to be self-documenting; and
2. The benefits set forth in PEP 570 ( https://www.python.org/dev/peps/pep-0570/#problems-without-positional-only-parameters ).

For example:

```python
# Define a public function like this:
def public_function(*, model: dict[str,Any]) -> str:
    pass

# Rather than like this:
def public_function(model: dict[str, Any]) -> str:
    pass
```

#### Pydantic Models

The data model is written using [Pydantic](https://github.com/pydantic/pydantic). Pydantic provides the framework for parsing and
validating input job templates.

1. We intentionally use `Decimal` in place of `float` in our data models as `Decimal` will preserve the
    precision present in the input whereas `float` will not.
1. Some classes in the model have "Definition" or "Template" version, as well as a "Target model" version.
    These exist for parts of the model where instantiating a JobTemplate into a Job changes the model in
    some way. These are not necessary for all parts of the model.

#### Exceptions

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
