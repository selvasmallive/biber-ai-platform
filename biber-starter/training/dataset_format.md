# BIBER Training Dataset Format

Use JSONL.

Each line:

```json
{
  "instruction": "Fix this Python FastAPI bug",
  "input": "Traceback or code here",
  "output": "Corrected code or patch here",
  "category": "python",
  "stack": ["python", "fastapi"],
  "quality": "verified"
}
```

Recommended categories:

- python
- react
- dotnet
- java
- rust
- mysql
- azure
- ffmpeg
- video
- audio
- proctoring

Important:
- Prefer verified examples with tests.
- Avoid private/customer code unless you have permission.
- Remove secrets.
