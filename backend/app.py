import os, json, uuid, base64, mimetypes
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'data'; UPLOADS=ROOT/'uploads'
DATA.mkdir(exist_ok=True); UPLOADS.mkdir(exist_ok=True)
MEM=DATA/'memory.json'
if not MEM.exists(): MEM.write_text('[]')

class Chat(BaseModel):
    message: str
    attachment_ids: list[str] = []

def memories():
    try: return json.loads(MEM.read_text())
    except: return []

def remember(x):
    a=memories(); a.append({'id':str(uuid.uuid4()),'text':x}); MEM.write_text(json.dumps(a[-500:],indent=2))

def client():
    key=os.getenv('OPENAI_API_KEY','').strip()
    return OpenAI(api_key=key) if key else None

app=FastAPI(title='Anja',version='1.2.1')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['*'],allow_headers=['*'])

@app.get('/health')
def health():
    return {'ok':True,'service':'anja'}

@app.get('/')
def home(): return FileResponse(ROOT/'frontend'/'index.html')

@app.get('/api/status')
def status():
    return {'name':'Anja','status':'online','provider':'openai' if client() else 'not_configured','model':os.getenv('ANJA_MODEL','gpt-5'),'memory':len(memories())}

@app.post('/api/upload')
async def upload(files:list[UploadFile]=File(...)):
    allowed={'.png','.jpg','.jpeg','.webp','.gif','.pdf','.docx','.txt','.md','.csv','.json'}
    out=[]
    for f in files:
        ext=Path(f.filename or '').suffix.lower()
        if ext not in allowed: raise HTTPException(400,f'Unsupported file type: {ext}')
        data=await f.read()
        if len(data)>30*1024*1024: raise HTTPException(413,'Maximum file size is 30 MB.')
        fid=str(uuid.uuid4()); p=UPLOADS/(fid+ext); p.write_bytes(data)
        out.append({'id':fid,'name':f.filename,'mime':f.content_type or mimetypes.guess_type(f.filename)[0]})
    return {'files':out}

@app.post('/api/chat')
def chat(req:Chat):
    c=client()
    if not c: return {'answer':'Anja is online, but OPENAI_API_KEY is not configured. Add the key in your deployment environment and restart the service.','provider':'not_configured'}
    content=[{'type':'input_text','text':req.message}]
    for fid in req.attachment_ids:
        found=list(UPLOADS.glob(fid+'*'))
        if not found: continue
        p=found[0]; mime=mimetypes.guess_type(p.name)[0] or 'application/octet-stream'; raw=base64.b64encode(p.read_bytes()).decode()
        if mime.startswith('image/'):
            content.append({'type':'input_image','image_url':f'data:{mime};base64,{raw}','detail':'auto'})
        else:
            content.append({'type':'input_file','file_data':f'data:{mime};base64,{raw}','filename':p.name})
    prior='\n'.join('- '+x['text'] for x in memories()[-8:])
    content.append({'type':'input_text','text':'Relevant Anja memory:\n'+(prior or '(none)')})
    response=c.responses.create(model=os.getenv('ANJA_MODEL','gpt-5'),instructions='You are Anja, an adaptive multimodal AI assistant. Answer directly, analyze supplied images/files, and never pretend you accessed information you did not receive.',input=[{'role':'user','content':content}])
    remember(req.message)
    return {'answer':response.output_text,'provider':'openai','memory':len(memories())}

@app.delete('/api/memory')
def clear(): MEM.write_text('[]'); return {'ok':True}
