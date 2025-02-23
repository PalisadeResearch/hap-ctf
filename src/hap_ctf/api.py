import io
import zipfile

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from .run import load_zip_to_memory, run_sandboxed_code  # Import the existing functions

app = FastAPI()


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

        # Run the sandboxed code with the in-memory modules
        result = run_sandboxed_code(modules)

        return JSONResponse({"result": result})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def main():
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)


if __name__ == "__main__":
    main()
