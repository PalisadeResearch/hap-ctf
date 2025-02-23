# hap-ctf

```
direnv allow
ninja
```

## API

```bash
uv run api
curl -X POST http://localhost:8000/run_code/ -H "Content-Type: multipart/form-data" -F "file=@submission.zip"
```
