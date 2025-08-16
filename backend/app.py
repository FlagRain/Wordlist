# backend/app.py
import os
import io
import mimetypes
import unicodedata
from typing import Optional, List, Any

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Response, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.responses import FileResponse

from sqlalchemy.orm import Session
from sqlalchemy import or_

from openpyxl import Workbook
from dotenv import load_dotenv

from db import SessionLocal, init_db
from models import Row, Audio
from schemas import RowOut, RowsPage
from auth import authenticate, verify_token, create_default_admin

load_dotenv()

# ==== 路径与应用 ====
AUDIO_DIR = os.getenv("AUDIO_DIR", "/home/ftp/rgyalrong-backend/storage/audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

app = FastAPI(title="Audio Table API")

# ==== CORS ====
origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# ==== DB 依赖 ====
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==== 启动初始化 ====
@app.on_event("startup")
def startup():
    init_db()
    with SessionLocal() as db:
        create_default_admin(db)

# ==== 工具：文件名规范化与索引 ====
def _canon(name: str) -> str:
    """统一空白、大小写、Unicode 规范（支持中文/全角空格）"""
    if not name:
        return ""
    s = unicodedata.normalize("NFC", name).strip().lower()
    s = s.replace("\u3000", " ")  # 全角空格 -> 半角
    return s

def _build_audio_index(db: Session) -> dict:
    """
    构建 { 规范化文件名 -> audio_id } 索引。
    DB 里有的直接记录 id；磁盘存在但 DB 无的暂记为 -1。
    """
    index: dict[str, int] = {}
    for a in db.query(Audio).all():
        index[_canon(a.filename)] = a.id

    if os.path.isdir(AUDIO_DIR):
        for fname in os.listdir(AUDIO_DIR):
            key = _canon(fname)
            if key and key not in index:
                index[key] = -1  # 磁盘有、DB 无
    return index

def _ensure_audio_record(db: Session, audio_index: dict, filename: str) -> Optional[int]:
    """
    给定文件名：
      - 若索引里 id>0：直接返回
      - 若索引里是 -1（磁盘有 DB 无）：创建 Audio 记录后返回 id，并更新索引
      - 找不到：返回 None
    """
    key = _canon(os.path.basename(filename or ""))
    if not key:
        return None

    aid = audio_index.get(key)
    if aid is None:
        return None
    if aid > 0:
        return aid

    # aid == -1：磁盘存在但 DB 无 -> 落库
    real_path = os.path.join(AUDIO_DIR, os.path.basename(filename))
    if os.path.exists(real_path):
        mime = mimetypes.guess_type(real_path)[0] or "audio/wav"
        a = Audio(filename=os.path.basename(filename), filepath=real_path, mime=mime)
        db.add(a)
        db.flush()
        audio_index[key] = a.id
        return a.id
    return None

# ==== 鉴权 ====
@app.post("/auth/login")
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    token = authenticate(db, username, password)
    if not token:
        raise HTTPException(401, "Invalid credentials")
    return {"access_token": token, "token_type": "bearer"}

def require_auth(creds: HTTPAuthorizationCredentials = Depends(security)):
    try:
        verify_token(creds.credentials)
    except Exception:
        raise HTTPException(401, "Invalid/expired token")

# （可选）供前端校验当前 token 是否有效
@app.get("/auth/me", dependencies=[Depends(require_auth)])
def me():
    return {"ok": True}

# ==== 列表 + 搜索 + 分页 ====
@app.get("/rows", response_model=RowsPage)
def list_rows(
    q: Optional[str] = Query(None, description="搜索关键字，匹配 col1/col2/文件名"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Row)
    if q:
        like = f"%{q}%"
        query = query.join(Audio, isouter=True).filter(
            or_(Row.col1.ilike(like), Row.col2.ilike(like), Audio.filename.ilike(like))
        )
    total = query.count()
    rows = query.order_by(Row.id.asc()).offset(offset).limit(limit).all()
    items = [
        RowOut(
            id=r.id,
            col1=r.col1,
            col2=r.col2,
            audio_id=r.audio_id,
            audio_filename=r.audio.filename if r.audio else None,
        )
        for r in rows
    ]
    return {"total": total, "items": items}

# ==== 批量导入（支持第三列文件名自动匹配） ====
@app.post("/rows/bulk", dependencies=[Depends(require_auth)])
def bulk_create_rows(payload: List[Any] = Body(...), db: Session = Depends(get_db)):
    """
    接受：
      - [{"col1":"..","col2":"..","audio":"月亮.wav"}]
      - [{"col1":"..","col2":"..","audio_id":123}]
      - [["col1","col2","月亮.wav"], ...] / [["col1","col2",123], ...]
    """
    audio_index = _build_audio_index(db)
    created = 0
    unmatched: list[str] = []

    for item in payload:
        col1 = col2 = ""
        audio_id: Optional[int] = None
        audio_name = ""

        if isinstance(item, dict):
            col1 = str(item.get("col1") or "")
            col2 = str(item.get("col2") or "")
            audio_id = item.get("audio_id")
            audio_name = item.get("audio") or item.get("audio_filename") or item.get("filename") or ""
        elif isinstance(item, (list, tuple)):
            col1 = str(item[0] or "") if len(item) > 0 else ""
            col2 = str(item[1] or "") if len(item) > 1 else ""
            if len(item) > 2:
                third = item[2]
                if isinstance(third, int):
                    audio_id = third
                elif isinstance(third, str):
                    audio_name = third

        # 根据文件名找 audio_id（优先用传入的 id）
        if audio_id is None and audio_name:
            aid = _ensure_audio_record(db, audio_index, audio_name)
            if aid is None:
                unmatched.append(unicodedata.normalize("NFC", audio_name).strip())
            audio_id = aid

        db.add(Row(col1=col1, col2=col2, audio_id=audio_id))
        created += 1

    db.commit()
    return {"created": created, "unmatched": unmatched}

# ==== 音频流（支持浏览器拖动播放） ====
@app.get("/audio/{audio_id}")
def get_audio(audio_id: int, db: Session = Depends(get_db)):
    a = db.query(Audio).get(audio_id)
    if not a:
        raise HTTPException(404, "Not found")
    media_type = a.mime or mimetypes.guess_type(a.filename)[0] or "audio/wav"
    return FileResponse(a.filepath, media_type=media_type, filename=a.filename)

# ==== 导出 Excel ====
@app.get("/export.xlsx")
def export_xlsx(db: Session = Depends(get_db)):
    wb = Workbook()
    ws = wb.active
    ws.title = "音频表"
    ws.append(["第一列", "第二列", "音频ID", "音频文件名"])
    for r in db.query(Row).order_by(Row.id.asc()).all():
        ws.append([r.col1 or "", r.col2 or "", r.audio_id or "", r.audio.filename if r.audio else ""])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    headers = {"Content-Disposition": "attachment; filename=audio_table.xlsx"}
    return Response(buf.read(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)

# ==== 增删改（需要登录） ====
@app.post("/rows", dependencies=[Depends(require_auth)])
def create_row(
    col1: str = Form(""),
    col2: str = Form(""),
    audio_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    row = Row(col1=col1, col2=col2, audio_id=audio_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}

@app.put("/rows/{row_id}", dependencies=[Depends(require_auth)])
def update_row(
    row_id: int,
    col1: Optional[str] = Form(None),
    col2: Optional[str] = Form(None),
    # 注意：把 audio_id 接成 str，这样 '' / '123' 都能先接到，再我们自己转
    audio_id: Optional[str] = Form(None),
    clear_audio: Optional[bool] = Form(False),
    db: Session = Depends(get_db),
):
    row = db.query(Row).get(row_id)
    if not row:
        raise HTTPException(404, "Not found")

    if col1 is not None:
        row.col1 = col1
    if col2 is not None:
        row.col2 = col2

    # —— 解绑优先 —— #
    if clear_audio:
        row.audio_id = None
    else:
        # 只有明确传了 audio_id 时才处理；空字符串代表“清空”
        if audio_id is not None:
            s = (audio_id or "").strip()
            if s == "":
                row.audio_id = None
            else:
                if s.isdigit():
                    row.audio_id = int(s)
                else:
                    raise HTTPException(400, "audio_id must be integer or empty")

    db.commit()
    return {"ok": True}


@app.delete("/rows/{row_id}", dependencies=[Depends(require_auth)])
def delete_row(row_id: int, db: Session = Depends(get_db)):
    row = db.query(Row).get(row_id)
    if not row:
        raise HTTPException(404, "Not found")
    db.delete(row)
    db.commit()
    return {"ok": True}

# ==== 上传音频（需要登录） ====
@app.post("/upload", dependencies=[Depends(require_auth)])
def upload_audio(file: UploadFile = File(...), db: Session = Depends(get_db)):
    filename = os.path.basename(file.filename or "")
    if not filename:
        raise HTTPException(400, "Invalid filename")
    path = os.path.join(AUDIO_DIR, filename)
    with open(path, "wb") as out:
        out.write(file.file.read())
    audio = Audio(filename=filename, filepath=path, mime=file.content_type or "audio/wav")
    db.add(audio)
    db.commit()
    db.refresh(audio)
    return {"audio_id": audio.id, "filename": audio.filename}

# ==== 维护：扫描目录把音频补登记到 DB（需要登录） ====
@app.post("/maintenance/sync-audio-db", dependencies=[Depends(require_auth)])
def sync_audio_db(db: Session = Depends(get_db)):
    os.makedirs(AUDIO_DIR, exist_ok=True)
    existing = {a.filename for a in db.query(Audio).all()}
    added = 0
    for fname in os.listdir(AUDIO_DIR):
        if not fname:
            continue
        if fname in existing:
            continue
        path = os.path.join(AUDIO_DIR, fname)
        if not os.path.isfile(path):
            continue
        mime = mimetypes.guess_type(fname)[0] or "audio/wav"
        a = Audio(filename=fname, filepath=path, mime=mime)
        db.add(a)
        added += 1
    db.commit()
    return {"added": added}
