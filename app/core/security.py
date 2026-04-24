import hashlib
import hmac
from urllib.parse import parse_qs

from fastapi import HTTPException, status


def validate_init_data(init_data: str, bot_token: str) -> dict[str, str]:
    parsed = parse_qs(init_data, keep_blank_values=True)
    received_hash = parsed.pop("hash", [None])[0]

    if not received_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing hash in initData",
        )

    data_check_pairs = sorted(
        (k, v[0]) for k, v in parsed.items()
    )
    data_check_string = "\n".join(f"{k}={v}" for k, v in data_check_pairs)

    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    calculated_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid initData signature",
        )

    result: dict[str, str] = {k: v[0] for k, v in parsed.items()}
    return result
