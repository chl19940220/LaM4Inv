import os

from dotenv import load_dotenv


load_dotenv()


class Config:
    SMT_CHECK_TIME = 50

    Limited_time = 1800

    maxkinduction=True

    BMC = os.getenv("ENABLE_BMC", "0") == "1"

    Verification="esbmc"

    PROMPT="full"

    # OpenAI model name (e.g. gpt-5-mini, gpt-4o-mini, gpt-4o), or Llama3 / Man / Exist
    LLM=os.getenv("OPENAI_MODEL", "gpt-5-mini")

    timeout_seconds = 5
    
    maxkstep = 10

    resultpath="test"

    exsitresult="test"

config = Config()
