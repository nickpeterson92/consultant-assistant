# attachment_tools.py


from pydantic import BaseModel
from langchain.tools import BaseTool
from typing import Optional
import pytesseract
from PIL import Image


class OCRToolInput(BaseModel):
    image: str
    lang: Optional[str] = "eng"


class OCRTool(BaseTool):
    name: str = "ocr_tool"
    description: str = (
        "This tool is used to extract text from an image using OCR."
        "Images will be something like a receipt, a business card, or other documents."
    )
    args_schema: type = OCRToolInput

    def _run(self, **kwargs) -> str:
        print(f"DEBUG: Tool 'ocr_tool' invoked with input: {kwargs}")
        data = OCRToolInput(**kwargs)
        return pytesseract.image_to_string(Image.open(data.image), lang=data.lang)