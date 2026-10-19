"""Allowlisted operational metadata only: never exception text, URLs, or payloads."""
import json
import logging
import os
import re
from time import perf_counter

import httpx
from postgrest.exceptions import APIError

logger = logging.getLogger(__name__)
CATEGORIES = frozenset(('timeout', 'transport', 'authentication', 'rate_limit',
                        'dependency_unavailable', 'request_denied', 'invalid_data',
                        'database', 'scan_failed', 'unexpected'))


def correlation_id(value=None):
    value = os.getenv('GITHUB_RUN_ID', '') if value is None else value
    return value if isinstance(value, str) and re.fullmatch(r'[0-9]{1,24}', value) else 'local'


def error_details(error):
    status = getattr(error, 'http_status', None)
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
    elif isinstance(error, APIError) and type(error.code) is int:
        # postgrest's fallback for a non-JSON HTTP error retains only this status.
        status = error.code
    status = status if type(status) is int and 100 <= status <= 599 else None
    category = getattr(error, 'category', None)
    if not isinstance(category, str) or category not in CATEGORIES:
        if isinstance(error, httpx.TimeoutException):
            category = 'timeout'
        elif isinstance(error, httpx.TransportError):
            category = 'transport'
        elif status in (401, 403):
            category = 'authentication'
        elif status == 429:
            category = 'rate_limit'
        elif status is not None and status >= 500:
            category = 'dependency_unavailable'
        elif status is not None and status >= 300:
            category = 'request_denied'
        elif isinstance(error, APIError):
            category = 'database'
        elif isinstance(error, (ValueError, TypeError, KeyError)):
            category = 'invalid_data'
        else:
            category = 'unexpected'
    error_class = getattr(error, 'error_class', None) or type(error).__name__
    if not isinstance(error_class, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', error_class):
        error_class = 'Exception'
    retries = getattr(error, 'retry_count', 0)
    retries = retries if type(retries) is int and 0 <= retries <= 10 else 0
    details = dict(category=category, error_class=error_class, http_status=status, retry_count=retries)
    if isinstance(error, APIError) and isinstance(error.code, str) and re.fullmatch(r'(?:[0-9A-Z]{5}|PGRST[0-9]{3})', error.code):
        details['database_code'] = error.code
    return details


def log_failure(stage, error, started, *, run_id=None, retry_count=None, will_retry=False):
    details = error_details(error)
    if retry_count is not None:
        details['retry_count'] = retry_count
    record = dict(stage=stage, run_id=correlation_id(run_id),
                  duration_ms=max(0, round((perf_counter()-started)*1000)),
                  will_retry=will_retry, **details)
    logger.log(logging.WARNING if will_retry else logging.ERROR,
               'FlyMind diagnostic: %s', json.dumps(record, sort_keys=True))
    return record
