from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
import os


# 分割文本
def split_text_into_chunks(text, chunk_size=500, chunk_overlap=50):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ".", "。", "！", "？"]
    )
    return splitter.split_text(text)


# 建立向量資料庫
def create_vectorstore(chunks):
    if not chunks:
        raise ValueError("chunks 為空，無法建立向量資料庫")

    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_texts(chunks, embedding=embeddings)
    return vectorstore


# 檢索與使用者指令相似的內容
def retrieve_relevant_chunks(vectorstore, query, k=5):
    if not vectorstore:
        raise ValueError("vectorstore 無效")
    if not query:
        raise ValueError("查詢字串為空")

    docs = vectorstore.similarity_search(query, k=k)
    return [doc.page_content for doc in docs if doc.page_content.strip()]


# 載入已建好的向量資料庫
def load_persistent_vectorstore(path="vectorstores/knowledge_base"):
    if not os.path.exists(path):
        raise FileNotFoundError(f"向量資料庫不存在：{path}")

    embeddings = OpenAIEmbeddings()
    return FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)


# backEnd/rag_utils.py（示意骨架，依你現況微調）
def ask_rag(query: str, context: str, top_k: int = 5, force_citations: bool = True):
    """
    回傳欄位級結構（最小可用版，先用規則/簡易抽取頂著，之後再換成 LLM+RAG）
    """
    import re
    # 簡易 baseline：用正則先抽，之後再接上你的向量庫檢索 + LLM
    course = None
    m_course = re.search(r"《([^》]+)》|課程[:：]\s*([^\n]+)", context)
    if m_course:
        course = m_course.group(1) or m_course.group(2)

    hours = None
    m_hours = re.search(r"(\d{1,3})\s*(小時|hr|hrs|hours?)", context, flags=re.I)
    if m_hours:
        hours = int(m_hours.group(1))

    date_pat = r"(20\d{2})[./-](0?[1-9]|1[0-2])[./-](0?[1-9]|[12]\d|3[01])"
    m_start = re.search(r"(起始|開始|自|from)\s*[:：]?\s*" + date_pat, context, flags=re.I)
    m_any = re.search(date_pat, context)

    fields = {
        "course_name": {
            "value": course,
            "confidence": 0.70 if course else 0.0,
            "evidence": {"chunk_id": 0, "offset": None} if course else None,
            "retrieval_score": 0.70 if course else 0.0,
            "abstain": course is None
        },
        "hours": {
            "value": hours,
            "confidence": 0.85 if hours is not None else 0.0,
            "evidence": {"chunk_id": 0, "offset": None} if hours is not None else None,
            "retrieval_score": 0.85 if hours is not None else 0.0,
            "abstain": hours is None
        },
        "date_start": {
            "value": f"{m_start.group(1)}-{m_start.group(2).zfill(2)}-{m_start.group(3).zfill(2)}" if m_start else (
                     f"{m_any.group(1)}-{m_any.group(2).zfill(2)}-{m_any.group(3).zfill(2)}" if m_any else None),
            "confidence": 0.65 if (m_start or m_any) else 0.0,
            "evidence": {"chunk_id": 0, "offset": None} if (m_start or m_any) else None,
            "retrieval_score": 0.65 if (m_start or m_any) else 0.0,
            "abstain": not (m_start or m_any)
        },
        "date_end": {
            "value": None,
            "confidence": 0.0,
            "evidence": None,
            "retrieval_score": 0.0,
            "abstain": True
        }
    }

    return {
        "model_ver": "baseline@0.1",
        "fields": fields
    }
