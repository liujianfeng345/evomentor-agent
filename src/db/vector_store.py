"""ChromaDB 封装 —— 统一管理 embedding 的存储和检索。"""
import chromadb
from chromadb.config import Settings
from src.core.config import config


class VectorStore:
    def __init__(self) -> None:
        self.client = chromadb.PersistentClient(
            path=config.CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        self._ensure_collections()

    def _ensure_collections(self) -> None:
        names = [c.name for c in self.client.list_collections()]
        for col_name in [
            "conversation_embeddings",
            "experience_embeddings",
            "code_pattern_embeddings",
            "research_embeddings",
            "skill_embeddings",
        ]:
            if col_name not in names:
                self.client.create_collection(name=col_name)

    def add(self, collection: str, doc_id: str, text: str, metadata: dict | None = None) -> None:
        """将文本向量化存入指定集合。embedding 由 ChromaDB 内置函数自动生成。"""
        col = self.client.get_collection(name=collection)
        col.add(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata] if metadata else None,
        )

    def search(self, collection: str, query: str, n_results: int = 5) -> list[dict]:
        """语义检索：返回最相关的文档列表。"""
        col = self.client.get_collection(name=collection)
        results = col.query(query_texts=[query], n_results=n_results)
        items = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                items.append({
                    "id": doc_id,
                    "document": results["documents"][0][i] if results["documents"] else "",
                    "distance": results["distances"][0][i] if results["distances"] else 0.0,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                })
        return items

    def upsert(self, collection: str, doc_id: str, text: str, metadata: dict | None = None) -> None:
        """更新或插入向量，避免重复 ID 报错。"""
        col = self.client.get_collection(name=collection)
        col.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata] if metadata else None,
        )

    def delete(self, collection: str, doc_id: str) -> None:
        col = self.client.get_collection(name=collection)
        col.delete(ids=[doc_id])


vector_store = VectorStore()
