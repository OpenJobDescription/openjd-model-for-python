use pyo3_stub_gen::Result;

fn main() -> Result<()> {
    let stub = _openjd_rs::stub_info()?;
    stub.generate()?;
    Ok(())
}
