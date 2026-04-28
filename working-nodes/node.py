from fastapi import FastAPI

# This is the "app" variable that uvicorn is looking for!
app = FastAPI() 

@app.get("/")
def read_root():
    return {"message": "Hello from the Worker Node!"}