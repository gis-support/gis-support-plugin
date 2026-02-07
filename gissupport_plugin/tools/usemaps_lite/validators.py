import re


def validate_email(email: str):
    """
    Prosty walidator maili.
    """

    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

    if re.match(pattern, email) is not None:
        return True

    return False
