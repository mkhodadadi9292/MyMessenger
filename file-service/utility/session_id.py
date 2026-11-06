import uuid

def generate_session_id() -> str:
    return uuid.uuid4().hex
