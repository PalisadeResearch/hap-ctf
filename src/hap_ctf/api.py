import io
import multiprocessing
import zipfile
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from .run import load_zip_to_memory, run_sandboxed_code

process_pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application."""
    # Initialize the process pool when the API starts
    global process_pool
    ctx = multiprocessing.get_context("spawn")
    process_pool = ctx.Pool(
        processes=4,
        maxtasksperchild=1,  # only use each process once
    )
    yield
    # Clean up the process pool when the API shuts down
    process_pool.close()
    process_pool.join()


app = FastAPI(lifespan=lifespan)


@app.post("/run_code/")
async def run_code(file: UploadFile):
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are allowed")

    try:
        # Read the file into memory
        zip_data = io.BytesIO(await file.read())

        # Load modules from the zip data
        with zipfile.ZipFile(zip_data) as zip_ref:
            modules = load_zip_to_memory(zip_ref)

        # Run the sandboxed code in a separate process
        global process_pool

        # Run the code with a timeout
        result = process_pool.apply_async(run_sandboxed_code, args=(modules,))
        try:
            final_result = result.get(timeout=60)
            return JSONResponse({"result": final_result})
        except multiprocessing.TimeoutError as e:
            raise HTTPException(
                status_code=408, detail="Code execution timed out"
            ) from e
        except Exception as e:
            # Extract the actual error from the worker process
            error_type = type(e).__name__
            error_msg = str(e)
            if "SyntaxError" in error_type:
                error_detail = f"SyntaxError: {error_msg}"
            elif "ValueError" in error_type and "No main() function found" in error_msg:
                error_detail = "No main() function found in __init__.py"
            else:
                error_detail = f"{error_type}: {error_msg}"
            raise HTTPException(status_code=500, detail=error_detail) from e

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
