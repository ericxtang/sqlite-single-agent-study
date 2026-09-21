mod storage;
mod json;
mod value;
mod syntax;
mod engine;
mod funcs;
use std::io::{self, BufRead, Write};
fn main() {
    let stdin = io::stdin();
    let mut stdout = io::BufWriter::new(io::stdout());
    let mut connection: Option<engine::Engine> = None;
    for line in stdin.lock().lines() {
        let line = match line { Ok(s) => s, Err(_) => break, };
        let response =
            std::panic::catch_unwind(std::panic::AssertUnwindSafe(||
                        -> Result<serde_json::Value, String>
                        {
                            let request: serde_json::Value =
                                serde_json::from_str(&line).map_err(|e| e.to_string())?;
                            match request.get("op").and_then(|v|
                                            v.as_str()).unwrap_or("") {
                                "open" => {
                                    connection = None;
                                    let path =
                                        request.get("path").and_then(|v|
                                                    v.as_str()).unwrap_or(":memory:");
                                    connection = Some(engine::Engine::open(path)?);
                                    Ok(engine::ResultSet::default().json())
                                }
                                "close" => {
                                    connection = None;
                                    Ok(engine::ResultSet::default().json())
                                }
                                "execute" => {
                                    let db =
                                        connection.as_mut().ok_or("no database connection is open")?;
                                    let sql =
                                        request.get("sql").and_then(|v|
                                                        v.as_str()).ok_or("missing SQL text")?;
                                    Ok(db.execute(sql)?.json())
                                }
                                _ => Err("unknown operation".into()),
                            }
                        }));
        let response =
            match response {
                Ok(Ok(v)) => v,
                Ok(Err(e)) => serde_json::json!({"ok":false,"error":e}),
                Err(_) =>
                    serde_json::json!({"ok":false,"error":"internal SQL evaluation error"}),
            };
        if writeln!(stdout,"{}",response).and_then(|_|
                        stdout.flush()).is_err() {
            break
        }
    }
}
