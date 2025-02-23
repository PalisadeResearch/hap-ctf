import io
import multiprocessing
import zipfile

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from .run import load_zip_to_memory, run_sandboxed_code

app = FastAPI()

process_pool = None


@app.on_event("startup")
async def startup_event():
    """Initialize the process pool when the API starts."""
    global process_pool
    process_pool = multiprocessing.Pool(
        processes=4,
        maxtasksperchild=1,  # only use each process once
    )


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up the process pool when the API shuts down."""
    global process_pool
    process_pool.close()
    process_pool.join()


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
        raise HTTPException(status_code=500, detail=str(e)) from e


def main():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
