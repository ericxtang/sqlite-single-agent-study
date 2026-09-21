"""No-inference capability probe against a localhost mock provider."""
import http.server,json,os,subprocess,tempfile,threading
from pathlib import Path
from datetime import datetime,timezone
from runtime_config import ROOT,config_text
from manage import save,doctor_identity
EXPECTED={'clock__curr_time','list_mcp_resource_templates','list_mcp_resources','mcp__workspace__exec','read_mcp_resource'}
class Capture(http.server.BaseHTTPRequestHandler):
    captured=[]
    def do_POST(self):
        self.captured.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
        if len(self.captured)!=1:
            self.send_response(400);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"error":{"message":"End of local probe","type":"invalid_request_error"}}');return
        item={'type':'custom_tool_call','id':'ctc_probe','call_id':'call_probe','namespace':'functions','name':'exec','input':'text(ALL_TOOLS.map(t => t.name)); text(await tools.mcp__workspace__exec({command: "printf bridge-ok"}));'}
        response={'id':'resp_probe','object':'response','status':'completed','model':'gpt-6-astra','output':[item],'usage':{'input_tokens':0,'output_tokens':0,'total_tokens':0}}
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        for event in [{'type':'response.created','response':dict(response,status='in_progress',output=[])},{'type':'response.output_item.added','output_index':0,'item':item},{'type':'response.output_item.done','output_index':0,'item':item},{'type':'response.completed','response':response}]:
            self.wfile.write(('data: '+json.dumps(event)+'\n\n').encode())
        self.wfile.flush()
    def log_message(self,*args):pass
def main():
    version=subprocess.check_output(['codex','--version'],text=True).strip()
    if version!='codex-cli 0.153.0':raise RuntimeError('Requires original CLI 0.153.0; a different CLI needs an explicit protocol adaptation and tool-surface review')
    image=json.loads((ROOT/'records/runtime-image.json').read_text())['id']
    import uuid
    name='astra-sqlite-replication-probe-'+uuid.uuid4().hex[:8]
    server=http.server.HTTPServer(('127.0.0.1',0),Capture);Capture.captured=[]
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        subprocess.run(['docker','run','-d','--name',name,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--cpus','4','--memory','4g','--pids-limit','256','--tmpfs','/tmp:rw,nosuid,size=512m',image],check=True,stdout=subprocess.DEVNULL)
        check="import importlib.util,ctypes,socket,shutil; assert importlib.util.find_spec('_sqlite3') is None; assert shutil.which('sqlite3') is None; s=socket.socket();s.settimeout(1);assert s.connect_ex(('1.1.1.1',443))!=0; print('offline-ok')"
        subprocess.run(['docker','exec',name,'python3','-c',check],check=True)
        with tempfile.TemporaryDirectory(prefix='sqlite-local-probe-') as temp:
            base=Path(temp);runtime=base/'runtime';runtime.mkdir();driver=base/'driver';driver.mkdir()
            cfg='model_provider = "probe"\n'+config_text(runtime,name,ROOT/'records/local-probe-tools.jsonl')
            cfg+='\n[model_providers.probe]\nname="Local non-inference probe"\nwire_api="responses"\nrequires_openai_auth=false\nbase_url="http://127.0.0.1:%d/v1"\nrequest_max_retries=0\nstream_max_retries=0\n'%server.server_port
            (runtime/'config.toml').write_text(cfg)
            env={'PATH':os.environ['PATH'],'HOME':temp,'CODEX_HOME':str(runtime),'TMPDIR':temp}
            r=subprocess.run(['codex','exec','--strict-config','--json','--skip-git-repo-check','-C',str(driver),'Local tool-surface probe.'],env=env,capture_output=True,text=True,timeout=60)
            # Do not persist complete requests: they include platform-supplied instructions.
            if len(Capture.captured)!=2:raise RuntimeError('Probe did not capture two requests: '+r.stderr[-1000:])
            request=Capture.captured[0];assert request['model']=='gpt-6-astra';assert request['reasoning']['effort']=='xhigh'
            assert '<skills_instructions>' not in json.dumps(request)
            outputs=[x for x in Capture.captured[1]['input'] if x.get('type')=='custom_tool_call_output']
            assert len(outputs)==1
            content=outputs[0]['output'];names=json.loads(content[1]['text'])
            if set(names)!=EXPECTED:raise RuntimeError('Unexpected callable tools: '+repr(names))
            assert 'bridge-ok' in json.dumps(content[2]);assert 'requires approval' not in json.dumps(content)
        details=json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0]
        assert details['HostConfig']['NetworkMode']=='none' and details['HostConfig']['ReadonlyRootfs']
        assert details['Config']['User']=='agent' and details['HostConfig']['CapDrop']==['ALL']
        assert not details['Mounts']
        save(ROOT/'records/doctor.json',{'passed':True,'recorded_at':datetime.now(timezone.utc).isoformat(),'inference_used':False,'cli_version':version,'callable_tools':sorted(names),'configuration':doctor_identity(),'scope':'Local no-inference surface and offline-container checks; live availability, compaction and deadline need a separate pilot'})
        print('PASS: expected tool surface; offline non-root container; no real inference.')
    finally:
        server.shutdown();server.server_close()
        subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
if __name__=='__main__':main()
