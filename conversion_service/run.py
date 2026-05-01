import uvicorn

if __name__ == "__main__":
    # Для запуска сервиса конвертации на нужном порту
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=12345,
        reload=False,
        workers=1,
        log_level="info",
        access_log=True,
    )
