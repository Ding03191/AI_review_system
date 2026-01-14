import os
import shutil
from PyPDF2 import PdfReader
import pdfplumber
import openai
import pytesseract
from PIL import Image, ImageEnhance, ImageOps  # 未來支援圖片上傳
# custom modules
from ..utils import functions as func
from ..utils.rag_utils import (
    create_vectorstore,
    load_persistent_vectorstore,
    retrieve_relevant_chunks,
    split_text_into_chunks,
)

# 設定 Tesseract 執行檔位置（Windows）
# 先看有沒有環境變數，沒有就用 C:\Tesseract-OCR\tesseract.exe
tesseract_path = (
    os.getenv("TESSERACT_CMD")
    or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    or shutil.which("tesseract")
)

if not tesseract_path or not os.path.exists(tesseract_path):
    # 不要整個程式直接 raise；先允許僅文字層解析，OCR 用到時再回報
    print("[WARN] 找不到 Tesseract，可讀 PDF 仍可處理；需要 OCR 時請安裝或設定 TESSERACT_CMD")
else:
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
    print(f"使用 Tesseract 執行檔：{tesseract_path}")


def preprocess_image(img):
    # 灰階 + 自動對比 + 輕微銳化；避免強制反相（有些證書底色會被反轉）
    img = img.convert("L")
    img = ImageOps.autocontrast(img)
    # 放大 1.5 倍有助中文 OCR（LANCZOS）
    img = img.resize((int(img.width * 1.5), int(img.height * 1.5)), Image.Resampling.LANCZOS)
    # 適度銳化
    img = ImageEnhance.Sharpness(img).enhance(1.5)
    img = ImageEnhance.Contrast(img).enhance(1.3)
    return img


# 處理檔案
def extract_file_content(file_path, ocr_dpi=400):
    ext = os.path.splitext(file_path)[-1].lower()

    def _need_ocr(s: str) -> bool:
        # 找不到這些關鍵詞才啟用 OCR（避免多做工）
        keys = ["認證時數", "閱讀時數", "測驗成績", "通過標準", "學員姓名", "課程名稱"]
        return not any(k in (s or "") for k in keys)

    try:
        if ext == ".pdf":
            # 先抽文字層
            text = ""
            try:
                reader = PdfReader(file_path)
                text = "".join([p.extract_text() or "" for p in reader.pages])
            except Exception:
                text = ""

            if text and text.strip() and not _need_ocr(text):
                print(" 檔案為可讀文字型 PDF（已含關鍵字），暫不啟用 OCR")
                return text.strip()

            # 需要 OCR 時才進行；若未安裝 Tesseract，回傳友善訊息
            if not (pytesseract.pytesseract.tesseract_cmd and os.path.exists(pytesseract.pytesseract.tesseract_cmd)):
                return (text or "") + "\n[OCR 提示] 未偵測到 Tesseract，可讀文字已回傳；若需識別圖片內容請安裝 Tesseract 或設定 TESSERACT_CMD"

            print(f" 啟用 OCR 模式處理圖片/混合 PDF，dpi={ocr_dpi}")
            ocr_all = []
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    try:
                        img = page.to_image(resolution=ocr_dpi).original.convert("RGB")
                        processed = preprocess_image(img)
                        ocr_text = pytesseract.image_to_string(processed, lang="chi_tra+eng", config="--oem 3 --psm 6")
                        ocr_all.append(f"[頁面{i + 1}]\n{ocr_text}")
                    except Exception as e:
                        ocr_all.append(f"[頁面{i + 1}] OCR 發生錯誤：{e}")
            merged = (text or "") + "\n\n" + "\n".join(ocr_all)
            return merged.strip() or " OCR 無法辨識任何文字，請確認 PDF 清晰度與格式。"

        elif ext in [".png", ".jpg", ".jpeg"]:
            if not (pytesseract.pytesseract.tesseract_cmd and os.path.exists(pytesseract.pytesseract.tesseract_cmd)):
                return " [OCR 提示] 未偵測到 Tesseract，無法解析圖片。"
            image = Image.open(file_path).convert("RGB")
            processed = preprocess_image(image)
            ocr_text = pytesseract.image_to_string(processed, lang="chi_tra+eng", config="--oem 3 --psm 6")
            return ocr_text.strip()

        else:
            return f"Unsupported file type: {ext}"

    except Exception as e:
        return f" Error processing file: {e}"


_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_PROMPT_PATH = os.path.join(_BACKEND_DIR, "promptList", "applicationInstruciton.txt")
system_instructions = func.read_file_to_string(_PROMPT_PATH)


# with files
def analyze_with_gpt(file_content, instruction):
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": f"{instruction}\nHere is the file content:\n{file_content}"}
            ],
            temperature=0.5,  # temperature => AI回饋的多樣性，2是最高，0是最低
            max_tokens=16384,  # 基本上要翻Document看call哪支的 來確認maximum token
            top_p=0.95,  # top_p => AI抽樣機率分布的範圍，1是最高，0是最低
            frequency_penalty=0,  # frequency_penalty => -2是最低，2是最高 越高在單句的回覆內越不會重複同樣字眼
            presence_penalty=0  # presence_penalty => -2是最低，2是最高 越高在複數的回應內越不會重複同樣字眼 (對於有歷史對話影響較多)
        )
        if not response.choices or not response.choices[0].message:
            return "Error: GPT 沒有給出有效回應"

        func.tokenUsed(response.usage.total_tokens)
        res = response.choices[0].message.content
        return res

    except Exception as e:
        return f"Error during GPT analysis: {e}"


def analyze_with_gpt_rag(file_content, instruction):
    try:
        # 切段
        chunks = split_text_into_chunks(file_content)

        # 建立臨時向量資料庫
        vectorstore = create_vectorstore(chunks)

        # 語意檢索最相關的片段
        top_chunks = retrieve_relevant_chunks(vectorstore, instruction, k=5)
        if not top_chunks:
            return "Error: 無法從文件中找到相關內容"

        relevant_text = "\n---\n".join(top_chunks)

        # 丟給 GPT 處理
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": f"{instruction}\n\n以下是與此最相關的內容：\n{relevant_text}"}
            ],
            temperature=0.5,
            max_tokens=4096
        )

        # 防呆：確認 GPT 回應有效
        if not response.choices or not response.choices[0].message:
            return "Error: GPT 沒有有效回應內容"

        # 回傳分析結果
        func.tokenUsed(response.usage.total_tokens)
        return response.choices[0].message.content

    except Exception as e:
        return f"Error during GPT-RAG analysis: {e}"


def analyze_with_gpt_rag_mix(file_content, instruction):
    try:
        # 🔹1. 即時 chunks 處理
        chunks = split_text_into_chunks(file_content)
        instant_vectorstore = create_vectorstore(chunks)
        instant_chunks = retrieve_relevant_chunks(instant_vectorstore, instruction, k=3)

        # 🔹2. 常駐知識庫處理
        persistent_vectorstore = load_persistent_vectorstore(
            os.path.join(_BACKEND_DIR, "vectorstores", "knowledge_base")
        )
        persistent_chunks = retrieve_relevant_chunks(persistent_vectorstore, instruction, k=3)

        # 🔹3. 合併所有 chunks
        all_chunks = instant_chunks + persistent_chunks
        if not all_chunks:
            return "Error: 無法從任何資料中找到相關內容"

        relevant_text = "\n---\n".join(all_chunks)

        # 🔹4. 丟給 GPT
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": f"{instruction}\n\n以下是與此最相關的內容：\n{relevant_text}"}
            ],
            temperature=0.5,
            max_tokens=4096
        )

        # Debug：確認 GPT response 結構
        print(" GPT response:", response)

        # 防呆：避免 response.choices 為空
        if not response.choices or not response.choices[0].message:
            return "Error: GPT 沒有有效回應內容"

        # 正常回傳
        func.tokenUsed(response.usage.total_tokens)
        return response.choices[0].message.content

    except Exception as e:
        return f"Error during GPT-RAG-MIX analysis: {e}"
