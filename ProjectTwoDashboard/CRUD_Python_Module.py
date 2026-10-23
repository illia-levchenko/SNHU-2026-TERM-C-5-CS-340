"""Reusable MongoDB CRUD operations for the Austin Animal Center database."""

from bson.errors import InvalidDocument
from pymongo import MongoClient
from pymongo.errors import PyMongoError


class AnimalShelter:
    """Connect to a MongoDB collection and create, read, update, or delete data.

    Credentials are supplied by the caller. The defaults match the Codio
    project environment; other connection settings can be supplied as needed.
    """

    def __init__(self, username, password, host="localhost", port=27017,
                 database="aac", collection="animals", auth_source="admin"):
        """Open an authenticated connection; raise if configuration or login fails.

        ``auth_source`` is the database where the MongoDB user was created.
        It can differ from the database containing the animal documents.
        """
        if not isinstance(username, str) or not username.strip():
            raise ValueError("A nonempty MongoDB username is required.")
        if not isinstance(password, str) or not password:
            raise ValueError("A nonempty MongoDB password is required.")

        self.client = MongoClient(
            host=host,
            port=port,
            username=username,
            password=password,
            authSource=auth_source,
            serverSelectionTimeoutMS=5000,
        )
        try:
            # MongoClient connects lazily; ping detects login/connection errors now.
            self.client.admin.command("ping")
            self.database = self.client[database]
            self.collection = self.database[collection]
        except (PyMongoError, TypeError, ValueError):
            self.client.close()
            raise

    def create(self, data):
        """Insert one nonempty dictionary; return True on success, else False."""
        if not isinstance(data, dict) or not data:
            return False
        try:
            return self.collection.insert_one(data).acknowledged
        except (PyMongoError, InvalidDocument, TypeError, ValueError):
            return False

    def read(self, query):
        """Return matching documents as a list, or [] for no matches/errors.

        An empty dictionary is allowed and reads every document. Materializing
        the find cursor here also catches errors raised during cursor iteration.
        """
        if not isinstance(query, dict):
            return []
        try:
            return list(self.collection.find(query))
        except (PyMongoError, InvalidDocument, TypeError, ValueError):
            return []

    def update(self, query, update_data):
        """Update all matches and return the number of documents changed.

        ``update_data`` is a MongoDB update document, for example
        {"$set": {"name": "Buddy"}}. A no-op, no match, or error returns 0.
        An empty query is rejected to prevent an accidental collection-wide edit.
        """
        if not isinstance(query, dict) or not query:
            return 0
        if not isinstance(update_data, dict) or not update_data:
            return 0
        try:
            return self.collection.update_many(query, update_data).modified_count
        except (PyMongoError, InvalidDocument, TypeError, ValueError):
            return 0

    def delete(self, query):
        """Delete all matches and return their count; return 0 on no match/error.

        An empty query is rejected to prevent an accidental collection-wide delete.
        """
        if not isinstance(query, dict) or not query:
            return 0
        try:
            return self.collection.delete_many(query).deleted_count
        except (PyMongoError, InvalidDocument, TypeError, ValueError):
            return 0

    def close(self):
        """Release the MongoDB client's resources when finished."""
        self.client.close()
