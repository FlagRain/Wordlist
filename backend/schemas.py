# backend/schemas.py
from typing import Optional, List, Union
from pydantic import BaseModel, ConfigDict, field_validator

class RowIn(BaseModel):
    """
    导入/批量写库时的输入模型：
    - 优先使用 `audio` 传入【文件名】（例如 '月亮.wav'）
    - 也兼容 `audio_id`（int 或数字字符串）；如果两者都给，后端应优先按文件名匹配
    """
    model_config = ConfigDict(extra='ignore')  # 允许多余字段不报错
    col1: str = ""
    col2: str = ""
    audio: Optional[str] = None
    audio_id: Optional[Union[int, str]] = None  # 兼容前端误传成字符串的情况

    @field_validator("audio", mode="before")
    def _clean_audio(cls, v):
        if v is None:
            return v
        return str(v).strip()

class RowOut(BaseModel):
    """
    /rows 返回用的条目
    """
    model_config = ConfigDict(from_attributes=True)
    id: int
    col1: str
    col2: str
    audio_id: Optional[int] = None
    audio_filename: Optional[str] = None

class RowsPage(BaseModel):
    total: int
    items: List[RowOut]

