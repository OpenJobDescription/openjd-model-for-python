# Open Job Description - Models For Python

[![pypi](https://img.shields.io/pypi/v/openjd-model.svg)](https://pypi.python.org/pypi/openjd-model)
[![python](https://img.shields.io/pypi/pyversions/openjd-model.svg?style=flat)](https://pypi.python.org/pypi/openjd-model)
[![license](https://img.shields.io/pypi/l/openjd-model.svg?style=flat)](https://github.com/OpenJobDescription/openjd-model/blob/mainline/LICENSE)

Open Job Description is a flexible open specification for defining render jobs which are portable
between studios and render management solutions. This package provides a Python implementation of the
data model for Open Job Description's template schemas. It can parse, validate, create JSON/Yaml
documents for the Open Job Description specification, and more. A main use-case that this library
targets is interoperability by creating applications to translate a Job from Open Job Description
to the render management software of your choice.

For more information about Open Job Description and our goals with it, please see the
Open Job Description [Wiki on GitHub](https://github.com/OpenJobDescription/openjd-specifications/wiki).

## Compatibility

This library requires:

1. Python 3.9 or higher; and
2. Linux, MacOS, or Windows operating system.

## Versioning

This package's version follows [Semantic Versioning 2.0](https://semver.org/), but is still considered to be in its
initial development, thus backwards incompatible versions are denoted by minor version bumps. To help illustrate how
versions will increment during this initial development stage, they are described below:

1. The MAJOR version is currently 0, indicating initial development.
2. The MINOR version is currently incremented when backwards incompatible changes are introduced to the public API.
3. The PATCH version is currently incremented when bug fixes or backwards compatible changes are introduced to the public API.

## Contributing

We encourage all contributions to this package.  Whether it's a bug report, new feature, correction, or additional
documentation, we greatly value feedback and contributions from our community.

Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for our contributing guidelines.

## Example Usage

### Reading and Validating a Job Template

To validate a job template, you can read the JSON or YAML input
into Python data structures and then pass the result to `decode_job_template`.
By default, this will accept templates of any supported version number with
no extensions enabled. Use `decode_environment_template` for environment templates.

To accept extensions in templates, provide the list of the names you support. See the
[Open Job Description 2023-09 specification](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas#1-root-elements)
for the list of extensions available.

```python
from openjd.model import DocumentType, decode_job_template, document_string_to_object

# String containing the json of the job template
template_string = """specificationVersion: jobtemplate-2023-09
name: DemoJob
steps:
  - name: DemoStep
    script:
      actions:
        onRun:
          command: python
          args: ["-c", "print('Hello')"]
"""

# You can use 'json.loads' or 'yaml.safe_load' directly as well
template_object = document_string_to_object(
    document=template_string,
    document_type=DocumentType.YAML
)

# Raises a DecodeValidationError if it fails.
job_template = decode_job_template(template=template_object, supported_extensions=["TASK_CHUNKING"])
```

Once you have the Open Job Description model object, you can use the `model_to_object` function
to convert it into an object suitable for converting to JSON or YAML.

```python
import json
from openjd.model import model_to_object

obj = model_to_object(model=job_template)
print(json.dumps(obj, indent=2))
```

### Creating Template Model Objects

As an alternative to assembling full job templates as raw data following the specification data model,
you can use the library to construct model objects of components, such as for StepTemplates,
and then assemble the result into a job template. The `parse_model` function provides a way to
do this.

To call `parse_model`, you will need to provide the list of extensions you want to enable as the
`supported_extensions` argument. Individual model objects can accept inputs differently depending on
what extensions are requested in the job template, and the model parsing context holds that list.
The functions `decode_job_template` and `decode_environment_template` create this
context from top-level template fields, but when using `parse_model` to process interior model types
you must provide it explicitly.

```python
import json
from openjd.model import parse_model, model_to_object
from openjd.model.v2023_09 import StepTemplate

extensions_list = ["TASK_CHUNKING"]

step_template = parse_model(
    model=StepTemplate,
    obj={
        "name": "DemoStep",
        "script": {
            "actions": {"onRun": {"command": "python", "args": ["-c", "print('Hello world!')"]}}
        },
    },
    supported_extensions=extensions_list,
)

obj = model_to_object(model=step_template)
print(json.dumps(obj, indent=2))
```

You can also construct the individual elements of the template from the model object types.
This can be more effort than using `parse_model` depending on how the enabled extensions
affect processing. You will need to create a ModelParsingContext object to hold
the extensions list, and pass it to any model object constructors that need it.

```python
import json
from openjd.model import model_to_object
from openjd.model.v2023_09 import (
    StepTemplate,
    StepScript,
    StepActions,
    Action,
    ArgString,
    CommandString,
    ModelParsingContext,
)

context = ModelParsingContext(supported_extensions=["TASK_CHUNKING"])

step_template = StepTemplate(
    name="DemoStep",
    script=StepScript(
        actions=StepActions(
            onRun=Action(
                command=CommandString("python", context=context),
                args=[
                    ArgString("-c", context=context),
                    ArgString("print('Hello world!')", context=context),
                ],
            )
        )
    ),
)

obj = model_to_object(model=step_template)
print(json.dumps(obj, indent=2))
```

### Creating a Job from a Job Template

```python
import os
from pathlib import Path
from openjd.model import (
    DecodeValidationError,
    create_job,
    decode_job_template,
    preprocess_job_parameters
)

job_template_path = Path("/absolute/path/to/job/template.json")
job_template = decode_job_template(
    template={
        "name": "DemoJob",
        "specificationVersion": "jobtemplate-2023-09",
        "parameterDefinitions": [
            { "name": "Foo", "type": "INT" }
        ],
        "steps": [
            {
                "name": "DemoStep",
                "script": {
                    "actions": {
                        "onRun": { "command": "python", "args": [ "-c", "print(r'Foo={{Param.Foo}}')" ] }
                    }
                }
            }
        ]
    }
)
try:
    parameters = preprocess_job_parameters(
        job_template=job_template,
        job_parameter_values={
            "Foo": "12"
        },
        job_template_dir=job_template_path.parent,
        current_working_dir=Path(os.getcwd())
    )
    job = create_job(
        job_template=job_template,
        job_parameter_values=parameters
    )
except (DecodeValidationError, RuntimeError) as e:
    print(str(e))
```

### Working with Step dependencies

```python
from openjd.model import (
    StepDependencyGraph,
    create_job,
    decode_job_template
)

job_template = decode_job_template(
    template={
        "name": "DemoJob",
        "specificationVersion": "jobtemplate-2023-09",
        "steps": [
            {
                "name": "Step1",
                "script": {
                    "actions": {
                        "onRun": { "command": "python", "args": [ "-c", "print('Step1')" ] }
                    }
                }
            },
            {
                "name": "Step2",
                "dependencies": [ { "dependsOn": "Step1" }, { "dependsOn": "Step3" }],
                "script": {
                    "actions": {
                        "onRun": { "command": "python", "args": [ "-c", "print('Step2')" ] }
                    }
                }
            },
            {
                "name": "Step3",
                "script": {
                    "actions": {
                        "onRun": { "command": "echo", "args": [ "Step3" ] }
                    }
                }
            },
        ]
    }
)
job = create_job(job_template=job_template, job_parameter_values={})
dependency_graph = StepDependencyGraph(job=job)

for step in job.steps:
    step_node = dependency_graph.step_node(stepname=step.name)
    if step_node.in_edges:
        name_list = ', '.join(edge.origin.step.name for edge in step_node.in_edges)
        print(f"Step '{step.name}' depends upon: {name_list}")
    if step_node.out_edges:
        name_list = ', '.join(edge.dependent.step.name for edge in step_node.out_edges)
        print(f"The following Steps depend upon '{step.name}': {name_list}")

print(f"\nSteps in topological order: {[step.name for step in dependency_graph.topo_sorted()]}")
# The following Steps depend upon 'Step1': Step2
# Step 'Step2' depends upon: Step1, Step3
# The following Steps depend upon 'Step3': Step2

# Steps in topological order: ['Step1', 'Step3', 'Step2']
```

### Working with a Step's Tasks

```python
from openjd.model import (
    StepParameterSpaceIterator,
    create_job,
    decode_job_template
)

job_template = decode_job_template(
    template={
        "name": "DemoJob",
        "specificationVersion": "jobtemplate-2023-09",
        "steps": [
            {
                "name": "DemoStep",
                "parameterSpace": {
                    "taskParameterDefinitions": [
                        { "name": "Foo", "type": "INT", "range": "1-5" },
                        { "name": "Bar", "type": "INT", "range": "1-5" }
                    ],
                    "combination": "(Foo, Bar)"
                },
                "script": {
                    "actions": {
                        "onRun": {
                            "command": "python",
                            "args": [ "-c", "print(f'Foo={{Task.Param.Foo}}, Bar={{Task.Param.Bar}}"]
                        }
                    }
                }
            },
        ]
    }
)
job = create_job(job_template=job_template, job_parameter_values={})
for step in job.steps:
    iterator = StepParameterSpaceIterator(space=step.parameterSpace)
    print(f"Step '{step.name}' has {len(iterator)} Tasks")
    for param_set in iterator:
        print(param_set)
# Step 'DemoStep' has 5 Tasks
# {'Foo': ParameterValue(type=<ParameterValueType.INT: 'INT'>, value='1'), 'Bar': ParameterValue(type=<ParameterValueType.INT: 'INT'>, value='1')}
# {'Foo': ParameterValue(type=<ParameterValueType.INT: 'INT'>, value='2'), 'Bar': ParameterValue(type=<ParameterValueType.INT: 'INT'>, value='2')}
# {'Foo': ParameterValue(type=<ParameterValueType.INT: 'INT'>, value='3'), 'Bar': ParameterValue(type=<ParameterValueType.INT: 'INT'>, value='3')}
# {'Foo': ParameterValue(type=<ParameterValueType.INT: 'INT'>, value='4'), 'Bar': ParameterValue(type=<ParameterValueType.INT: 'INT'>, value='4')}
# {'Foo': ParameterValue(type=<ParameterValueType.INT: 'INT'>, value='5'), 'Bar': ParameterValue(type=<ParameterValueType.INT: 'INT'>, value='5')}
```

## Downloading

You can download this package from:
- [PyPI](https://pypi.org/project/openjd-model/)
- [GitHub releases](https://github.com/OpenJobDescription/openjd-model-for-python/releases)

### Verifying GitHub Releases

See [Verifying GitHub Releases](https://github.com/OpenJobDescription/openjd-model-for-python?tab=security-ov-file#verifying-github-releases) for more information.

## Security

We take all security reports seriously. When we receive such reports, we will
investigate and subsequently address any potential vulnerabilities as quickly
as possible. If you discover a potential security issue in this project, please
notify AWS/Amazon Security via our [vulnerability reporting page](http://aws.amazon.com/security/vulnerability-reporting/)
or directly via email to [AWS Security](aws-security@amazon.com). Please do not
create a public GitHub issue in this project.

## License

This project is licensed under the Apache-2.0 License.
