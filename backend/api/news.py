import os
import time
import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()

_cache: dict = {}
CACHE_TTL = 3600

@router.get('/news')
async def get_news():
    now = time.time()
    if _cache.get('ts') and now - _cache['ts'] < CACHE_TTL:
        return _cache['data']

    key = os.getenv('NEWSAPI_KEY')
    if not key:
        raise HTTPException(500, 'NEWSAPI_KEY not set')

    async with httpx.AsyncClient() as client:
        r = await client.get(
            'https://newsapi.org/v2/top-headlines',
            params={'category': 'business', 'language': 'en', 'pageSize': 6, 'apiKey': key},
        )

    if r.status_code != 200:
        raise HTTPException(502, 'NewsAPI error')

    articles = r.json().get('articles', [])
    result = [
        {'source': a['source']['name'], 'title': a['title'], 'url': a.get('url', '')}
        for a in articles
        if a.get('title') and '[Removed]' not in a['title']
    ][:6]

    _cache['data'] = result
    _cache['ts'] = now
    return result
