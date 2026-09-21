use serde::{Serialize,Deserialize};
use std::cmp::Ordering;
#[derive(Clone,Debug,Serialize,Deserialize,PartialEq)]
pub enum Val { Null, Int(i64), Real(f64), Text(String), Blob(Vec<u8>), Json(String) }
#[derive(Clone,Copy,Debug,Serialize,Deserialize,PartialEq,Eq)]
pub enum Aff { None, Blob, Text, Numeric, Integer, Real }
pub fn affinity(t:&str)->Aff { let t=t.to_ascii_uppercase(); if t.contains("INT"){Aff::Integer}else if t.contains("CHAR")||t.contains("CLOB")||t.contains("TEXT"){Aff::Text}else if t.is_empty()||t.contains("BLOB"){Aff::Blob}else if t.contains("REAL")||t.contains("FLOA")||t.contains("DOUB"){Aff::Real}else{Aff::Numeric} }
pub fn realstr(f:f64)->String { if f.is_infinite(){return if f>0.0{"Inf"}else{"-Inf"}.into()} let s=f.to_string(); if !s.contains('.')&&!s.contains('e') {format!("{}.0",s)}else{s} }
pub fn hex(b:&[u8])->String{b.iter().map(|v|format!("{:02X}",v)).collect()}
pub fn unhex(s:&str)->Option<Vec<u8>>{if s.len()%2!=0{return None} (0..s.len()).step_by(2).map(|i|u8::from_str_radix(s.get(i..i+2)?,16).ok()).collect()}
impl Val {
 pub fn cell(&self)->serde_json::Value {use serde_json::json; match self {Self::Null=>json!({"type":"null"}), Self::Int(i)=>json!({"type":"integer","value":i.to_string()}),Self::Real(r)=>json!({"type":"real","value":realstr(*r)}),Self::Text(s)|Self::Json(s)=>json!({"type":"text","value":s}),Self::Blob(b)=>json!({"type":"blob","value":hex(b)})} }
 pub fn kind(&self)->&'static str{match self{Self::Null=>"null",Self::Int(_)=>"integer",Self::Real(_)=>"real",Self::Text(_)|Self::Json(_)=>"text",Self::Blob(_)=>"blob"}}
 pub fn null(&self)->bool{matches!(self,Self::Null)}
 pub fn text(&self)->String{match self{Self::Null=>String::new(),Self::Int(i)=>i.to_string(),Self::Real(r)=>realstr(*r),Self::Text(s)|Self::Json(s)=>s.clone(),Self::Blob(b)=>String::from_utf8_lossy(b).into_owned()}}
 pub fn bytes(&self)->Vec<u8>{if let Self::Blob(b)=self{b.clone()}else{self.text().into_bytes()}}
 pub fn num(&self)->Val{match self{Self::Int(_)|Self::Real(_)|Self::Null=>self.clone(),_=>{let s=self.text(); let p=num_prefix(&s,false); if p.is_empty(){return Self::Int(0)}if !p.contains(['.','e','E']){if let Ok(i)=p.parse(){return Self::Int(i)}} Self::real(p.parse().unwrap_or(0.0))}}}
 pub fn real(f:f64)->Self{if f.is_nan(){Self::Null}else{Self::Real(f)}}
 pub fn float(&self)->f64{match self.num(){Self::Int(i)=>i as f64,Self::Real(r)=>r,_=>0.0}}
 pub fn int(&self)->i64{match self{Self::Int(i)=>*i,Self::Real(r)=>*r as i64,Self::Null=>0,_=>{let s=self.text();let p=num_prefix(&s,true);p.parse::<i64>().unwrap_or_else(|_|p.parse::<f64>().unwrap_or(0.0) as i64)}}}
 pub fn truth(&self)->Option<bool>{if self.null(){None}else{Some(self.float()!=0.0)}}
 pub fn boolean(b:bool)->Self{Self::Int(b as i64)}
 pub fn apply(&self,a:Aff)->Self{if let Self::Json(s)=self{return Self::Text(s.clone()).apply(a)}match a{Aff::Text=>if matches!(self,Self::Int(_)|Self::Real(_)){Self::Text(self.text())}else{self.clone()},Aff::Integer|Aff::Numeric|Aff::Real=>{let v=match self{Self::Text(s)=>{let t=s.trim();if t.is_empty()||t.starts_with("0x")||t.starts_with("0X")||num_prefix(t,false)!=t {return self.clone()}if let Ok(i)=t.parse::<i64>(){Self::Int(i)}else if let Ok(f)=t.parse::<f64>(){Self::real(f)}else{return self.clone()}},_=>self.clone()};match v{Self::Int(i) if a==Aff::Real=>Self::Real(i as f64),Self::Real(f) if a!=Aff::Real&&f>=i64::MIN as f64&&f<(i64::MAX as f64)&&f.fract()==0.0=>Self::Int(f as i64),_=>v}},_=>self.clone()}}
 pub fn cast(&self,t:&str)->Self{if self.null(){return Self::Null}match affinity(t){Aff::Integer=>Self::Int(self.int()),Aff::Real=>Self::real(self.float()),Aff::Text=>Self::Text(self.text()),Aff::Blob|Aff::None=>Self::Blob(self.bytes()),Aff::Numeric=>{if matches!(self,Self::Int(_)|Self::Real(_)){return self.clone()}let n=self.num();match n{Self::Real(f)if f.fract()==0.0&&f.abs()<2251799813685248.0=>Self::Int(f as i64),_=>n}}}}
}
pub fn num_prefix(s:&str,integer:bool)->&str {let s=s.trim_start(); let b=s.as_bytes(); let mut i=0;if matches!(b.first(),Some(b'+')|Some(b'-')){i+=1}let mut digits=0;while i<b.len()&&b[i].is_ascii_digit(){i+=1;digits+=1}if !integer&&b.get(i)==Some(&b'.'){i+=1;while i<b.len()&&b[i].is_ascii_digit(){i+=1;digits+=1}}if digits==0{return ""}if !integer&&matches!(b.get(i),Some(b'e')|Some(b'E')){let start=i;i+=1;if matches!(b.get(i),Some(b'+')|Some(b'-')){i+=1}let beg=i;while i<b.len()&&b[i].is_ascii_digit(){i+=1}if beg==i{i=start}}&s[..i]}
fn rank(v:&Val)->u8{match v{Val::Null=>0,Val::Int(_)|Val::Real(_)=>1,Val::Text(_)|Val::Json(_)=>2,Val::Blob(_)=>3}}
pub fn cmp(a:&Val,b:&Val,coll:&str)->Ordering{match(a,b){(Val::Null,Val::Null)=>Ordering::Equal,(Val::Int(x),Val::Int(y))=>x.cmp(y),(Val::Int(x),Val::Real(y))=>intreal(*x,*y),(Val::Real(x),Val::Int(y))=>intreal(*y,*x).reverse(),(Val::Real(x),Val::Real(y))=>x.partial_cmp(y).unwrap_or(Ordering::Equal),(Val::Text(x)|Val::Json(x),Val::Text(y)|Val::Json(y))=>match coll.to_ascii_uppercase().as_str(){"NOCASE"=>x.to_ascii_lowercase().cmp(&y.to_ascii_lowercase()),"RTRIM"=>x.trim_end_matches(' ').cmp(y.trim_end_matches(' ')),_=>x.as_bytes().cmp(y.as_bytes())},(Val::Blob(x),Val::Blob(y))=>x.cmp(y),_=>rank(a).cmp(&rank(b))}}
fn intreal(i:i64,r:f64)->Ordering{if r>=9223372036854775808.0{return Ordering::Less}if r< -9223372036854775808.0{return Ordering::Greater}let j=r as i64;let c=i.cmp(&j);if c!=Ordering::Equal{c}else{(i as f64).partial_cmp(&r).unwrap_or(Ordering::Equal)}}

