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

### Reading and Validating a Template File

```python
from openjd.model import (
    DecodeValidationError,
    DocumentType,
    JobTemplate,
    document_string_to_object,
    decode_job_template
)

# String containing the json of the job template
template_string = "..."
try:
    template_object = document_string_to_object(
        document=template_string,
        document_type=DocumentType.JSON
    )
    # Use 'decode_environment_template()' instead if decoding an
    # Environment Template
    job_template = decode_job_template(template=template_object)
except DecodeValidationError as e:
    print(str(e))
```

### Creating a Template Model

```python
from openjd.model.v2023_09 import *

job_template = JobTemplate(
    specificationVersion="jobtemplate-2023-09",
    name="DemoJob",
    steps=[
        StepTemplate(
            name="DemoStep",
            script=StepScript(
                actions=StepActions(
                    onRun=Action(
                        command="python",
                        args=["-c", "print('Hello world!')"]
                    )
                )
            )
        )
    ]
)
```

### Converting a Template Model to a Dictionary

```python
import json
from openjd.model import (
    decode_job_template,
    model_to_object,
)
from openjd.model.v2023_09 import *

job_template = JobTemplate(
    specificationVersion="jobtemplate-2023-09",
    name="DemoJob",
    steps=[
        StepTemplate(
            name="DemoStep",
            script=StepScript(
                actions=StepActions(
                    onRun=Action(
                        command="echo",
                        args=["Hello world"]
                    )
                )
            )
        )
    ]
)

obj = model_to_object(model=job_template)
print(json.dumps(obj))
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

You can verify the authenticity of the release artifacts using the `gpg` command line tool.

1) Download the desired release artifacts from the GitHub releases page. Make sure to download the corresponding PGP signature file (ending with `.sig`) as well.
For example, if you would like to verify your download of the wheel for version `1.2.3`, you should have the following files downloaded:
    ```
    openjd_model-1.2.3-py3-none-any.whl
    openjd_model-1.2.3-py3-none-any.whl.sig
    ```

2) Install the `gpg` command line tool. The installation process varies by operating system. Please refer to the GnuPG website for instructions: https://gnupg.org/download/

3) Save the following contents to a file called `openjobdescription-pgp.asc`:
    ```
    -----BEGIN PGP PUBLIC KEY BLOCK-----
    
    mQINBGXGjx0BEACdChrQ/nch2aYGJ4fxHNQwlPE42jeHECqTdlc1V/mug+7qN7Pc
    C4NQk4t68Y72WX/NG49gRfpAxPlSeNt18c3vJ9/sWTukmonWYGK0jQGnDWjuVgFT
    XtvJAAQBFilQXN8h779Th2lEuD4bQX+mGB7l60Xvh7vIehE3C4Srbp6KJXskPLPo
    dz/dx7a+GXRiyYCYbGX4JziXSjQZRc0tIaxLn/GDm7VnXpdHcUk3qJitree61oC8
    agtRHCH5s56E8wt8fXzyStElMkFIZsoLDlLp5lFqT81En9ho/+K6RLBkIj0mC8G7
    BafpHKlxkrIgNK3pWACL93GE6xihqwkZMCAeqloVvkOTdfAKDHuDSEHwKxHG3cZ1
    /e1YhtkPMVF+NMeoQavykUGVUT1bRoVNdk6bYsnbUjUI1A+JNf6MqvdRJyckZqEC
    ylkBekBp/SFpFHvQkRCpfVizm2GSrjdZKgXpm1ZlQJyMRVzc/XPbqdSWhz52r3IC
    eudwReHDc+6J5rs6tg3NbFfPVfCBMSqHlu1HRewWAllIp1+y6nfL4U3iEsUvZ1Y6
    IV3defHIP3kNPU14ZWf3G5rvJDZrIRnjoWhDcaVmivmB/cSdDzphL5FovSI8dsPm
    iU/JZGQb3EvZq+nl4pOiK32hETJ/fgCCzgUA3WqGeFNUNSI9KYZgBe6daQARAQAB
    tDRPcGVuIEpvYiBEZXNjcmlwdGlvbiA8b3BlbmpvYmRlc2NyaXB0aW9uQGFtYXpv
    bi5jb20+iQJXBBMBCABBFiEEvBcWYrv5OB7Tl2sZovDwWbzECYcFAmXGjx0DGy8E
    BQkDwmcABQsJCAcCAiICBhUKCQgLAgMWAgECHgcCF4AACgkQovDwWbzECYcSHRAA
    itPYx48xnJiT6tfnult9ZGivhcXhrMlvirVYOqEtRrt0l18sjr84K8mV71eqFwMx
    GS7e4iQP6guqW9biQfMA5/Id8ZjE7jNbF0LUGsY6Ktj+yOlAbTR+x5qr7Svb7oEs
    TMB/l9HBZ1WtIRzcUk9XYqzvYQr5TT997A63F28u32RchJ+5ECAz4g/p91aWxwVo
    HIfN10sGzttoukJCzC10CZAVscJB+nnoUbB/o3bPak6GUxBHpMgomb0K5g4Z4fXY
    4AZ9jKFoLgNcExdwteiUdSEnRorZ5Ny8sP84lwJziD3wuamVUsZ1C/KiQJBGTp5e
    LUY38J1oIwptw5fqjaAq2GQxEaIknWQ4fr3ZvNYUuGUt5FbHe5U5XF34gC8PK7v7
    bT/7sVdZZzKFScDLfH5N36M5FrXfTaXsVbfrRoa2j7U0kndyVEZyJsKVAQ8vgwbJ
    w/w2hKkyQLAg3l5yO5CHLGatsfSIzea4WoOAaroxiNtL9gzVXzqpw6qPEsH9hsws
    HsPEQWXHmDQvFTNUU14qic1Vc5fyxCBXIAGAPBd20b+219XznJ5uBKUgtvnqcItj
    nMYe6Btxh+pjrTA15X/p81z6sB7dkL1hPHfawLhCEzJbIPyyBTQYqY00/ap4Rj7t
    kzSiyzBejniFfAZ6eYBWsej7uXUsVndBF1ggZynPTeE=
    =iaEm
    -----END PGP PUBLIC KEY BLOCK-----
    ```

4) Import the OpenPGP key for Open Job Description by running the following command:

    ```
    gpg --import --armor openjobdescription-pgp.asc
    ```

5) Determine whether to trust the OpenPGP key. Some factors to consider when deciding whether or not to trust the above key are:

    - The internet connection you’ve used to obtain the GPG key from this website is secure
    - The device that you are accessing this website on is secure

    If you have decided to trust the OpenPGP key, then edit the key to trust with `gpg` like the following example:
    ```
    $ gpg --edit-key A2F0F059BCC40987
    gpg (GnuPG) 2.0.22; Copyright (C) 2013 Free Software Foundation, Inc.
    This is free software: you are free to change and redistribute it.
    There is NO WARRANTY, to the extent permitted by law.
    
    
    pub  4096R/BCC40987  created: 2024-02-09  expires: 2026-02-08  usage: SCEA
                         trust: unknown       validity: unknown
    [ unknown] (1). Open Job Description <openjobdescription@amazon.com>
    
    gpg> trust
    pub  4096R/BCC40987  created: 2024-02-09  expires: 2026-02-08  usage: SCEA
                         trust: unknown       validity: unknown
    [ unknown] (1). Open Job Description <openjobdescription@amazon.com>
    
    Please decide how far you trust this user to correctly verify other users' keys
    (by looking at passports, checking fingerprints from different sources, etc.)
    
      1 = I don't know or won't say
      2 = I do NOT trust
      3 = I trust marginally
      4 = I trust fully
      5 = I trust ultimately
      m = back to the main menu
    
    Your decision? 5
    Do you really want to set this key to ultimate trust? (y/N) y
    
    pub  4096R/BCC40987  created: 2024-02-09  expires: 2026-02-08  usage: SCEA
                         trust: ultimate      validity: unknown
    [ unknown] (1). Open Job Description <openjobdescription@amazon.com>
    Please note that the shown key validity is not necessarily correct
    unless you restart the program.
    
    gpg> quit
    ```

6) Verify the signature of the Open Job Description release via `gpg --verify`. The command for verifying the example files from step 1 would be:

    ```
    gpg --verify ./openjd_model-1.2.3-py3-none-any.whl.sig ./openjd_model-1.2.3-py3-none-any.whl
    ```

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This project is licensed under the Apache-2.0 License.
