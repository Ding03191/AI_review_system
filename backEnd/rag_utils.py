from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
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
