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

## Docker

```bash
export HAP_CTF_IMAGE=$(docker load -q -i $(nix build --no-link --print-out-paths .#docker) | awk -F': ' '{print $2}')
docker run --rm -t $HAP_CTF_IMAGE
```
