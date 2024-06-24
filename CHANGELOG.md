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



