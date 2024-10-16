from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from neo4j import GraphDatabase
import openai
import re
import sqlite3

app = FastAPI()

# Neo4j 和 OpenAI 配置
neo4j_driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "why53665"))
openai.api_key = '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'

# SQLite 数据库配置
DB_FILE = "interactions.db"
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()

# 创建日志表
c.execute('''CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT,
    response TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)''')
conn.commit()

KEYWORDS = [
    # 你的关键词列表
]

@app.post("/query/")
async def query_knowledge_graph(request: Request):
    data = await request.json()
    input_text = data.get("input_text")

    if not input_text:
        raise HTTPException(status_code=400, detail="Input text is required.")

    question_text = input_text
    prompt_text = f"请根据'{input_text}'生成一条详细的学习路径，包括关键知识点和资源。尽量包含以下关键词：{', '.join(KEYWORDS)}"

    # 使用 ChatGPT 生成学习路径
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt_text}]
    )
    chat_response = response.choices[0].message['content']

    # 存储日志
    c.execute("INSERT INTO logs (question, response) VALUES (?, ?)", (question_text, chat_response))
    conn.commit()

    # 从回答中提取关键词并查询知识图谱
    graph_content = ""
    for match in re.finditer(r'\b(' + '|'.join(KEYWORDS) + r')\b', chat_response):
        keyword = match.group(0)
        with neo4j_driver.session() as session:
            result = session.run(
                "MATCH (n) WHERE n.name = $name RETURN n.name AS name, n.description AS description",
                name=keyword
            ).single()
            if result:
                graph_content += f"节点: {result['name']}\n描述: {result['description']}\n\n"

    return {"response": chat_response, "graph_content": graph_content}

@app.get("/", response_class=HTMLResponse)
async def read_root():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>人工智能知识图谱查询与学习路径生成</title>
    </head>
    <body>
        <h1>人工智能知识图谱查询与学习路径生成</h1>
        <form id="queryForm">
            <input type="text" id="inputText" name="inputText" placeholder="请输入查询内容" required>
            <button type="submit">查询</button>
        </form>
        <h2>ChatGPT回答</h2>
        <pre id="chatResponse"></pre>
        <h2>知识图谱节点</h2>
        <pre id="graphContent"></pre>

        <script>
        document.getElementById("queryForm").addEventListener("submit", async function(event) {
            event.preventDefault();
            const inputText = document.getElementById("inputText").value;
            const response = await fetch("/query/", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({input_text: inputText})
            });
            const data = await response.json();
            document.getElementById("chatResponse").textContent = data.response;
            document.getElementById("graphContent").textContent = data.graph_content;
        });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
