"""Bind publication consent to the exact reviewed content and metadata."""

from hashlib import sha256
import json


def public_content_sha256(metadata: dict, markdown: str) -> str:
    data = dict(metadata)
    data['audit'] = dict(data['audit'])
    data['audit'].pop('public_content_sha256', None)
    encoded = json.dumps({'metadata': data, 'markdown': markdown}, ensure_ascii=False,
                         sort_keys=True, separators=(',', ':')).encode('utf-8')
    return sha256(encoded).hexdigest()
