import os
import pdfplumber
from pdf2image import convert_from_path
import pytesseract
# from PIL import Image
from langchain_community.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document


pytesseract.pytesseract.tesseract_cmd = r"C:\Tesseract-OCR\tesseract.exe"


# 將 PDF 圖片轉為文字
def pdf_to_text(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            img = page.to_image(resolution=300).original
            page_text = pytesseract.image_to_string(img, lang="chi_tra+eng")
            text += page_text + "\n"
    return text


# 將整個 knowledge 資料夾的 PDF 轉為 TXT
def convert_folder_pdfs_to_txt(pdf_folder, output_folder):
    os.makedirs(output_folder, exist_ok=True)

    for filename in os.listdir(pdf_folder):
        if filename.endswith(".pdf"):
            full_path = os.path.join(pdf_folder, filename)
            text = pdf_to_text(full_path)

            output_path = os.path.join(output_folder, filename.replace(".pdf", ".txt"))
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"轉換完成：{filename} -> {output_path}")


# 載入 txt 檔案並轉為 Document
def load_txt_documents(folder_path):
    documents = []
    for filename in os.listdir(folder_path):
        if filename.endswith(".txt"):
            with open(os.path.join(folder_path, filename), "r", encoding="utf-8") as f:
                content = f.read()
                documents.append(Document(page_content=content, metadata={"source": filename}))
    return documents


def pdf_to_text_with_ocr(pdf_path, output_path="/mnt/data/ocr_output.txt"):
    text = ""
    try:
        # 將 PDF 每頁轉成高解析度圖片
        images = convert_from_path(pdf_path, dpi=300)
        for idx, image in enumerate(images):
            # OCR 中英文識別
            page_text = pytesseract.image_to_string(image, lang="chi_tra+eng")
            text += page_text + "\n"

        # 存成文字檔案
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)

        # 回傳預覽部分內容
        return text[:2000]

    except Exception as e:
        return f"OCR 轉換錯誤: {e}"


# 執行整體流程
if __name__ == "__main__":
    # 1. 把圖片式 PDF 轉成純文字
    convert_folder_pdfs_to_txt("knowledge", "knowledge_txt")

    # 2. 載入 TXT 並切 chunk
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ".", "。"]
    )
    docs = load_txt_documents("knowledge_txt")
    split_docs = splitter.split_documents(docs)

    # 3. 建立向量資料庫
    db = FAISS.from_documents(split_docs, OpenAIEmbeddings())
    db.save_local("vectorstores/knowledge_base")

    print("向量資料庫建置完成！")

