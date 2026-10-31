"""Compare Windows extended paths without weakening directory containment."""
import re


def comparable_path(value):
    text=str(value)
    if text.startswith('\\\\?\\UNC\\'):
        return '\\\\'+text[8:]
    if text.startswith('\\\\?\\'):
        ordinary=text[4:]
        if not re.match(r'^[A-Za-z]:\\',ordinary):
            raise ValueError('Unsupported Windows device namespace')
        return ordinary
    return text
