// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

use pyo3_stub_gen::Result;

fn main() -> Result<()> {
    let stub = _openjd_rs::stub_info()?;
    stub.generate()?;
    Ok(())
}
