"""Abstract base class for storage backends."""

from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """Abstract storage backend for file operations.

    Implementations: LocalStorageBackend, S3StorageBackend
    """

    @abstractmethod
    async def store(self, data: bytes, path: str) -> str:
        """Store file data at path.

        Args:
            data: File content as bytes
            path: Relative storage path

        Returns:
            Stored path (may differ from input if normalized)
        """
        ...

    @abstractmethod
    async def retrieve(self, path: str) -> bytes:
        """Retrieve file content.

        Args:
            path: Storage path

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        ...

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete file from storage.

        Args:
            path: Storage path

        Returns:
            True if deleted, False if the key was not found
        """
        ...

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if file exists.

        Args:
            path: Storage path

        Returns:
            True if exists
        """
        ...
