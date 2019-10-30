def duplicate_rows(uldk_response_rows):
    """Zabezpieczenie przed błędnym zwracaniem wielu takich samych obiektów"""
    if len(set(uldk_response_rows)) == 1:
        return [uldk_response_rows[0]]
    else:
        return uldk_response_rows