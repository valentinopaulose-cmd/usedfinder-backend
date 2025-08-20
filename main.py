from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, httpx

app = FastAPI(title="UsedFinder Backend", version="1.0")

app.add_middleware(CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

class Listing(BaseModel):
    title: str
    price: str | None = None
    url: str
    thumb: str | None = None
    location: str | None = None

ETSY_API_KEY = os.getenv("ETSY_API_KEY")

@app.get("/etsy", response_model=list[Listing])
async def etsy_search(q: str = Query(..., min_length=1), loc: str | None = None, limit: int = 24):
    if not ETSY_API_KEY:
        raise HTTPException(status_code=501, detail="ETSY_API_KEY not configured on server.")
    url = "https://openapi.etsy.com/v3/application/listings/active"
    params = {"keywords": q, "limit": min(max(limit, 1), 48), "includes": "images,shop",
              "sort_on": "score", "state": "active"}
    headers = {"x-api-key": ETSY_API_KEY, "accept": "application/json", "user-agent": "UsedFinder/1.0 (+iOS)"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, params=params, headers=headers)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=f"Etsy API error: {r.text[:256]}")
    data = r.json()
    raw = data.get("results") or data.get("listings") or []
    out = []
    for it in raw:
        lid = it.get("listing_id")
        page_url = f"https://www.etsy.com/listing/{lid}" if lid else (it.get("url") or "")
        price = None
        if isinstance(it.get("price"), dict):
            amt = it["price"].get("amount"); curr = it["price"].get("currency_code") or it["price"].get("currency")
            if amt is not None and curr:
                try: price = f"{curr} {float(amt)/100:.2f}"
                except: pass
        elif isinstance(it.get("price"), str):
            price = it["price"]
        images = it.get("images") or []
        thumb = None
        if images and isinstance(images, list):
            first = images[0]; thumb = first.get("url_fullxfull") or first.get("url_570xN") or first.get("url_170x135")
        shop = it.get("shop") or {}
        loc = shop.get("city") or shop.get("location")
        title = it.get("title") or "Etsy listing"
        if page_url:
            out.append(Listing(title=title, price=price, url=page_url, thumb=thumb, location=loc))
    return out

@app.get("/healthz")
async def health(): return {"ok": True}
