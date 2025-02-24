import os
import requests
import xml.etree.ElementTree as ET
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema.runnable import RunnableLambda, RunnablePassthrough
from langchain.vectorstores.faiss import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from langchain_community.document_loaders import AsyncChromiumLoader

# 🎯 대화 메시지 상태 저장
if "messages" not in st.session_state:
    st.session_state["messages"] = []

def save_message(message, role):
    st.session_state["messages"].append({"message": message, "role": role})

def send_message(message, role, save=True):
    with st.chat_message(role):
        st.markdown(message)
    if save:
        save_message(message, role)

def paint_history():
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["message"])

def get_chat_history():
    return "\n".join(f"{msg['role']}: {msg['message']}" for msg in st.session_state["messages"])

llm = ChatOpenAI(temperature=0.1)

# 🎯 프롬프트 정의
answers_prompt = ChatPromptTemplate.from_template(
    """
    Chat History:
    {chat_history}

    Website Content:
    {context}

    Using the above information, answer the user's question.
    Then, give a score to the answer between 0 and 5.

    Your turn!
    Question: {question}
    """
)

def get_answers(inputs):
    docs = inputs["docs"]
    question = inputs["question"]
    chat_history = get_chat_history()
    answers_chain = answers_prompt | llm
    return {
        "question": question,
        "answers": [
            { 
                "answer": answers_chain.invoke(
                    {"question": question, "context": doc.page_content, "chat_history": chat_history}
                ).content,
                "source": doc.metadata["source"],
            } for doc in docs
        ],
    }

choose_prompt = ChatPromptTemplate.from_messages([
    ("system", "Use ONLY the following answers to respond."),
    ("human", "{question}"),
])

def choose_answer(inputs):
    answers = inputs["answers"]
    question = inputs["question"]
    choose_chain = choose_prompt | llm
    condensed = "\n\n".join(f"{answer['answer']}\nSource:{answer['source']}" for answer in answers)
    return choose_chain.invoke({"question": question, "answers": condensed})

# 🎯 Selenium을 사용한 동적 HTML 로딩
def fetch_dynamic_content(url):
    """ JavaScript가 렌더링된 후의 HTML을 가져오는 함수 """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    driver.get(url)
    driver.implicitly_wait(7)  # 🚀 JS 실행 후 로딩 시간 증가
    html = driver.page_source
    driver.quit()
    
    return html

# 🎯 페이지 본문 추출 (자동 태그 탐색)
def parse_page(soup):
    """ 본문을 추출하는 함수 """
    content_tags = ["main", "article", "section", "div"]
    for tag in content_tags:
        content = soup.find(tag)
        if content:
            return content.get_text().strip()

    return soup.get_text().strip()

# 🎯 사이트맵에서 키워드가 포함된 URL만 추출
def parse_urls(sitemap_url, keyword):
    if sitemap_url:
        try:
            # 사이트맵 URL에서 XML 데이터를 가져옴
            response = requests.get(sitemap_url)
            response.raise_for_status()  # HTTP 에러 발생 시 예외 처리

            # XML 파싱
            root = ET.fromstring(response.content)
            # 기본 네임스페이스 지정
            ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            urls = []

            # 모든 <url> 요소 순회하며 <loc> 태그의 텍스트(실제 URL) 추출
            for url_elem in root.findall("ns:url", ns):
                loc = url_elem.find("ns:loc", ns)
                if loc is not None:
                    url_text = loc.text
                    # 키워드가 입력된 경우, URL에 키워드가 포함되었는지 확인
                    if keyword:
                        if keyword.lower() in url_text.lower():
                            urls.append(url_text)
                    else:
                        urls.append(url_text)

            return urls  # ✅ URL 리스트 반환

        except Exception as e:
            st.error(f"Error fetching/parsing sitemap: {e}")
            return []  # ✅ 오류 발생 시 빈 리스트 반환

# 🎯 FAISS 인덱스를 저장하지 않고 메모리에서 직접 생성
@st.cache_data(show_spinner="Loading website...")
def load_website(sitemap_url, keyword=None):
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=1000,
        chunk_overlap=200,
    )

    # ✅ 리턴값을 받아서 Streamlit UI에 표시
    filtered_urls = parse_urls(sitemap_url, keyword)

    # ✅ 반환된 리스트를 활용하여 출력
    if filtered_urls:
        st.write("Filtered URLs:" if keyword else "Extracted URLs:")
        st.write(filtered_urls)
        for page_url in filtered_urls: 
            raw_html = fetch_dynamic_content(page_url)
            soup = BeautifulSoup(raw_html, "html.parser")
            st.write(parse_page(soup))
    else:
        st.write("No URLs found with the given keyword." if keyword else "No URLs found.")
        

    loader = AsyncChromiumLoader(filtered_urls)
    loader.requests_per_second = 2
    docs = loader.load()
    docs = splitter.split_documents(docs)
    vector_store = FAISS.from_documents(docs, OpenAIEmbeddings())
    print(vector_store.as_retriever())
    return vector_store.as_retriever()


# 🎯 Streamlit UI 설정
st.set_page_config(page_title="SiteGPT", page_icon="🖥️")

st.markdown("""
# SiteGPT
Ask questions about the content of a website.
Enter the Sitemap URL in the sidebar to begin.
""")

with st.sidebar:
    sitemap_url = st.text_input("Enter Sitemap URL", placeholder="https://example.com/sitemap.xml")
    keyword = st.text_input("Input keyword (optional)", placeholder="Keyword")
    load_button = st.button("Load Website")

# 🎯 웹사이트 로드 및 질의응답 처리
if sitemap_url and load_button:
    if ".xml" not in sitemap_url:
        st.error("Please enter a valid Sitemap URL.")
    else:
        retriever = load_website(sitemap_url, keyword)

        if retriever:
            paint_history()
            user_input = st.chat_input("Ask a question about the website.")

            if user_input:
                send_message(user_input, "human")
                chain = ({"docs": retriever, "question": RunnablePassthrough()} | RunnableLambda(get_answers) | RunnableLambda(choose_answer))
                result = chain.invoke(user_input)
                answer = result.content.replace("$", "\$")
                send_message(answer, "ai")
