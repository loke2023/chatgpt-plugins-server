import os
import uvicorn
from fastapi import FastAPI, File, HTTPException, Depends, Body, UploadFile 
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials 
from fastapi.staticfiles import StaticFiles
from services.openai import get_chat_completion_for_prompt
from services.openai import get_chat_completion
from services.openai import construct_prompt, construct_prompt_tips
from datastore.pgdatastore import *

from models.api import (
    DeleteRequest,
    DeleteResponse,
    QueryRequest,
    QueryResponse,
    UpsertRequest,
    UpsertResponse,
    LoginRequest,
)
from datastore.factory import get_datastore
from services.file import get_document_from_file
 

bearer_scheme = HTTPBearer()
os.environ['DATASTORE'] = 'milvus'
os.environ['BEARER_TOKEN'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'
os.environ['OPENAI_API_KEY'] = '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'
os.environ['OPENAI_API_BASE'] = 'https://api.openai.com/v1'
os.environ['MILVUS_HOST'] = '8.134.70.20'
os.environ['MILVUS_PORT'] = '19530'
os.environ['MILVUS_COLLECTION'] = 'lishiwenxueku'

BEARER_TOKEN = os.environ.get("BEARER_TOKEN")
assert BEARER_TOKEN is not None 

def validate_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if credentials.scheme != "Bearer" or credentials.credentials != BEARER_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    return credentials


app = FastAPI(dependencies=[Depends(validate_token)])
app.mount("/.well-known", StaticFiles(directory=".well-known"), name="static")

# Create a sub-application, in order to access just the query endpoint in an OpenAPI schema, found at http://0.0.0.0:8000/sub/openapi.json when the app is running locally
sub_app = FastAPI(
    title="Retrieval Plugin API",
    description="A retrieval API for querying and filtering documents based on natural language queries and metadata",
    version="1.0.0",
    servers=[{"url": "https://your-app-url.com"}],
    dependencies=[Depends(validate_token)],
)
app.mount("/sub", sub_app) 

@app.post(
    "/upsert-file",
    response_model=UpsertResponse,
)
async def upsert_file(
    file: UploadFile = File(...),
):
    document = await get_document_from_file(file)
    print(document)
    file_md5 = get_file_md5(file)
    #从数据库判断文档是否存在
    exist_embedding = await get_file_is_embedding(file_md5)
    #如果存在，则查询是否已经成功embedding, 如果成功embedding，则直接返回
    if exist_embedding:
        print("exist_embedding")
        return UpsertResponse(ids=exist_embedding)

    #如果不存在，则将文档数据写入数据库
    await insert_data_to_pg(file, file_md5, os.path.getsize(file), "gpt3.5")

    try:
        ids = await datastore.upsert([document])

        #embedding文档返回结果，更新数据库记录
        await update_file_embedding_result(file_md5, ids)

        return UpsertResponse(ids=ids)
    
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail=f"str({e})")


@app.post(
    "/upsert",
    response_model=UpsertResponse,
)
async def upsert(
    request: UpsertRequest = Body(...),
):
    try:
        ids = await datastore.upsert(request.documents)
        return UpsertResponse(ids=ids)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")

@app.post(
    "/embedding_chat",
    response_model=str,
)
async def embedding_chat(
    request: QueryRequest = Body(...),
):
    try:
        #收到请求先入库
        print("xxxx1")
        log_id = add_gpt_chat_log("root", "embedding_chat", "gpt3.5", request.queries[0].query)

        print("xxxx2")
        results = await datastore.query(
            request.queries,
        )

        print("xxxx3")
        print(results)
        #更新ebedding结果到记录值
        update_gpt_chat_log_embedding(log_id, results)
        print("xxxx4")
        same_thins = construct_prompt(results)
        print("same_thins:")
        print(same_thins) 

        chat_ret = get_chat_completion_for_prompt(same_thins, request.queries[0].query)
        print("chat_ret:")
        print(chat_ret)

        #更新chat结果到记录值
        update_gpt_chat_log_response(log_id, same_thins, chat_ret)

        return chat_ret
    
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")

@app.post(
    "/rewrite_manuscript",
    response_model=str,
)
async def rewrite_manuscript(
    request: QueryRequest = Body(...),
):
    try:
        #收到请求先入库
        log_id = add_gpt_chat_log("root", "rewrite_manuscript", "gpt3.5", request.queries[0].query)

        print("收到洗稿请求:")
        print(request.queries[0].query)

        results = await datastore.query(
            request.queries,
        )

        print("开始整理提示词 prompt, results:")
        print(results)
        #更新ebedding结果到记录值
        update_gpt_chat_log_embedding(log_id, results)

        same_thins = construct_prompt_tips(results, "作家", request.queries[0].query)
        print("rewrite_manuscript same_thins:")
        print(same_thins)

        chat_ret = get_chat_completion([{"role":"user", "content":same_thins}])
        print("rewrite_manuscript chat_ret:")
        print(chat_ret)

        #更新chat结果到记录值
        update_gpt_chat_log_response(log_id, same_thins, chat_ret)

        return chat_ret
    
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")

@app.post(
    "/query",
    response_model=QueryResponse,
)
async def query_main(
    request: QueryRequest = Body(...),
):
    try:
        results = await datastore.query(
            request.queries,
        )
        print(results)
        return QueryResponse(results=results)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@sub_app.post(
    "/query",
    response_model=QueryResponse,
    # NOTE: We are describing the shape of the API endpoint input due to a current limitation in parsing arrays of objects from OpenAPI schemas. This will not be necessary in the future.
    description="Accepts search query objects array each with query and optional filter. Break down complex questions into sub-questions. Refine results by criteria, e.g. time / source, don't do this often. Split queries if ResponseTooLargeError occurs.",
)
async def query(
    request: QueryRequest = Body(...),
):
    try:
        results = await datastore.query(
            request.queries,
        )
        return QueryResponse(results=results)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")

@app.delete(
    "/delete",
    response_model=DeleteResponse,
)
async def delete(
    request: DeleteRequest = Body(...),
):
    if not (request.ids or request.filter or request.delete_all):
        raise HTTPException(
            status_code=400,
            detail="One of ids, filter, or delete_all is required",
        )
    try:
        success = await datastore.delete(
            ids=request.ids,
            filter=request.filter,
            delete_all=request.delete_all,
        )
        return DeleteResponse(success=success)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.on_event("startup")
async def startup():
    global datastore
    datastore = await get_datastore()


def start():
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
