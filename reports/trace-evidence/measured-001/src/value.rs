use serde::{
    Serialize,Deserialize
}
;
use std::cmp::Ordering;
#[derive(Clone,Debug,Serialize,Deserialize,PartialEq)]
pub enum Value {
    Null, Integer(i64), Real(#[serde(with="real_bits")] f64), Text(String), JsonText(String), Blob(Vec<u8>)
}
#[derive(Clone,Copy,Debug,Serialize,Deserialize,PartialEq,Eq)]
pub enum Affinity {
    None, Blob, Text, Numeric, Integer, Real
}
pub fn affinity(t:&str)->Affinity {
    let t=t.to_uppercase();
    if t.contains("INT") {
        Affinity::Integer
    }
    else if ["CHAR","CLOB","TEXT"].iter().any(|s|t.contains(s)) {
        Affinity::Text
    }
    else if t.is_empty()||t.contains("BLOB") {
        Affinity::Blob
    }
    else if ["REAL","FLOA","DOUB"].iter().any(|s|t.contains(s)) {
        Affinity::Real
    }
    else {
        Affinity::Numeric
    }
}
pub fn real(f:f64)->Value {
    if f.is_nan(){
        Value::Null
    }
    else{
        Value::Real(f)
    }
}
pub fn ftext(f:f64)->String {
    if f.is_infinite(){
        return if f<0.0 {
            "-Inf"
        }
        else{
            "Inf"
        }
        .into()
    }
    let s=format!("{}",f);
    if s.contains('.')||s.contains('e'){
        s
    }
    else{
        format!("{}.0",s)
    }
}
impl Value {
    pub fn is_json(&self)->bool {matches!(self,Self::JsonText(_))}
    pub fn into_plain(self)->Self {match self {Self::JsonText(s)=>Self::Text(s),v=>v}}

    pub fn null(&self)->bool {
        matches!(self,Self::Null)
    }
    pub fn typ(&self)->&'static str {
        match self {
            Self::Null=>"null",Self::Integer(_)=>"integer",Self::Real(_)=>"real",Self::Text(_)|Self::JsonText(_)=>"text",Self::Blob(_)=>"blob"
        }
    }
    pub fn text(&self)->String {
        match self {
            Self::Null=>String::new(),Self::Integer(i)=>i.to_string(),Self::Real(f)=>sql_real_text(*f),Self::Text(s)|Self::JsonText(s)=>s.clone(),Self::Blob(b)=>String::from_utf8_lossy(b).into_owned()
        }
    }
    pub fn number(&self)->Value {
        match self {
            Self::Integer(_)|Self::Real(_)|Self::Null=>self.clone(), _=> {
                let s=self.text();
                let s=s.trim_start_matches(|c:char|c.is_ascii_whitespace());
                let p=numeric_prefix(s);
                if p.is_empty(){
                    Self::Integer(0)
                }
                else if !p.contains(['.','e','E']) {
                    p.parse::<i64>().map(Self::Integer).unwrap_or_else(|_|real(p.parse().unwrap_or(0.0)))
                }
                else {
                    real(p.parse().unwrap_or(0.0))
                }
            }
        }
    }
    pub fn int(&self)->i64 {
        match self.number() {
            Self::Integer(n)=>n,Self::Real(f)=>f as i64,_=>0
        }
    }
    pub fn float(&self)->f64 {
        match self.number() {
            Self::Integer(n)=>n as f64,Self::Real(f)=>f,_=>0.0
        }
    }
    pub fn truth(&self)->Option<bool>{
        if self.null(){
            None
        }
        else{
            Some(self.float()!=0.0)
        }
    }
    pub fn boolean(b:bool)->Self{
        Self::Integer(b as i64)
    }
    pub fn apply(&self,a:Affinity)->Self {
        match a {
            Affinity::Text=>match self {
                Self::Integer(_)|Self::Real(_)=>Self::Text(self.text()),_=>self.clone()
            }
            ,
            Affinity::Integer|Affinity::Numeric|Affinity::Real=>{
                let n=match self {
                    Self::Text(s)|Self::JsonText(s)=> {
                        let s=s.trim_matches(|c:char|c.is_ascii_whitespace());
                        if numeric_prefix(s)!=s || s.is_empty(){
                            return self.clone()
                        }
                        if let Ok(i)=s.parse::<i64>(){
                            Self::Integer(i)
                        }
                        else if let Ok(f)=s.parse::<f64>(){
                            real(f)
                        }
                        else{
                            return self.clone()
                        }
                    }
                    ,_=>self.clone()
                }
                ;
                match n {
                    Self::Integer(i) if a==Affinity::Real=>Self::Real(i as f64),Self::Real(f) if a!=Affinity::Real&&f>=i64::MIN as f64&&f<(i64::MAX as f64)&&f.trunc()==f=>Self::Integer(f as i64),_=>n
                }
            }
            ,_=>self.clone()
        }
    }
    pub fn cast(&self,t:&str)->Self {
        if self.null(){
            return Self::Null
        }
        match affinity(t){
            Affinity::Integer=>{
                match self{
                    Self::Text(_)|Self::JsonText(_)|Self::Blob(_)=>{
                        let s=self.text();
                        let s=s.trim_start_matches(|c:char|c.is_ascii_whitespace());
                        let b=s.as_bytes();
                        let mut n=usize::from(b.first()==Some(&b'+')||b.first()==Some(&b'-'));
                        while n<b.len()&&b[n].is_ascii_digit(){
                            n+=1
                        }
                        Self::Integer(s[..n].parse().unwrap_or_else(|_|if n>1 {
                            if s.starts_with('-'){
                                i64::MIN
                            }
                            else{
                                i64::MAX
                            }
                        }
                        else{
                            0
                        }
                        ))
                    }
                    ,_=>Self::Integer(self.int())
                }
            }
            ,Affinity::Real=>real(self.float()),Affinity::Numeric=>match self{
                Self::Integer(_)|Self::Real(_)=>self.clone(),_=>match self.number(){
                    Self::Real(f) if f>=-2251799813685248.0&&f<2251799813685248.0&&f.trunc()==f=>Self::Integer(f as i64),
                    value=>value
                }
            }
            ,Affinity::Text=>Self::Text(self.text()),_=>Self::Blob(match self{
                Self::Blob(b)=>b.clone(),_=>self.text().into_bytes()
            }
            )
        }
    }
    pub fn json(&self)->serde_json::Value{
        use serde_json::json;
        match self{
            Self::Null=>json!({
                "type":"null"
            }
            ),Self::Integer(i)=>json!({
                "type":"integer","value":i.to_string()
            }
            ),Self::Real(f)=>json!({
                "type":"real","value":ftext(*f)
            }
            ),Self::Text(s)|Self::JsonText(s)=>json!({
                "type":"text","value":s
            }
            ),Self::Blob(b)=>json!({
                "type":"blob","value":hex(b)
            }
            )
        }
    }
}
pub fn hex(b:&[u8])->String {
    b.iter().map(|x|format!("{:02X}",x)).collect()
}
pub fn unhex(s:&str)->Option<Vec<u8>>{
    if s.len()%2!=0{
        return None
    }
    (0..s.len()).step_by(2).map(|i|u8::from_str_radix(s.get(i..i+2)?,16).ok()).collect()
}
pub fn numeric_prefix(s:&str)->&str {
    let b=s.as_bytes();
    let mut i=0;
    if b.first()==Some(&b'+')||b.first()==Some(&b'-'){
        i+=1
    }
    let start=i;
    while i<b.len()&&b[i].is_ascii_digit(){
        i+=1
    }
    let mut digits=i-start;
    if i<b.len()&&b[i]==b'.'{
        i+=1;
        let j=i;
        while i<b.len()&&b[i].is_ascii_digit(){
            i+=1
        }
        digits+=i-j;
    }
    if digits==0{
        return ""
    }
    if i<b.len()&&(b[i]==b'e'||b[i]==b'E'){
        let old=i;
        i+=1;
        if i<b.len()&&(b[i]==b'+'||b[i]==b'-'){
            i+=1
        }
        let j=i;
        while i<b.len()&&b[i].is_ascii_digit(){
            i+=1
        }
        if i==j{
            i=old
        }
    }
    &s[..i]
}
pub fn compare_affinity(a:&Value,b:&Value,aa:Affinity,ba:Affinity,collation:&str)->Ordering{
    let mut x=a.clone();let mut y=b.clone();
    let numeric=|affinity|matches!(affinity,Affinity::Integer|Affinity::Real|Affinity::Numeric);
    if numeric(aa)&&!numeric(ba){y=y.apply(Affinity::Numeric);}
    else if numeric(ba)&&!numeric(aa){x=x.apply(Affinity::Numeric);}
    else if aa==Affinity::Text&&ba==Affinity::None{y=y.apply(Affinity::Text);}
    else if ba==Affinity::Text&&aa==Affinity::None{x=x.apply(Affinity::Text);}
    compare(&x,&y,collation)
}
pub fn compare(a:&Value,b:&Value,coll:&str)->Ordering {
    use Value::*;
    match(a,b){
        (Null,Null)=>Ordering::Equal,(Null,_)=>Ordering::Less,(_,Null)=>Ordering::Greater,(Integer(a),Integer(b))=>a.cmp(b),(Real(a),Real(b))=>a.partial_cmp(b).unwrap_or(Ordering::Equal),(Integer(a),Real(b))=>int_real(*a,*b),(Real(a),Integer(b))=>int_real(*b,*a).reverse(),(Text(a)|JsonText(a),Text(b)|JsonText(b))=>match coll.to_ascii_lowercase().as_str(){
            "nocase"=>a.split('\0').next().unwrap_or("").to_ascii_lowercase().cmp(&b.split('\0').next().unwrap_or("").to_ascii_lowercase()).then_with(||a.len().cmp(&b.len())),"rtrim"=>a.trim_end_matches(' ').cmp(b.trim_end_matches(' ')),_=>a.cmp(b)
        }
        ,(Blob(a),Blob(b))=>a.cmp(b),_=>rank(a).cmp(&rank(b))
    }
}
fn rank(v:&Value)->u8 {
    match v{
        Value::Null=>0,Value::Integer(_)|Value::Real(_)=>1,Value::Text(_)|Value::JsonText(_)=>2,Value::Blob(_)=>3
    }
}
fn int_real(i:i64,f:f64)->Ordering{
    if f>=9223372036854775808.0{
        return Ordering::Less
    }
    if f< -9223372036854775808.0{
        return Ordering::Greater
    }
    let x=f as i64;
    let c=i.cmp(&x);
    if c==Ordering::Equal{
        (i as f64).partial_cmp(&f).unwrap_or(c)
    }
    else{
        c
    }
}
fn sql_real_text(f:f64)->String{
    if !f.is_finite(){
        return ftext(f)
    }
    if f==0.0{
        return "0.0".into()
    }
    let scientific=format!("{:.14e}",f);
    let (mantissa,exp)=scientific.split_once('e').unwrap();
    let exp=exp.parse::<i32>().unwrap();
    if !(-4..15).contains(&exp){
        let mut m=mantissa.trim_end_matches('0').to_string();
        if m.ends_with('.') {
            m.push('0')
        }
        format!("{}e{}{:02}",m,if exp<0{
            '-'
        }
        else{
            '+'
        }
        ,exp.abs())
    }
    else{
        let mut s=format!("{:.*}",(14-exp).max(0) as usize,f);
        if s.contains('.') {
            while s.ends_with('0'){
                s.pop();
            }
            if s.ends_with('.') {
                s.push('0')
            }
        }
        else{
            s.push_str(".0")
        }
        s
    }
}
// Snapshot serialization preserves all IEEE-754 values, including infinities.
mod real_bits {
    use serde::{
        Serializer,Deserializer,de::{
            Visitor,Error
        }
    }
    ;
    pub fn serialize<S:Serializer>(f:&f64,s:S)->Result<S::Ok,S::Error>{
        s.serialize_str(&format!("{:016x}",f.to_bits()))
    }
    pub fn deserialize<'de,D:Deserializer<'de>>(d:D)->Result<f64,D::Error>{
        struct Float;
        impl<'de> Visitor<'de> for Float{
            type Value=f64;
            fn expecting(&self,f:&mut std::fmt::Formatter)->std::fmt::Result{
                write!(f,"IEEE-754 bit string or numeric value")
            }
            fn visit_str<E:Error>(self,s:&str)->Result<f64,E>{
                u64::from_str_radix(s,16).map(f64::from_bits).map_err(E::custom)
            }
            fn visit_f64<E:Error>(self,f:f64)->Result<f64,E>{
                Ok(f)
            }
            fn visit_i64<E:Error>(self,i:i64)->Result<f64,E>{
                Ok(i as f64)
            }
            fn visit_u64<E:Error>(self,i:u64)->Result<f64,E>{
                Ok(i as f64)
            }
        }
        d.deserialize_any(Float)
    }
}
