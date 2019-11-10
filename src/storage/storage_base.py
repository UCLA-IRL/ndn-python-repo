class Storage:
    """
    Interface for storage functionalities
    """
    def put(self, key: str, data: bytes):
        raise NotImplementedError

    def get(self, key: str) -> bytes:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError

    def remove(self, key: str) -> bool:
        raise NotImplementedError