from google.cloud import datastore
from .storage_base import Storage
from google_auth_oauthlib import flow

class DataStoreStorage(Storage):
    def __init__(self):
        appflow = flow.InstalledAppFlow.from_client_secrets_file(
            'client_secrets.json',
            scopes=['https://www.googleapis.com/auth/datastore'])

        appflow.run_local_server()

        credentials = appflow.credentials

        self.client = datastore.Client('cs131project-1558761929598', credentials=credentials)

    def put(self, key: str, value: bytes):
        entity = datastore.Entity(self.client.key(key))
        entity.update({'data': value})
        self.client.put(entity)

    def get(self, key: str) -> bytes:
        key = self.client.key(key)
        record = self.client.get(key)
        if record is None:
            return None
        return record['data']

    def exists(self, key: str) -> bool:
        key = self.client.key(key)
        record = self.client.get(key)
        if record is None:
            return False
        return True

    def remove(self, key: str) -> bool:
        key = self.client.key(key)
        self.client.delete(key)
        return True

    def get_key_list(self) -> list:
        key_list = list()
        query = self.client.query()
        query_iter = query.fetch()
        for entity in query_iter:
            key_list.append(entity.key)
        return key_list
