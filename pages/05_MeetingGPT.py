import streamlit as st
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

st.title("Sitemap URL Parser")

sitemap_url = st.text_input("Enter Sitemap URL", "https://developers.cloudflare.com/sitemap-0.xml")
keyword = st.text_input("Enter keyword to filter URLs (optional)", "")

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

def parse_page(soup):
    """ 본문을 추출하는 함수 """
    content_tags = ["main", "article", "section", "div"]
    for tag in content_tags:
        content = soup.find(tag)
        if content:
            return content.get_text().strip()

    return soup.get_text().strip()

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
