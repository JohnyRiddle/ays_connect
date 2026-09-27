"""Bounded synthetic Projects/Work HTTP gate through the isolated staging proxy."""
import json
import os
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

assert os.environ.get("PEOPLE_ACCEPTANCE_MODE")=="1"
fixture=json.loads(Path("/staging-private/projects-fixture.json").read_text())
base="http://proxy"
checks=0

def call(method,path,data=None,token=None,key=None,expect=200):
    global checks
    body=json.dumps(data).encode() if data is not None else None
    headers={"Content-Type":"application/json"}
    if token: headers["Authorization"]="Bearer "+token
    if key: headers["Idempotency-Key"]=key
    req=Request(base+path,data=body,headers=headers,method=method)
    try:
        with urlopen(req,timeout=8) as response:
            status=response.status;raw=response.read()
    except HTTPError as error:
        status=error.code;raw=error.read()
    if status!=expect: raise AssertionError(f"HTTP gate expected={expect} actual={status} path={path.split('?')[0]}")
    checks+=1
    return json.loads(raw) if raw and path!="/" else None

for attempt in range(10):
    try:
        call("GET","/")
        break
    except (URLError,AssertionError):
        if attempt==9: raise
        time.sleep(min(3,attempt+1))
manager=fixture["actors"]["manager"]
outsider=fixture["actors"]["outsider"]
auth=call("POST","/api/v1/auth/login/",{"email":manager["email"],"password":manager["password"]})
token=auth["access"]
outside=call("POST","/api/v1/auth/login/",{"email":outsider["email"],"password":outsider["password"]})["access"]
key=str(uuid.uuid4())
payload={"name":"Synthetic API project","manager":manager["employee"],"goal":"Projects HTTP gate"}
project=call("POST","/api/internal/v1/projects/",payload,token,key,201)
same=call("POST","/api/internal/v1/projects/",payload,token,key,200)
assert same["id"]==project["id"]
call("POST","/api/internal/v1/projects/",{**payload,"name":"Mismatch"},token,key,409)
project_id=project["id"];path=f"/api/internal/v1/projects/{project_id}/"
call("GET",path,token=outside,expect=404)
call("GET",path+"counters/",token=outside,expect=404)
call("GET",path+"history/",token=outside,expect=404)
stage=call("POST",path+"stages/",{"version":project["version"],"name":"Synthetic stage"},token,expect=201)
project=call("GET",path,token=token)
task_key=str(uuid.uuid4())
task_payload={"project_version":project["version"],"stage":stage["id"],"title":"Synthetic inside project",
              "responsible_target":fixture["target"],"executor_target":fixture["target"],"acceptance_policy":"author"}
inside=call("POST",path+"create-task/",task_payload,token,task_key,201)
repeat=call("POST",path+"create-task/",task_payload,token,task_key,200)
assert repeat["id"]==inside["id"]
project=call("GET",path,token=token)
standalone=call("POST","/api/internal/v1/tasks/",{"title":"Synthetic standalone for link",
                 "responsible_target":fixture["target"],"executor_target":fixture["target"],"acceptance_policy":"author"},token,expect=201)
call("POST",path+"link-task/",{"project_version":project["version"],"task_version":standalone["version"],
                  "task":standalone["id"],"stage":stage["id"]},token,expect=201)
linked=call("GET",f"/api/internal/v1/tasks/{standalone['id']}/",token=token)
assert linked["project"]["id"]==project_id
project=call("GET",path,token=token)
call("POST",path+"move-stage/",{"project_version":project["version"],"task_version":linked["version"],
                  "task":standalone["id"],"stage":None},token)
tasks=call("GET",path+"tasks/",token=token)
assert tasks["count"]==2
summary=call("GET",path+"counters/",token=token)
assert summary["available"]==2 and summary["scope"]=="accessible_tasks"
project=call("GET",path,token=token)
call("POST",path+"start/",{"version":project["version"]},token)
for task_id in (inside["id"],standalone["id"]):
    task=call("GET",f"/api/internal/v1/tasks/{task_id}/",token=token)
    for action in ("publish","start","complete","accept"):
        task=call("POST",f"/api/internal/v1/tasks/{task_id}/{action}/",{"version":task["version"]},token)
    assert task["status"]=="completed"
project=call("GET",path,token=token)
summary=call("GET",path+"counters/",token=token)
assert summary["progress_percent"]==100 and project["status"]=="active"
call("POST",path+"complete/",{"version":project["version"]},token)
final=call("GET",path,token=token)
assert final["status"]=="completed"
print(f"projects_api=PASS checks={checks} unauthorized_scope=PASS idempotent_create=PASS work_acceptance=PASS")
