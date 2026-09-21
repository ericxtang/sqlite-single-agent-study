import json, subprocess, pathlib
p=subprocess.Popen(['/work/target/release/sqlite-agent'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
count=0
def req(x):
 p.stdin.write(json.dumps(x)+'\n');p.stdin.flush();return json.loads(p.stdout.readline())
def sql(s,expected=None,error=False,columns=None):
 global count
 r=req({'op':'execute','sql':s});count+=1
 if error: assert not r['ok'],(s,r);return
 assert r['ok'],(s,r)
 actual=[[None if v['type']=='null' else int(v['value']) if v['type']=='integer' else float(v['value']) if v['type']=='real' else v['value'] for v in row] for row in r['rows']]
 if expected is not None:assert actual==expected,(s,actual,expected)
 if columns is not None:assert r['columns']==columns,(s,r['columns'],columns)
 return r
assert req({'op':'open','path':':memory:'})['ok']
sql("SELECT 1+2, 7/2, 7/2.0, NULL=1, NULL IS NULL, 0 AND NULL, 1 OR NULL",[[3,3,3.5,None,1,0,1]])
sql("SELECT 'a''b', x'01FF', typeof(9223372036854775807), typeof(9223372036854775807+1)",[["a'b",'01FF','integer','real']])
sql("SELECT CAST('123e5' AS INTEGER), CAST('123e5' AS NUMERIC), 0xFFFFFFFFFFFFFFFF",[[123,12300000,-1]])
sql("SELECT 3 IN (1,2,NULL), 3 NOT IN (), NULL IN (), 'ABC' LIKE 'a%', 'abc' GLOB 'a?c'",[[None,1,0,1,1]])
sql("CREATE TABLE t(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, n NUMERIC DEFAULT 2, ck INTEGER CHECK(ck>0))")
sql("INSERT INTO t(name,ck) VALUES ('a',1),('b',2),('c',3) RETURNING id,name,n",[[1,'a',2],[2,'b',2],[3,'c',2]])
sql("INSERT INTO t(name,ck) VALUES ('d',4),('a',1)",error=True)
sql("SELECT count(*),sum(ck),avg(ck),min(name),max(name) FROM t",[[3,6,2,'a','c']])
sql("SELECT name,n FROM t WHERE id>1 ORDER BY id DESC LIMIT 1",[['c',2]])
sql("UPDATE t SET n=n+ck WHERE id>=2 RETURNING name,n",[['b',4],['c',5]])
sql("INSERT INTO t(name,n,ck) VALUES('b',99,4) ON CONFLICT(name) DO UPDATE SET n=excluded.n RETURNING id,n",[[2,99]])
sql("SELECT name, CASE WHEN n>10 THEN 'big' ELSE 'small' END AS size FROM t ORDER BY name",[['a','small'],['b','big'],['c','small']])
sql("SELECT n%2 AS k,count(*) FROM t GROUP BY k HAVING count(*)>1",[[1,2]])
sql("SELECT name FROM t WHERE id<0",[],columns=['name'])
sql("BEGIN");sql("DELETE FROM t WHERE id=1");sql("SAVEPOINT s");sql("INSERT INTO t(name,ck) VALUES('d',4)");sql("ROLLBACK TO s");sql("SELECT count(*) FROM t",[[2]]);sql("ROLLBACK");sql("SELECT count(*) FROM t",[[3]])
sql("CREATE TABLE u(id INTEGER PRIMARY KEY, tag TEXT)");sql("INSERT INTO u VALUES(1,'one'),(3,'three'),(4,'four')")
sql("SELECT t.id,name,tag FROM t LEFT JOIN u ON t.id=u.id ORDER BY t.id",[[1,'a','one'],[2,'b',None],[3,'c','three']])
sql("SELECT id FROM t UNION SELECT id FROM u ORDER BY id",[[1],[2],[3],[4]])
sql("SELECT name,(SELECT tag FROM u WHERE u.id=t.id) AS tag FROM t ORDER BY id",[['a','one'],['b',None],['c','three']])
sql("SELECT name FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.id=t.id) ORDER BY id",[['a'],['c']])
sql("WITH q AS (SELECT id,name FROM t WHERE id>1) SELECT name FROM q ORDER BY id",[['b'],['c']])
sql("WITH RECURSIVE cnt(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM cnt WHERE x<5) SELECT sum(x) FROM cnt",[[15]])
sql("SELECT id,row_number() OVER (ORDER BY id DESC),sum(id) OVER (ORDER BY id) FROM t ORDER BY id",[[1,3,1],[2,2,3],[3,1,6]])
sql("SELECT date('2024-02-29','+1 year'),date('2024-02-29','+1 year','floor'),datetime(0,'unixepoch'),julianday('2000-01-01 12:00:00')",[['2025-03-01','2025-02-28','1970-01-01 00:00:00',2451545]])
sql("SELECT json_extract('{\"a\":[1,2]}','$.a[1]'),json_type('null'),json_array(1,'x',NULL)",[[2,'null','[1,"x",null]']])
sql("CREATE VIEW v AS SELECT name,n FROM t");sql("SELECT * FROM v ORDER BY name",[['a',2],['b',99],['c',5]])
sql("PRAGMA foreign_keys=ON");sql("CREATE TABLE parent(id INTEGER PRIMARY KEY)");sql("CREATE TABLE child(id INTEGER PRIMARY KEY,p REFERENCES parent(id) ON DELETE CASCADE)");sql("INSERT INTO parent VALUES(1)");sql("INSERT INTO child VALUES(1,1)");sql("INSERT INTO child VALUES(2,2)",error=True);sql("DELETE FROM parent");sql("SELECT count(*) FROM child",[[0]])
sql("CREATE TABLE aff(t TEXT,nu NUMERIC,i INTEGER,r REAL,no BLOB)");sql("INSERT INTO aff VALUES('500.0','500.0','500.0','500.0','500.0')");sql("SELECT typeof(t),typeof(nu),typeof(i),typeof(r),typeof(no) FROM aff",[['text','integer','integer','real','text']])
path='/work/test-persistence.db';pathlib.Path(path).unlink(missing_ok=True)
assert req({'op':'open','path':path})['ok'];sql('CREATE TABLE durable(x)');sql('INSERT INTO durable VALUES(42)');sql('BEGIN');sql('INSERT INTO durable VALUES(43)');req({'op':'close'});assert req({'op':'open','path':path})['ok'];sql('SELECT * FROM durable',[[42]]);req({'op':'close'});pathlib.Path(path).unlink(missing_ok=True)
p.terminate();print(f'{count} smoke assertions passed')
