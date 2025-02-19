import streamlit as st
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.document_loaders import UnstructuredFileLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings, CacheBackedEmbeddings
from langchain.schema.runnable import RunnablePassthrough, RunnableLambda
from langchain.vectorstores import FAISS
from langchain.storage import LocalFileStore
from langchain.chat_models import ChatOpenAI
from langchain.callbacks.base import BaseCallbackHandler
from langchain.memory import ConversationBufferMemory

st.set_page_config(page_title="DocumentGPT", page_icon="📑")
st.title("DocumentGPT")

# ✅ "messages" 세션 상태 초기화 (없다면 빈 리스트로 설정)
if "messages" not in st.session_state:
    st.session_state["messages"] = []

with st.sidebar:
    file = st.file_uploader("Upload a .txt, .pdf, or .docx file", type=["pdf", "txt", "docx"])
    openai_api_key = st.text_input("🔑 OpenAI API 키를 입력하세요:", type="password")

if openai_api_key:
    st.session_state["openai_api_key"] = openai_api_key

if "memory" not in st.session_state:
    st.session_state["memory"] = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True
    )

memory = st.session_state["memory"]  # Use session state memory

class ChatCallbackHander(BaseCallbackHandler):
    def __init__(self):
        self.message = ""
        self.message_box = None  

    def on_llm_start(self, *args, **kwargs):
        self.message_box = st.empty()

    def on_llm_end(self, *args, **kwargs):
        save_message(self.message, "ai")

    def on_llm_new_token(self, token, *args, **kwargs):
        self.message += token
        self.message_box.markdown(self.message)

llm = ChatOpenAI(
    temperature=0.1,
    streaming=True,
    openai_api_key=openai_api_key,
    callbacks=[ChatCallbackHander()]
)

@st.cache_resource(show_spinner="Embedding file...") 
def embed_file(file, openai_api_key):
    import os

    # 파일 저장 디렉터리 생성
    cache_dir = "./.cache/files/"
    os.makedirs(cache_dir, exist_ok=True)  

    # 파일 저장 경로 설정
    file_path = os.path.join(cache_dir, file.name)

    # 파일 저장
    with open(file_path, "wb") as f:
        f.write(file.read())

    # 파일이 제대로 저장되었는지 확인
    if not os.path.exists(file_path):
        st.error(f"❌ 파일 저장에 실패했습니다: {file_path}")
        st.stop()
    
    st.success(f"✅ 파일이 성공적으로 저장됨: {file_path}")

    # Embedding 캐시 디렉터리 설정
    embedding_cache_dir = f"./.cache/embeddings/{file.name}"
    os.makedirs(embedding_cache_dir, exist_ok=True)  

    # 문서 분할 및 로딩
    splitter = CharacterTextSplitter.from_tiktoken_encoder(
        separator="\n", 
        chunk_size=600,
        chunk_overlap=100
    )      
    docs = UnstructuredFileLoader(file_path).load_and_split(text_splitter=splitter)

    # 임베딩 저장
    embeddings = CacheBackedEmbeddings.from_bytes_store(
        OpenAIEmbeddings(openai_api_key=openai_api_key), 
        LocalFileStore(embedding_cache_dir)
    )
    return FAISS.from_documents(docs, embeddings).as_retriever()

def load_memory(_):
    return memory.load_memory_variables({}).get("chat_history", [])

def save_message(message, role):
    # ✅ messages가 없을 경우 초기화 (안전장치)
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    st.session_state["messages"].append({"message": message, "role": role})

def send_message(message, role, save=True):
    with st.chat_message(role):
        st.markdown(message)
    if save:
        save_message(message, role)

def paint_history():
    for message in st.session_state["messages"]:
        send_message(message["message"], message["role"], save=False)

def format_docs(docs):
    return "\n\n".join(document.page_content for document in docs)

prompt = ChatPromptTemplate.from_messages([
    ("system", 
    """
    Given the following extracted parts of a long document and a question, create a final answer.
    If you don't know the answer, just say that you don't know. Don't try to make up an answer.
    -------
    Context: {context}
    """),
    MessagesPlaceholder(variable_name="chat_history"),  # ✅ Ensure chat history is included
    ("human", "{question}")
])

if file:
    if "openai_api_key" not in st.session_state or not st.session_state["openai_api_key"]:
        st.warning("⚠️ API 키를 입력해야 합니다!")
        st.stop()

    openai_api_key = st.session_state["openai_api_key"]
    retriever = embed_file(file, openai_api_key)

    send_message("I'm ready! Ask away!", "ai", save=False)
    paint_history()
    
    message = st.chat_input("Ask anything about your file...")

    if message:
        send_message(message, "human")

        chain = {
            "chat_history": RunnableLambda(load_memory),  # ✅ Loads previous chat history
            "context": retriever | RunnableLambda(format_docs), 
            "question": RunnablePassthrough()
        } | prompt | llm

        with st.chat_message("ai"):
            response = chain.invoke(message)

        memory.save_context(
            inputs={"input": message}, 
            outputs={"output": response.content}
        )