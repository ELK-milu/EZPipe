import uvicorn
from typing import Union
from fastapi import FastAPI
import os
from fastapi_cdn_host import monkey_patch_for_docs_ui, AssetUrl

app = FastAPI()
monkey_patch_for_docs_ui(app,
    cdn_host = AssetUrl(
        js='http://my-cdn.com/swagger-ui.js',
        css='http://my-cdn.com/swagger-ui.css',
        redoc='http://my-cdn.com/redoc.standalone.js',
        favicon='http://my-cdn.com/favicon.ico',
    )
)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}

if __name__ == '__main__':
    name_app = os.path.splitext(os.path.basename(__file__))[0]
    uvicorn.run(app=f"{name_app}:app", host="0.0.0.0",port=3422)