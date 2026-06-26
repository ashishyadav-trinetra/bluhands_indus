import os
import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

_logger = logging.getLogger(__name__)

router = APIRouter(tags=['Auth'])

# ── JWKS cache for ES256 tokens ───────────────────────────────────────────────
_JWKS_CACHE: dict = {}
_JWKS_FETCHED_AT: float = 0.0
_JWKS_TTL: float = 3600.0


def _get_supabase_jwks() -> dict:
    """Fetch and cache Supabase JWKS (used for ES256 token verification)."""
    global _JWKS_CACHE, _JWKS_FETCHED_AT
    now = time.monotonic()
    if _JWKS_CACHE and (now - _JWKS_FETCHED_AT) < _JWKS_TTL:
        return _JWKS_CACHE

    supabase_url = os.getenv('SUPABASE_URL', '').rstrip('/')
    if not supabase_url:
        _logger.warning('SUPABASE_URL not set — cannot fetch JWKS for ES256 verification')
        return {}

    jwks_url = f'{supabase_url}/auth/v1/.well-known/jwks.json'
    try:
        import json as _json
        import urllib.request
        with urllib.request.urlopen(jwks_url, timeout=5) as resp:
            data = _json.loads(resp.read())

        from jwt.algorithms import ECAlgorithm
        new_cache: dict = {}
        for jwk in data.get('keys', []):
            try:
                pub_key = ECAlgorithm.from_jwk(jwk)
                kid = jwk.get('kid', 'default')
                new_cache[kid] = pub_key
            except Exception as e:
                _logger.warning(f'Failed to load JWKS key: {e}')

        _JWKS_CACHE = new_cache
        _JWKS_FETCHED_AT = now
        return _JWKS_CACHE
    except Exception as e:
        _logger.warning(f'Failed to fetch JWKS from {jwks_url}: {e}')
        return _JWKS_CACHE  # return stale cache if available


def _decode_supabase_token(token: str) -> dict | None:
    import jwt

    # Peek at the header to pick the right verification path
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get('alg', 'HS256')
    except jwt.DecodeError as e:
        _logger.debug(f'Cannot read JWT header: {e}')
        return None

    # ── ES256 path: verify with EC public key from JWKS ───────────────────────
    if alg == 'ES256':
        kid = header.get('kid', 'default')
        jwks = _get_supabase_jwks()
        pub_key = jwks.get(kid) or (next(iter(jwks.values()), None) if jwks else None)
        if pub_key is None:
            _logger.warning('No ES256 public key available from JWKS')
            return None
        try:
            return jwt.decode(
                token,
                pub_key,
                algorithms=['ES256'],
                options={'verify_exp': True, 'verify_aud': False},
            )
        except jwt.ExpiredSignatureError:
            _logger.debug('Supabase ES256 token expired')
            return None
        except jwt.InvalidTokenError as e:
            _logger.debug(f'Invalid Supabase ES256 token: {e}')
            return None

    # ── HS256 path: verify with SUPABASE_JWT_SECRET ───────────────────────────
    jwt_secret = os.getenv('SUPABASE_JWT_SECRET')
    if not jwt_secret:
        return None
    try:
        return jwt.decode(
            token,
            jwt_secret,
            algorithms=['HS256'],
            options={'verify_exp': True, 'verify_aud': False},
        )
    except jwt.ExpiredSignatureError:
        _logger.debug('Supabase token expired')
        return None
    except jwt.InvalidTokenError as e:
        _logger.debug(f'Invalid Supabase token: {e}')
        return None


@router.post('/api/authenticate')
async def authenticate(request: Request):
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return JSONResponse(status_code=401, content={'detail': 'Not authenticated'})
    token = auth_header[7:]
    payload = _decode_supabase_token(token)
    if payload is None:
        return JSONResponse(status_code=401, content={'detail': 'Not authenticated'})
    return JSONResponse(status_code=200, content={'authenticated': True})


@router.post('/api/logout')
async def logout():
    return JSONResponse(status_code=200, content={'message': 'Logged out'})


@router.post('/api/auth/sync-user')
async def sync_user(request: Request):
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return JSONResponse(status_code=401, content={'detail': 'Not authenticated'})
    token = auth_header[7:]
    payload = _decode_supabase_token(token)
    if payload is None:
        # In OSS mode there's no user DB to sync — just accept auth'd requests
        return JSONResponse(status_code=200, content={'message': 'User synced'})
    return JSONResponse(status_code=200, content={'message': 'User synced'})
