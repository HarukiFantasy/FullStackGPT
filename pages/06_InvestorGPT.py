import streamlit as st
import os, requests
from typing import Type
from langchain.schema import SystemMessage
from langchain.chat_models import ChatOpenAI
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from langchain.agents import initialize_agent, AgentType
from langchain.utilities import DuckDuckGoSearchAPIWrapper

st.set_page_config(page_title="InvestorGPT", page_icon="💹")
st.markdown(
    """ 
    # InvestorGPT
    Welcome to InvestorGPT

    Write down the name of a company and our Agent will do the research for you.
    """
)

llm = ChatOpenAI(model_name="gpt-4o-mini-2024-07-18", temperature = 0.1)
alpha_vantage_api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")

class StockMarketSymbolSearchToolArgsSchema(BaseModel):
    query: str = Field(description="The query you will search for")

class StockMarketSymbolSearchTool(BaseTool):
    name: str = "StockMarketSymnbolSearchTool"
    description: str = """
    Use this tool to find the stock market symbol for a compnay. 
    It takes a query as an argument.
    Example query: Storck Market Symbol for Apple Company
    """
    args_schema: Type[StockMarketSymbolSearchToolArgsSchema] = StockMarketSymbolSearchToolArgsSchema

    def _run(self, query):
        ddg = DuckDuckGoSearchAPIWrapper()
        result = ddg.run(query)
        return result

class CompanyOverviewArgsSchema(BaseModel):
    symbol: str = Field(description="Stock symbol of the company. Example: AAPL, TSLA")

class CompnayOverviewTool(BaseTool):
    name: str = "CompnayOverviewTool"
    description: str = """ 
    Use this to get an overview of the financials of the company. 
    You should enter a stock symbol. 
    """

    def _run(self, symbol):
        r = requests.get(f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={symbol}&apikey={alpha_vantage_api_key}")
        return r.json()
    

class CompnayIncomeStatementTool(BaseTool):
    name: str = "CompnayIncomeStatementTool"
    description: str = """ 
    Use this to get an income statement of the company. 
    You should enter a stock symbol. 
    """

    def _run(self, symbol):
        r = requests.get(f"https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol={symbol}&apikey={alpha_vantage_api_key}")
        return r.json() #["annualReports"]


class CompnayStockPerformanceTool(BaseTool):
    name: str = "CompnayStockPerformanceTool"
    description: str = """ 
    Use this to get a weely performance of the company. 
    You should enter a stock symbol. 
    """

    def _run(self, symbol):
        r = requests.get(f"https://www.alphavantage.co/query?function=TIME_SERIES_WEEKLY&symbol={symbol}&apikey={alpha_vantage_api_key}")
        response = r.json()
        return list(response)
    
agent = initialize_agent(
    llm=llm,
    verbose=True,
    agent=AgentType.OPENAI_FUNCTIONS,
    handle_parsing_errors=True,
    tools=[
        StockMarketSymbolSearchTool(),
        CompnayOverviewTool(),
        CompnayIncomeStatementTool(),
        CompnayStockPerformanceTool()
    ],
    agent_kwargs={
        "system_message": SystemMessage(
            content="""
            You are a hedge fund manager.
            You evaluate a company and provide your opinion and reasons why the stock is a buy or not.
            Consider the performance of a stock, the company overview and the income statement.
            Be assertive in your judgement and recommend the stock or advise the user against it."""
            )
    }
)

company = st.text_input("Write the name of the company you are interested in")

if company:
    result = agent.invoke(company)
    st.write(result["output"].replace("$", "\$"))
