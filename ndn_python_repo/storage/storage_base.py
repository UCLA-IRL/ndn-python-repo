class Storage:
    """
    Interface for storage functionalities
    """
    def put(self, key: bytes, data: bytes):
        raise NotImplementedError

    def get(self, key: bytes) -> bytes:
        raise NotImplementedError

    def exists(self, key: bytes) -> bool:
        raise NotImplementedError

    def remove(self, key: bytes) -> bool:
        raise NotImplementedError