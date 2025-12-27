from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify
import mysql.connector, time, sys, json
from datetime import date, datetime
from flask_session import Session

from pydantic import BaseModel
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

import os,uuid,json

import uvicorn

app = Flask(__name__)

load_dotenv()
debug_output = True


##############################################################################
openai_endpoint = "https://tejas-mj8ki4qk-eastus2.cognitiveservices.azure.com/"
search_endpoint="https://triam-ai-search.search.windows.net"
model_name = "text-embedding-3-small"
deployment = "text-embedding-3-small"
search_key=os.getenv("AI_SEARCH_KEY")
api_key=os.getenv("OPENAI_API_KEY")
AZURE_SEARCH_INDEX="rag-index"
AZURE_OPENAI_CHAT_DEPLOYMENT="gpt-4o-mini"

# Azure AI Search client
openai_client = AzureOpenAI(
    api_version="2024-12-01-preview",
    azure_endpoint=openai_endpoint,
    api_key=api_key
)

search_client = SearchClient(
    endpoint=search_endpoint,
    index_name=AZURE_SEARCH_INDEX,
    credential=AzureKeyCredential(search_key)
)

class QuestionRequest(BaseModel):
    question: str

def get_embedding(text: str):
    try:
        response = openai_client.embeddings.create(
            input=text,
            model=deployment
        )    
        return response.data[0].embedding
    except Exception as e:
        # A general handler for any other exception
        print(f"A embed exception error occurred:")
    
def retrieve_context(question: str, k: int = 3) -> str:
    debug_msg("retrieving")
    vector = get_embedding(question)
    debug_msg(vector)
    debug_msg("Debug2")
    results = search_client.search(
        search_text=question,
        vector_queries=[{
            "kind": "vector",
            "vector": vector,
            "k": k,
            "fields": "embedding"
        }],
        select=["content"]
    )

    debug_msg("debug3")
    retval = ""
    for r in results:
        debug_msg("==========")
        debug_msg(r)
        debug_msg("------")
        retval = retval + r["content"]
        debug_msg("==----------====")
    #tmp = "\n".join([r.content for r in results])
    debug_msg("====debug==========")
    print(retval)
    debug_msg("====-----==========")
    return retval

def generate_answer(question: str, context: str) -> str:
    response = openai_client.chat.completions.create(
        model=AZURE_OPENAI_CHAT_DEPLOYMENT,
        messages=[
            {
                "role": "system",
                "content": "Answer ONLY from the provided context. If not found, say 'Not available in knowledge base.'"
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion:\n{question}"
            }
        ]
    )
    debug_msg(response.choices)
    return response.choices[0].message.content

@app.route('/ask', methods=['GET', 'POST'])
def ask_question():
    if request.method == "POST":
        data = request.get_json()
        question = data.get("question")
        debug_msg("Question"+question)
        context = retrieve_context(question)
        answer = generate_answer(question, context)
        return jsonify({"question": question,"answer": answer})
            

@app.route('/triam-ai')
def triam_ai():
    return render_template("index.html")

def debug_msg(msg):
    if debug_output == True:
        print(msg)


def upload_ai_docs(client, file_path,openaiclient):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    embedding2 = openai_client.embeddings.create(
        model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        input=content
    ).data[0].embedding

    doc = {
        "id": "dms",
        "content": content,
        "embedding": embedding2
    }

    client.upload_documents(documents=[doc])
    print("TXT file uploaded")


@app.route('/update-ai-doc', methods=['GET', 'POST'])
def update_ai_doc():
    content = file.read()
    embedding2 = openai_client.embeddings.create(
        model=deployment,
        input=content
    ).data[0].embedding
    doc = {
        "id": "dms",
        "content": content,
        "embedding": embedding2
    }
    search_client.upload_documents(documents=[doc])
    print("TXT file uploaded")
    
    return jsonify({"message": "File uploaded successfully"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
