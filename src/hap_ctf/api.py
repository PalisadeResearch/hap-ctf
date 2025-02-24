import io
import multiprocessing
import zipfile
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from loguru import logger

from .config import Settings
from .run import load_zip_to_memory, run_sandboxed_code


@lru_cache
def get_settings():
    return Settings()


app = FastAPI()


def run_code_in_process(modules, result_queue):
    """Wrapper function to run code in a separate process and put result in a queue."""
    try:
        result = run_sandboxed_code(modules)
        result_queue.put(result)
    except Exception as e:
        result_queue.put(e)


@app.post("/run_code/")
async def run_code(
    file: UploadFile, settings: Annotated[Settings, Depends(get_settings)]
):
    logger.debug(f"/run_code file: {file.filename}, settings: {settings}")

    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are allowed")

    try:
        # Read the file into memory
        zip_data = io.BytesIO(await file.read())

        # Load modules from the zip data
        with zipfile.ZipFile(zip_data) as zip_ref:
            modules = load_zip_to_memory(zip_ref)

        ctx = multiprocessing.get_context("spawn")
        result_queue = ctx.Queue()
        process = ctx.Process(target=run_code_in_process, args=(modules, result_queue))
        process.start()
        process.join(timeout=settings.process_timeout)

        if process.is_alive():
            process.terminate()
            process.join()
            raise HTTPException(status_code=408, detail="Code execution timed out")

        # Get result from the queue.  It could be a successful result or an exception.
        result = result_queue.get()

        if isinstance(result, Exception):
            error_type = type(result).__name__
            error_msg = str(result)
            error_detail = f"{error_type}: {error_msg}"
            raise HTTPException(status_code=500, detail=error_detail) from result

        return JSONResponse({"result": result})

    except zipfile.BadZipFile as e:
        raise HTTPException(status_code=400, detail="Invalid zip file format") from e
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) from e


def main():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
