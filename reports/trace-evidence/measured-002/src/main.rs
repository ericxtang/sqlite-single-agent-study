mod dml;
mod replace;
mod format;
mod cte;
mod analyze;
mod pagelimit;
mod subquery;
mod reindex;
mod settings;
mod windowdef;
mod rowvalue;
mod vacuum;
mod persistence;
mod value;mod lex;mod ast;mod parser;mod func;mod date;mod jsonfunc;mod query;mod db;mod storage;mod render;mod locking;mod schema;mod journal;mod schema_edit;mod introspect;
use std::io::{self,BufRead,Write};
use serde_json::{Value,json};
fn main(){let stdin=io::stdin();let mut stdout=io::BufWriter::new(io::stdout().lock());let mut conn:Option<db::Connection>=None;for line in stdin.lock().lines(){let line=match line{Ok(s)=>s,Err(_)=>break};let result=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||->Result<query::Rel,String>{let v:Value=serde_json::from_str(&line).map_err(|e|e.to_string())?;match v.get("op").and_then(Value::as_str).ok_or("missing op")?{"open"=>{conn=None;let p=v.get("path").and_then(Value::as_str).ok_or("missing path")?;conn=Some(db::Connection::open(p)?);Ok(query::Rel::default())},"close"=>{conn=None;Ok(query::Rel::default())},"execute"=>{let c=conn.as_mut().ok_or("no open database connection")?;let sql=v.get("sql").and_then(Value::as_str).ok_or("missing sql")?;c.execute(sql)},_=>Err("unknown operation".into())}}));let response=match result{Ok(Ok(r))=>json!({"ok":true,"columns":r.fields.iter().map(|f|f.name.clone()).collect::<Vec<_>>(),"rows":r.rows.iter().map(|r|r.iter().map(|v|v.cell()).collect::<Vec<_>>()).collect::<Vec<_>>()}),Ok(Err(e))=>json!({"ok":false,"error":e}),Err(_)=>json!({"ok":false,"error":"internal execution error"})};if writeln!(stdout,"{}",response).and_then(|_|stdout.flush()).is_err(){break}}}
