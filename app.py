from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from pydantic import BaseModel
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

import os

import uvicorn

load_dotenv()
debug_output = False
app = FastAPI()


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
                "role": "user",
                "content": f"My question is {question}. Can you make this question to cover broader. make three more additional questions so that my docs will not miss it."
            }
        ]
    )
    print("Updated question:"+response.choices[0].message.content)
    

    response2 = openai_client.chat.completions.create(
        model=AZURE_OPENAI_CHAT_DEPLOYMENT,
        messages=[
            {
                "role": "system",
                "content": "Answer ONLY from the provided context. If not found, say 'Not available in knowledge base.'"
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion:\n{response.choices[0].message.content}"
            }
        ]
    )
    debug_msg(response.choices)
    return response.choices[0].message.content

@app.post("/ask")
async def ask_question(req: QuestionRequest):
    print(req.question)
    context = retrieve_context(req.question)
    debug_msg("========Context=============")
    debug_msg(context)
    debug_msg("==========-------===========")
    answer = generate_answer(req.question, context)
    print("----------answere-----------")
    print(answer)

    return {
        "question": req.question,
        "answer": answer
    }


##############################################################################

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

def debug_msg(msg):
    if debug_output == True:
        print(msg)


def upload_ai_docs(client, file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    doc = {
        "id": str(uuid.uuid4()),
        "content": content
    }

    client.upload_documents(documents=[doc])
    print("TXT file uploaded")


@app.route("/upload", methods=["POST"])
def upload_ai_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)
    upload_ai_docs(search_client,filepath)
    debug_msg("File uploaded successfully")

    return jsonify({"message": f"File '{file.filename}' uploaded successfully"})

