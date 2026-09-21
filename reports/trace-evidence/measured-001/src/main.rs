mod value;
mod lexer;
mod ast;
mod parser;
mod storage;
mod snapshot;
mod journal;
mod functions;
mod formatting;
mod engine;
mod compound;
mod cte;
mod memo;
mod mutate;
mod upsert;
mod pragma;
mod window;
mod datetime;
mod json;
mod trigger;
mod validate;
mod attach;
mod json_value;
mod schema;
mod jsonb;
mod sequence;
mod foreign;mod maintenance;
use std::io::{
    self,BufRead,Write
}
;
use engine::Engine;
fn main(){
    let stdin=io::stdin();
    let mut stdout=io::BufWriter::new(io::stdout());
    let mut conn:Option<Engine>=None;
    for line in stdin.lock().lines(){
        let line=match line{
            Ok(s)=>s,Err(_)=>break
        }
        ;
        let result=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||->Result<serde_json::Value,String>{
            let req:serde_json::Value=serde_json::from_str(&line).map_err(|e|e.to_string())?;
            let op=req.get("op").and_then(|v|v.as_str()).ok_or("missing op")?;
            match op{
                "open"=>{
                    conn=None;
                    let path=req.get("path").and_then(|v|v.as_str()).ok_or("missing path")?;
                    conn=Some(Engine::open(path)?);
                    Ok(engine::Relation::default().json())
                }
                ,"close"=>{
                    conn=None;
                    Ok(engine::Relation::default().json())
                }
                ,"execute"=>{
                    let sql=req.get("sql").and_then(|v|v.as_str()).ok_or("missing sql")?;
                    conn.as_mut().ok_or("no database connection is open")?.execute(sql).map(|r|r.json())
                }
                ,_=>Err(format!("unknown operation: {}",op))
            }
        }
        ));
        let response=match result{
            Ok(Ok(v))=>v,Ok(Err(e))=>serde_json::json!({
                "ok":false,"error":e
            }
            ),Err(_)=>serde_json::json!({
                "ok":false,"error":"internal execution error"
            }
            )
        }
        ;
        if serde_json::to_writer(&mut stdout,&response).is_err(){
            break
        }
        if writeln!(stdout).is_err()||stdout.flush().is_err(){
            break
        }
    }
}
