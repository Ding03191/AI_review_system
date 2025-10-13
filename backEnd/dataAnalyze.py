import os
from PyPDF2 import PdfReader
import pdfplumber
import openai
import pytesseract
import shutil
from PIL import Image, ImageEnhance, ImageOps  # 未來支援圖片上傳
# custom modules
import functions as func
# RAG
from rag_utils import split_text_into_chunks, create_vectorstore, retrieve_relevant_chunks, load_persistent_vectorstore

# 設定 Tesseract 執行檔位置（Windows）
pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD") or shutil.which("tesseract")


def preprocess_image(img):
    img = img.convert("L")  # 灰階
    img = ImageOps.invert(img)  # 反轉（白底黑字）
    img = img.resize((img.width * 2, img.height * 2))  # 放大影像
    img = ImageEnhance.Contrast(img).enhance(3)
    img = ImageEnhance.Sharpness(img).enhance(3)
    return img


# 處理檔案
def extract_file_content(file_path):
    extension = os.path.splitext(file_path)[-1].lower()

    try:
        if extension == '.pdf':
            reader = PdfReader(file_path)
            text = ''.join([page.extract_text() or "" for page in reader.pages])

            if text.strip():
                print(" 檔案為可讀文字型 PDF，不使用 OCR")
                return text.strip()

            # PDF 為圖片格式 → 啟用 OCR
            print(" 啟用 OCR 模式處理圖片 PDF")
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    try:
                        img = page.to_image(resolution=500).original.convert("RGB")  # 提高解析度
                        processed_img = preprocess_image(img)
                        ocr_text = pytesseract.image_to_string(processed_img, lang='chi_tra+eng')

                        print(f" OCR 第 {i + 1} 頁內容:\n{ocr_text[:200]}...\n")  # Preview
                        text += f"\n[頁面{i + 1}]\n" + ocr_text
                    except Exception as img_err:
                        print(f" 圖像處理錯誤（第 {i + 1} 頁）: {img_err}")
                        text += f"\n[頁面{i + 1}] 圖像處理錯誤: {img_err}\n"

            if not text.strip():
                return " OCR 無法辨識任何文字，請確認 PDF 清晰度與格式。"
            return text.strip()

        elif extension in ['.png', '.jpg', '.jpeg']:
            image = Image.open(file_path).convert("RGB")
            processed_img = preprocess_image(image)
            ocr_text = pytesseract.image_to_string(processed_img, lang='chi_tra+eng')
            print(" 單張圖片 OCR 預覽：", ocr_text[:200])
            return ocr_text.strip()

        else:
            return f"Unsupported file type: {extension}"

    except Exception as e:
        return f" Error processing file: {e}"


# system_instructions = func.read_file_to_string(r'PromptRefine\backEnd\promptList\applicationInstruciton.txt')
system_instructions = func.read_file_to_string(
    os.path.join(os.path.dirname(__file__), 'promptList', 'applicationInstruciton.txt')
)


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
        persistent_vectorstore = load_persistent_vectorstore("vectorstores/knowledge_base")
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