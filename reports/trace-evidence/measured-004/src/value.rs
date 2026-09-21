use serde::{Serialize, Deserialize};
use std::cmp::Ordering;
#[derive(Clone,Debug,Serialize,Deserialize,PartialEq)]
pub enum V {
    Null,
    Int(i64),
    Real(
        #[serde(with="float_serde")]
        f64),
    Text(String),
    Blob(Vec<u8>),
}
pub fn real(f: f64) -> V { if f.is_nan() { V::Null } else { V::Real(f) } }
pub fn affinity(t: &str) -> char {
    let t = t.to_ascii_uppercase();
    if t.contains("INT") {
        'I'
    } else if ["CHAR", "CLOB", "TEXT"].iter().any(|s| t.contains(s)) {
        'T'
    } else if t.is_empty() || t.contains("BLOB") {
        'B'
    } else if ["REAL", "FLOA", "DOUB"].iter().any(|s| t.contains(s)) {
        'R'
    } else { 'N' }
}
impl V {
    pub fn null(&self) -> bool { matches!(self,V::Null) }
    pub fn kind(&self) -> &'static str {
        match self {
            V::Null => "null",
            V::Int(_) => "integer",
            V::Real(_) => "real",
            V::Text(_) => "text",
            V::Blob(_) => "blob",
        }
    }
    pub fn text(&self) -> String {
        match self {
            V::Null => String::new(),
            V::Int(i) => i.to_string(),
            V::Real(f) => format_general(*f, 15, true, false),
            V::Text(s) => s.clone(),
            V::Blob(b) => String::from_utf8_lossy(b).into_owned(),
        }
    }
    pub fn numeric(&self) -> V {
        match self {
            V::Text(s) => parse_number(s, false),
            V::Blob(b) => parse_number(&String::from_utf8_lossy(b), false),
            _ => self.clone(),
        }
    }
    pub fn f64(&self) -> f64 {
        match self.numeric() {
            V::Int(i) => i as f64,
            V::Real(f) => f,
            _ => 0.0,
        }
    }
    pub fn i64(&self) -> i64 {
        match self.numeric() {
            V::Int(i) => i,
            V::Real(f) => f as i64,
            _ => 0,
        }
    }
    pub fn truth(&self) -> Option<bool> {
        if self.null() { None } else { Some(self.f64() != 0.0) }
    }
    pub fn apply(&self, a: char) -> V {
        match a {
            'T' =>
                match self {
                    V::Int(_) | V::Real(_) => V::Text(self.text()),
                    _ => self.clone(),
                },
            'I' | 'N' | 'R' => {
                let v =
                    match self {
                        V::Text(s) => parse_number(s, true),
                        _ => self.clone(),
                    };
                match v {
                    V::Int(i) if a == 'R' => V::Real(i as f64),
                    V::Real(f) if
                        a != 'R' && f >= i64::MIN as f64 && f < (i64::MAX as f64) &&
                            f.fract() == 0.0 => V::Int(f as i64),
                    _ => v,
                }
            }
            _ => self.clone(),
        }
    }
    pub fn cast(&self, t: &str) -> V {
        if self.null() { return V::Null }
        match affinity(t) {
            'T' => V::Text(self.text()),
            'B' =>
                V::Blob(match self {
                        V::Blob(b) => b.clone(),
                        _ => self.text().into_bytes(),
                    }),
            'I' => {
                let s = self.text();
                let s = s.trim_start();
                let n =
                    s.char_indices().take_while(|(i, c)|
                                        c.is_ascii_digit() ||
                                            (*i == 0 &&
                                                    (*c == '+' ||
                                                            *c ==
                                                                '-'))).last().map(|(i, c)| i + c.len_utf8()).unwrap_or(0);
                V::Int(if matches!(self,V::Text(_)|V::Blob(_)) {
                        s[..n].parse::<i64>().unwrap_or_else(|_|
                                if !s[..n].chars().any(|c| c.is_ascii_digit()) {
                                    0
                                } else if s.starts_with('-') { i64::MIN } else { i64::MAX })
                    } else { self.i64() })
            }
            'R' => real(self.f64()),
            _ => {
                let n = self.numeric();
                if matches!(self,V::Text(_)|V::Blob(_)) {
                    match n {
                        V::Real(f) if f.abs() >= 2251799813685248.0 => V::Real(f),
                        n => n.apply('N'),
                    }
                } else { n }
            }
        }
    }
    pub fn json(&self) -> serde_json::Value {
        if self.null() {
            serde_json::json!({"type":"null"})
        } else {
            let s =
                match self {
                    V::Blob(b) =>
                        b.iter().map(|x| format!("{:02x}",x)).collect(),
                    V::Real(f) => {
                        let s = f.to_string();
                        if f.is_finite() && !s.contains('.') && !s.contains('e') {
                            format!("{}.0",s)
                        } else { s }
                    }
                    _ => self.text(),
                };
            serde_json::json!({"type":self.kind(),"value":s})
        }
    }
}
pub fn parse_number(s: &str, strict: bool) -> V {
    let t = s.trim();
    if strict {
        if let Ok(i) = t.parse::<i64>() { return V::Int(i) }
        if t.chars().all(|c| c.is_ascii_digit() || "+-.eE".contains(c)) {
            if let Ok(f) = t.parse::<f64>() { return real(f) }
        }
        return V::Text(s.into())
    }
    let b = t.as_bytes();
    let mut i = 0;
    if b.first() == Some(&b'+') || b.first() == Some(&b'-') { i += 1 }
    let start = i;
    while i < b.len() && b[i].is_ascii_digit() { i += 1 }
    let mut digits = i - start;
    if i < b.len() && b[i] == b'.' {
        i += 1;
        let j = i;
        while i < b.len() && b[i].is_ascii_digit() { i += 1 }
        digits += i - j
    }
    if digits == 0 { return V::Int(0) }
    if i < b.len() && (b[i] == b'e' || b[i] == b'E') {
        let old = i;
        i += 1;
        if i < b.len() && (b[i] == b'+' || b[i] == b'-') { i += 1 }
        let j = i;
        while i < b.len() && b[i].is_ascii_digit() { i += 1 }
        if i == j { i = old }
    }
    let n = &t[..i];
    if let Ok(v) = n.parse::<i64>() {
        V::Int(v)
    } else { real(n.parse().unwrap_or(0.0)) }
}
pub fn cmp(a: &V, b: &V, coll: &str) -> Ordering {
    match (a, b) {
        (V::Null, V::Null) => Ordering::Equal,
        (V::Null, _) => Ordering::Less,
        (_, V::Null) => Ordering::Greater,
        (V::Int(x), V::Int(y)) => x.cmp(y),
        (V::Int(x), V::Real(y)) => cmp_ir(*x, *y),
        (V::Real(x), V::Int(y)) => cmp_ir(*y, *x).reverse(),
        (V::Real(x), V::Real(y)) =>
            x.partial_cmp(y).unwrap_or(Ordering::Equal),
        (V::Text(x), V::Text(y)) =>
            match coll.to_ascii_uppercase().as_str() {
                "NOCASE" =>
                    x.split('\0').next().unwrap_or("").to_ascii_lowercase().cmp(&y.split('\0').next().unwrap_or("").to_ascii_lowercase()),
                "RTRIM" =>
                    x.trim_end_matches(' ').cmp(y.trim_end_matches(' ')),
                _ => x.cmp(y),
            },
        (V::Blob(x), V::Blob(y)) => x.cmp(y),
        _ => rank(a).cmp(&rank(b)),
    }
}
fn cmp_ir(i: i64, f: f64) -> Ordering {
    if f >= 9223372036854775808.0 { return Ordering::Less }
    if f < -9223372036854775808.0 { return Ordering::Greater }
    let j = f as i64;
    match i.cmp(&j) {
        Ordering::Equal =>
            (i as f64).partial_cmp(&f).unwrap_or(Ordering::Equal),
        x => x,
    }
}
fn rank(v: &V) -> u8 {
    match v {
        V::Null => 0,
        V::Int(_) | V::Real(_) => 1,
        V::Text(_) => 2,
        V::Blob(_) => 3,
    }
}
pub fn boolean(b: Option<bool>) -> V {
    match b { None => V::Null, Some(b) => V::Int(b as i64), }
}

mod float_serde {
    use serde::{Serialize, Deserialize, Serializer, Deserializer};
    pub fn serialize<S: Serializer>(f: &f64, s: S)
        -> Result<S::Ok, S::Error> {
        f.to_string().serialize(s)
    }
    pub fn deserialize<'de, D: Deserializer<'de>>(d: D)
        -> Result<f64, D::Error> {
        #[derive(Deserialize)]
        #[serde(untagged)]
        enum N { S(String), F(f64), }
        match N::deserialize(d)? {
            N::S(s) => s.parse().map_err(serde::de::Error::custom),
            N::F(f) => Ok(f),
        }
    }
}

pub fn format_general(f: f64, precision: usize, force_decimal: bool,
    upper: bool) -> String {
    if f.is_nan() { return "NaN".into() }
    if f.is_infinite() {
        return if f.is_sign_negative() { "-Inf" } else { "Inf" }.into()
    }
    if f == 0.0 { return if force_decimal { "0.0" } else { "0" }.into() }
    let precision = precision.clamp(1, 26);
    let sci = format!("{:.*e}",precision-1,f);
    let (mantissa, exponent) = sci.split_once('e').unwrap();
    let exponent = exponent.parse::<i32>().unwrap_or(0);
    let scientific = exponent < -4 || exponent >= precision as i32;
    let mut body =
        if scientific {
            mantissa.to_string()
        } else {
            format!("{:.*}",(precision as i32-exponent-1).max(0)as usize,f)
        };
    if body.contains('.') {
        while body.ends_with('0') { body.pop(); }
        if body.ends_with('.') {
            if force_decimal { body.push('0') } else { body.pop(); }
        }
    } else if force_decimal { body.push_str(".0") }
    if scientific {
        body.push(if upper { 'E' } else { 'e' });
        body.push(if exponent >= 0 { '+' } else { '-' });
        body.push_str(&format!("{:02}",exponent.abs()));
    }
    body
}
