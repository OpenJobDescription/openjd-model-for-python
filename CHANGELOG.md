## 0.9.0 (2026-02-02)


### Features
* Implement FEATURE_BUNDLE_1 RFC 0004 ([`86f79ee`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/86f79ee823ff15f4385b59d3e7b5224241963d50))



## 0.8.7 (2025-12-29)



### Bug Fixes
* fix crash on invalid discriminator in Optional discriminated unions (#256) ([`13e1c79`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/13e1c793f115644fc8df7534b1d6be44724cab99))


## 0.8.6 (2025-12-15)



### Bug Fixes
* handle None value for environment field in EnvironmentTemplate ([`41b2494`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/41b2494d186d7d3c7d5b4d4e67ccd6e0e2a1809e))


## 0.8.5 (2025-10-27)



### Bug Fixes
* Running in Python 3.14 produces a pydantic.v1 warning message. ([`3e9086e`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/3e9086eb6964e893920487d1ad6acd0a53bd88c0))


## 0.8.4 (2025-09-12)



### Bug Fixes
* improve error reporting when allowedValues is set to None (#184) ([`3b9c703`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/3b9c7036654ad724e806d5404701fea7990cc06f))

## 0.8.3 (2025-08-18)


### Features
* Attempting to load use CSafeLoader for faster YAML parsing where available. CSafeLoader can offer 9->11x performance improvements in some cases while still performing the safe loading methods of safe_load (#219) ([`37d3a65`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/37d3a65fe0cfe27473586005f5a22cfc109f891d))

## 0.8.2 (2025-07-08)



### Bug Fixes
* Adding a TypeAdapter cache to fix a performance regression with larger templates. ([`b62a4f1`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/b62a4f133b33bbea13da2f9dbb97e33441ffe8ca))

## 0.8.1 (2025-06-30)


### Features
* Exposing ExtensionName publicy (#200) ([`0a0cb4a`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/0a0cb4acc6d8d70f5419c4f9b49c1a1b56b01b60))

### Bug Fixes
* sdist failed to install (#198) ([`ed30b7f`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/ed30b7f38c8828a6d33969196dc8db7a74894d09))
* EnvironmentActions type was not validated properly (#197) ([`ae69150`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/ae691502f547bd845001c5f10e32175f386cbe96))

## 0.8.0 (2025-05-22)

### BREAKING CHANGES
* Creation of a DynamicConstrainedStr or FormatString now requires a model parsing context, including the Open Job Description revision and any extensions that are enabled. ([`2a8db9d`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/2a8db9d7064715079b3f7160988787c90fa93f0e))
* instantiate_model no longer accepts optional loc and within_field arguments. ([`2a8db9d`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/2a8db9d7064715079b3f7160988787c90fa93f0e))

### Features
* Added extension definition, REDACTED_ENV_VARS, for RFC-0003: Redacted Environment Variables ([`460656a`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/460656aa06d5f9e16b64a8b67f705bc80bdd31dc))


## 0.7.0 (2025-03-03)

### BREAKING CHANGES
* The IntRangeExpr class now normalizes the steps of individual range components like "3-1:-2" to be positive like "1-3:2".

### Features
* Implement 'in' operator and chunksize overide for StepParameterSpaceIterator ([`b33c6cf`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/b33c6cf00422ac8b22b94a7373631cd9f4ae42db))


## 0.6.0 (2025-02-25)

### BREAKING CHANGES

* This release includes a few small changes to the public contract of `IntRangeExpr` and the `StepParameterSpaceIterator`. Review the changes to see if this affects your usage ([`9253018`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/925301888ea997a7f4a0d4aae6638ed49b12a800)).
* Model classes migrated from Pydantic V1 to Pydantic V2, which is not backwards compatible. If you depend on Pydantic V1 APIs, consult this [guide](https://docs.pydantic.dev/latest/migration/) to migrate usage to Pydantic V2.([`0753a1b`](https://github.com/OpenJobDescription/openjd-model-for-python/pull/164/commits/0753a1bfe2ee2306f12af8b914a61116c81c5d4d)).

### Features
* Implement step parameter space iteration for chunks ([`9253018`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/925301888ea997a7f4a0d4aae6638ed49b12a800))
* Implement the task chunking RFC 0001 ([`c51683e`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/c51683e5196af68e691a5847c4c55f10490282ad))
* Implement the extensions RFC 0002 ([`cd0e289`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/cd0e2892174b0fbff46e0c7a220f6a3815a973e6))

## 0.5.1 (2024-11-08)




## 0.5.0 (2024-11-05)

### BREAKING CHANGES
* compatibility with pydantic v2 (#148) ([`c359496`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/c359496b6485da9cf2793eb9105fe5012e0292cb))


### Bug Fixes
* format string errors no longer embed the entire format string (#135) ([`5872f7c`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/5872f7c6b301fc8f2bcc76412d7964fcf970fca3))

## 0.4.4 (2024-06-24)


### Features
* add merge_job_parameter_definitions to public api (#126) ([`c2c4fae`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/c2c4fae39494313a2eb67fd6cb5d2080f2b14b94))


## 0.4.3 (2024-06-11)



### Bug Fixes
* fix lint, Break up long regex over multiple lines (#116) ([`3801c80`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/3801c8034956112954c6f76a6cedf49e6d5a7f31))

## 0.4.2 (2024-03-27)


### Features
* add validation that associative op&#39;s args are equal length (#96) ([`5d3c9bb`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/5d3c9bbd8c9b2e2c1dbc259bbd01f581edf28455))


## 0.4.1 (2024-02-26)



### Bug Fixes
* correct the bad &#39;\Z&#39; escape sequence in a regex (#79) ([`a1cf4b0`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/a1cf4b00f8615592703a90433ef2fc019b421817))
* update homepage url (#76) ([`f33810b`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/f33810bd735844d5539f16670302093682cbf5fa))

## 0.4.0 (2024-02-13)

### BREAKING CHANGES
* public release (#69) ([`14af439`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/14af43964756718dfa1690562adf79d678a3627d))



## 0.3.1 (2024-02-12)



### Bug Fixes
* no longer shortcircuit validation if there are parameter reference errors (#71) ([`d554bfd`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/d554bfd7a5b23ee04ff80b98dd7c1a1cbcfb5590))

## 0.3.0 (2024-02-08)

### BREAKING CHANGES
* redefine model versioning enums (#44) ([`c90352f`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/c90352f43e155216cba564872148349066e3b356))

### Features
* suggest template variables when symbol is unknown (#48) ([`435971a`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/435971ac240c5fedf1c24310e9a3f50d487abaf6))
* Extend IntRangeExpression and make it an external interface ([`df7071c`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/df7071c4f81abc579d020ad5ed56a70b4a9d51b1))
* Add topo_sorted() function to the StepDependencyGraph ([`9a49c41`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/9a49c417336b34670e95834630dfbf07956909c7))

### Bug Fixes
* improve validation errors when parameter defs have errors (#47) ([`6ba9a72`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/6ba9a724b35c5cc4bab68a5d2e6f6e69fa3ed85a))
* Support iterating zero-dimensional step parameter spaces ([`c891ee1`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/c891ee1d3feed627b707bc42a2628010e61e634c))

## 0.2.0 (2024-01-18)

### BREAKING CHANGES
* Add PATH parameter handling logic to preprocess_job_parameters() (#39) ([`9d8d08c`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/9d8d08c44facc50d68b718c89cb6123b36605345))

### Features
* adds merge_job_parameter_definitions() (#32) ([`ad944eb`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/ad944eb906abd4b6f2ca7f8a12b68f51653eda55))
* adds model_to_object() function (#34) ([`c6d7752`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/c6d7752357a0fb93ea073612c33474d84d37d6c8))
* implement semantics for merging a job parameter&#39;s definitions (#30) ([`9c43b24`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/9c43b241049c16896c1c3bebd30963e62f7f3987))
* add model for EnvironmentTemplate to 2023-09 (#20) ([`454f4f2`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/454f4f25705657a6fd0e65a57f27968ea005cd1b))

### Bug Fixes
* incorrect type for default in JobIntParameterDefinition (#36) ([`cc249b9`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/cc249b90cb743b9ed44daffd74a29e4805c01cee))
* crash when missing hostRequirement name (#35) ([`47a3e60`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/47a3e60d5f51ddfe283a47a5a43f15dc8a4f5587))

## 0.1.2 (2023-10-27)




## 0.1.1 (2023-09-15)

### BREAKING CHANGES
* remove ValidationError and FormatString.validate ([`a145a1b`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/a145a1ba018a3868229f183be8ba38927f6eab0a))

### Features
* improve validation error messaging (#13) ([`bc3497f`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/bc3497f9ff2fb1cbf50e686e05f290092b2cda9d))

### Bug Fixes
* make typed union disciminators function correctly ([`55982f3`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/55982f393e6e12c5b5f78f0ec1f59ce797d29770))

## 0.1.0 (2023-09-12)

### BREAKING CHANGES
* Import from internal repository (#1) ([`cb887a1`](https://github.com/OpenJobDescription/openjd-model-for-python/commit/cb887a16e27352959e2070182c58f3c0610b13fe))



