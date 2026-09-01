import uvicorn
import sys
import os

if __name__ == "__main__":
    # Ensure project root is in python path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print("Starting PackAudit FastAPI server on http://127.0.0.1:8000 ...")
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
