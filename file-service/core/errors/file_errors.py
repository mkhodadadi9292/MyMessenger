class HashStateMissingError(Exception):
    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"hash state missing for session_id={session_id}")
