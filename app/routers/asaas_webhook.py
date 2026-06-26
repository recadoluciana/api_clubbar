@router.post("/webhook")
async def asaas_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        body = await request.json()
    except Exception:
        body = {}

    print("[ASAAS WEBHOOK]")
    print(body)

    return {"ok": True}