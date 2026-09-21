use serde::{Serialize,Deserialize};
use std::cmp::Ordering;
#[derive(Clone,Debug,Serialize,Deserialize,PartialEq)]
pub enum V { Null, Int(i64), Real(f64), Text(String), Blob(Vec<u8>) }
impl V {
 pub fn null(&self)->bool {matches!(self,V::Null)}
 pub fn kind(&self)->&'static str {match self {V::Null=>"null",V::Int(_)=>"integer",V::Real(_)=>"real",V::Text(_)=>"text",V::Blob(_)=>"blob"}}
 pub fn text(&self)->String {match self {V::Null=>String::new(),V::Int(i)=>i.to_string(),V::Real(f)=>real_text(*f),V::Text(s)=>s.clone(),V::Blob(b)=>String::from_utf8_lossy(b).into_owned()}}
 pub fn numeric(&self)->V {match self {V::Int(_)|V::Real(_)|V::Null=>self.clone(),_=>num_prefix(&self.text())}}
 pub fn f64(&self)->f64 {match self.numeric() {V::Int(i)=>i as f64,V::Real(f)=>f,_=>0.0}}
 pub fn i64(&self)->i64 {match self {V::Int(i)=>*i,V::Real(f)=>*f as i64,V::Text(s)=>int_prefix(s),V::Blob(b)=>int_prefix(&String::from_utf8_lossy(b)),_=>0}}
 pub fn truth(&self)->Option<bool> {if self.null(){None}else{Some(self.f64()!=0.0)}}
 pub fn bool(b:bool)->V {V::Int(b as i64)}
 pub fn json(&self)->serde_json::Value {match self {V::Null=>serde_json::json!({"type":"null"}),V::Blob(b)=>serde_json::json!({"type":"blob","value":hex(b)}),_=>serde_json::json!({"type":self.kind(),"value":self.text()})}}
 pub fn affinity(self,a:char)->V {match a {'T'=>match self {V::Int(_)|V::Real(_)=>V::Text(self.text()),_=>self},'I'|'N'|'R'=>{let v=match &self {V::Text(s)=>parse_num(s.trim()).unwrap_or(self),_=>self};match v {V::Int(i) if a=='R'=>V::Real(i as f64),V::Real(f) if a!='R' && f.is_finite() && f>=i64::MIN as f64 && f<(i64::MAX as f64) && f.fract()==0.0=>V::Int(f as i64),_=>v}},_=>self}}
 pub fn cast(&self,t:&str)->V {if self.null(){return V::Null} match affinity(t) {'T'=>V::Text(self.text()),'B'=>V::Blob(match self {V::Blob(b)=>b.clone(),_=>self.text().into_bytes()}),'I'=>V::Int(self.i64()),'R'=>V::Real(self.f64()),_=>match self{V::Int(_)|V::Real(_)=>self.clone(),_=>self.numeric().affinity('N')}}}
}
pub fn real_text(f:f64)->String {if f.is_infinite(){return if f>0.0{"Inf".into()}else{"-Inf".into()}}let s=f.to_string();if !s.contains('.')&&!s.contains('e'){format!("{}.0",s)}else{s}}
pub fn hex(b:&[u8])->String {b.iter().map(|x|format!("{:02X}",x)).collect()}
pub fn unhex(s:&str)->Option<Vec<u8>> {if s.len()%2!=0{return None}(0..s.len()).step_by(2).map(|i|u8::from_str_radix(s.get(i..i+2)?,16).ok()).collect()}
pub fn affinity(t:&str)->char {let t=t.to_ascii_uppercase();if t.contains("INT"){'I'}else if ["CHAR","CLOB","TEXT"].iter().any(|s|t.contains(s)){'T'}else if t.is_empty()||t.contains("BLOB"){'B'}else if ["REAL","FLOA","DOUB"].iter().any(|s|t.contains(s)){'R'}else{'N'}}
pub fn parse_num(s:&str)->Option<V> {if s.is_empty()||s.starts_with("0x")||s.eq_ignore_ascii_case("nan")||s.to_ascii_lowercase().contains("inf"){return None}if let Ok(i)=s.parse::<i64>(){return Some(V::Int(i))}s.parse::<f64>().ok().map(V::Real)}
pub fn int_prefix(s:&str)->i64 {let s=s.trim_start();let b=s.as_bytes();let mut n=usize::from(b.first()==Some(&b'+')||b.first()==Some(&b'-'));let start=n;while n<b.len()&&b[n].is_ascii_digit(){n+=1}if n==start {0}else{s[..n].parse().unwrap_or(if s.starts_with('-'){i64::MIN}else{i64::MAX})}}
pub fn num_prefix(s:&str)->V {let s=s.trim_start();let b=s.as_bytes();let mut n=usize::from(b.first()==Some(&b'+')||b.first()==Some(&b'-'));let mut digits=0;while n<b.len()&&b[n].is_ascii_digit(){n+=1;digits+=1}if b.get(n)==Some(&b'.'){n+=1;while n<b.len()&&b[n].is_ascii_digit(){n+=1;digits+=1}}if digits==0{return V::Int(0)}if matches!(b.get(n),Some(b'e'|b'E')){let e=n;n+=1;if matches!(b.get(n),Some(b'+'|b'-')){n+=1}let d=n;while n<b.len()&&b[n].is_ascii_digit(){n+=1}if n==d {n=e}}parse_num(&s[..n]).unwrap_or(V::Int(0))}
pub fn cmp(a:&V,b:&V,coll:&str)->Ordering {use V::*;match (a,b){(Null,Null)=>Ordering::Equal,(Null,_)=>Ordering::Less,(_,Null)=>Ordering::Greater,(Int(x),Int(y))=>x.cmp(y),(Int(x),Real(y))=>int_real_cmp(*x,*y),(Real(x),Int(y))=>int_real_cmp(*y,*x).reverse(),(Real(x),Real(y))=>x.partial_cmp(y).unwrap_or(Ordering::Equal),(Int(_)|Real(_),_)=>Ordering::Less,(_,Int(_)|Real(_))=>Ordering::Greater,(Text(x),Text(y))=>match coll.to_ascii_lowercase().as_str(){"nocase"=>x.to_ascii_lowercase().cmp(&y.to_ascii_lowercase()),"rtrim"=>x.trim_end_matches(' ').cmp(y.trim_end_matches(' ')),_=>x.cmp(y)},(Text(_),Blob(_))=>Ordering::Less,(Blob(_),Text(_))=>Ordering::Greater,(Blob(x),Blob(y))=>x.cmp(y)}}
fn int_real_cmp(i:i64,f:f64)->Ordering {if f>=9223372036854775808.0{return Ordering::Less}if f< -9223372036854775808.0{return Ordering::Greater}let c=i.cmp(&(f as i64));if c==Ordering::Equal {(i as f64).partial_cmp(&f).unwrap_or(c)}else{c}}
