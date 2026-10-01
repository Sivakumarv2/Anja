import os, json, uuid, base64, mimetypes, urllib.request, urllib.error
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from pypdf import PdfReader
from docx import Document

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'data'
UPLOADS=ROOT/'uploads'
DATA.mkdir(exist_ok=True)
UPLOADS.mkdir(exist_ok=True)
MEM=DATA/'memory.json'
if not MEM.exists():
    MEM.write_text('[]', encoding='utf-8')

class Chat(BaseModel):
    message: str
    attachment_ids: list[str] = []

def memories():
    try:
        return json.loads(MEM.read_text(encoding='utf-8'))
    except Exception:
        return []

def remember(x):
    a=memories()
    a.append({'id':str(uuid.uuid4()),'text':x})
    MEM.write_text(json.dumps(a[-500:],indent=2), encoding='utf-8')

def openai_client():
    key=os.getenv('OPENAI_API_KEY','').strip()
    return OpenAI(api_key=key) if key else None

def ollama_url(path=''):
    return os.getenv('OLLAMA_BASE_URL','http://127.0.0.1:11434').rstrip('/') + path

def ollama_available():
    try:
        req=urllib.request.Request(ollama_url('/api/tags'), method='GET')
        with urllib.request.urlopen(req, timeout=1.5) as r:
            return 200 <= r.status < 300
    except Exception:
        return False

def extract_file_text(path: Path, mime: str) -> str:
    try:
        ext=path.suffix.lower()
        if ext == '.pdf':
            reader=PdfReader(str(path))
            return '\n\n'.join((p.extract_text() or '') for p in reader.pages)[:50000]
        if ext == '.docx':
            doc=Document(str(path))
            return '\n'.join(p.text for p in doc.paragraphs)[:50000]
        if ext in {'.txt','.md','.csv','.json'}:
            return path.read_text(encoding='utf-8', errors='ignore')[:50000]
    except Exception as e:
        return f'[Could not extract text from {path.name}: {e}]'
    return ''

def chat_ollama(req: Chat):
    model=os.getenv('OLLAMA_MODEL','gemma3:4b')
    messages=[{
        'role':'system',
        'content':(
            'You are Anja, an adaptive multimodal AI assistant. '
            'Answer directly and clearly. Analyze supplied files/images when present. '
            'Never claim to have accessed information you did not receive. '
            'You may reason internally, but provide concise conclusions and useful steps rather than hidden chain-of-thought.'
        )
    }]

    text=req.message
    prior='\n'.join('- '+x['text'] for x in memories()[-8:])
    text += '\n\nRelevant Anja memory:\n' + (prior or '(none)')
    images=[]

    for fid in req.attachment_ids:
        found=list(UPLOADS.glob(fid+'*'))
        if not found:
            continue
        p=found[0]
        mime=mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
        if mime.startswith('image/'):
            images.append(base64.b64encode(p.read_bytes()).decode('ascii'))
        else:
            extracted=extract_file_text(p,mime)
            if extracted:
                text += f'\n\n--- File: {p.name} ---\n{extracted}'

    user_msg={'role':'user','content':text}
    if images:
        user_msg['images']=images
    messages.append(user_msg)

    payload=json.dumps({
        'model':model,
        'messages':messages,
        'stream':False
    }).encode('utf-8')

    try:
        req_http=urllib.request.Request(
            ollama_url('/api/chat'),
            data=payload,
            headers={'Content-Type':'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req_http, timeout=300) as response:
            data=json.loads(response.read().decode('utf-8'))
        answer=data.get('message',{}).get('content','').strip()
        if not answer:
            raise RuntimeError('Ollama returned an empty response.')
        return answer, model
    except urllib.error.HTTPError as e:
        body=e.read().decode('utf-8','ignore')[:1200]
        raise HTTPException(502, detail=f'Ollama request failed (HTTP {e.code}): {body}')
    except urllib.error.URLError as e:
        raise HTTPException(503, detail='Ollama is not running. Start Ollama on this computer, then try again.')
    except Exception as e:
        raise HTTPException(502, detail=f'Ollama request failed: {str(e)[:1200]}')

app=FastAPI(title='Anja',version='2.0.0')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['*'],allow_headers=['*'])

@app.get('/health')
def health():
    return {'ok':True,'service':'anja','provider':os.getenv('ANJA_PROVIDER','ollama')}

@app.get('/')
def home():
    return FileResponse(ROOT/'frontend'/'index.html')

@app.get('/api/status')
def status():
    provider=os.getenv('ANJA_PROVIDER','ollama').lower()
    if provider == 'openai':
        configured=bool(os.getenv('OPENAI_API_KEY','').strip())
        return {'name':'Anja','status':'online','provider':'openai' if configured else 'openai_not_configured','model':os.getenv('ANJA_MODEL','gpt-5'),'memory':len(memories())}
    available=ollama_available()
    return {'name':'Anja','status':'online','provider':'ollama' if available else 'ollama_offline','model':os.getenv('OLLAMA_MODEL','gemma3:4b'),'memory':len(memories())}

@app.post('/api/upload')
async def upload(files:list[UploadFile]=File(...)):
    allowed={'.png','.jpg','.jpeg','.webp','.gif','.pdf','.docx','.txt','.md','.csv','.json'}
    out=[]
    for f in files:
        ext=Path(f.filename or '').suffix.lower()
        if ext not in allowed:
            raise HTTPException(400,f'Unsupported file type: {ext}')
        data=await f.read()
        if len(data)>30*1024*1024:
            raise HTTPException(413,'Maximum file size is 30 MB.')
        fid=str(uuid.uuid4())
        p=UPLOADS/(fid+ext)
        p.write_bytes(data)
        out.append({'id':fid,'name':f.filename,'mime':f.content_type or mimetypes.guess_type(f.filename)[0]})
    return {'files':out}

@app.post('/api/chat')
def chat(req:Chat):
    provider=os.getenv('ANJA_PROVIDER','ollama').lower()

    if provider == 'openai':
        c=openai_client()
        if not c:
            raise HTTPException(503,'OpenAI is not configured. Set ANJA_PROVIDER=ollama for the free local mode.')
        content=[{'type':'input_text','text':req.message}]
        for fid in req.attachment_ids:
            found=list(UPLOADS.glob(fid+'*'))
            if not found:
                continue
            p=found[0]
            mime=mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
            raw=base64.b64encode(p.read_bytes()).decode()
            if mime.startswith('image/'):
                content.append({'type':'input_image','image_url':f'data:{mime};base64,{raw}','detail':'auto'})
            else:
                content.append({'type':'input_file','file_data':f'data:{mime};base64,{raw}','filename':p.name})
        prior='\n'.join('- '+x['text'] for x in memories()[-8:])
        content.append({'type':'input_text','text':'Relevant Anja memory:\n'+(prior or '(none)')})
        try:
            response=c.responses.create(
                model=os.getenv('ANJA_MODEL','gpt-5'),
                instructions='You are Anja, an adaptive multimodal AI assistant. Answer directly, analyze supplied images/files, and never pretend you accessed information you did not receive.',
                input=[{'role':'user','content':content}]
            )
            answer=response.output_text
        except Exception as e:
            msg=str(e).replace(os.getenv('OPENAI_API_KEY',''),'[REDACTED]')
            raise HTTPException(502,detail=f'OpenAI request failed: {msg[:1200]}')
        remember(req.message)
        return {'answer':answer,'provider':'openai','memory':len(memories())}

    answer,model=chat_ollama(req)
    remember(req.message)
    return {'answer':answer,'provider':'ollama','model':model,'memory':len(memories())}

@app.delete('/api/memory')
def clear():
    MEM.write_text('[]', encoding='utf-8')
    return {'ok':True}
