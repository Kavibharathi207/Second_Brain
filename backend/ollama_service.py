"""
Ollama Integration Service
Handles communication with Ollama and Llama 3.1 model
"""

import requests
import json
from typing import Optional, Generator
from .config import config


class OllamaService:
    """Service for interacting with Ollama and local LLM"""

    def __init__(self, host: str = None, model: str = None):
        """
        Initialize Ollama service
        
        Args:
            host: Ollama host URL
            model: Model name to use
        """
        self.host = host or config.OLLAMA_HOST
        self.model = model or config.OLLAMA_MODEL
        self.embedding_model = config.OLLAMA_EMBEDDING_MODEL
        self.timeout = 120

    def check_connection(self) -> bool:
        """Check if Ollama is running"""
        try:
            response = requests.get(
                f"{self.host}/api/tags",
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Connection error: {str(e)}")
            return False

    def list_models(self) -> list:
        """Get list of available models"""
        try:
            response = requests.get(
                f"{self.host}/api/tags",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            return []
        except Exception as e:
            print(f"Error listing models: {str(e)}")
            return []

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 40,
        stream: bool = False
    ) -> str:
        """
        Generate text using Ollama
        
        Args:
            prompt: The prompt to generate from
            model: Model to use (defaults to configured model)
            temperature: Temperature for sampling
            top_p: Top-p sampling parameter
            top_k: Top-k sampling parameter
            stream: Whether to stream the response
            
        Returns:
            Generated text
        """
        if model is None:
            model = self.model

        try:
            url = f"{self.host}/api/generate"
            
            payload = {
                "model": model,
                "prompt": prompt,
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
                "stream": stream,
            }

            if stream:
                return self._stream_generate(url, payload)
            else:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    lines = response.text.split("\n")
                    full_response = ""
                    for line in lines:
                        if line.strip():
                            try:
                                data = json.loads(line)
                                full_response += data.get("response", "")
                            except:
                                pass
                    return full_response.strip()
                else:
                    return f"Error: {response.status_code}"
        except Exception as e:
            return f"Generation failed: {str(e)}"

    def _stream_generate(self, url: str, payload: dict) -> Generator[str, None, None]:
        """Stream generation response"""
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout,
                stream=True
            )

            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            yield data.get("response", "")
                        except:
                            pass
        except Exception as e:
            yield f"Streaming error: {str(e)}"

    def embed(self, text: str, model: Optional[str] = None) -> Optional[list]:
        """
        Generate embeddings for text
        
        Args:
            text: Text to embed
            model: Embedding model to use
            
        Returns:
            Embedding vector or None if failed
        """
        if model is None:
            model = self.embedding_model

        try:
            url = f"{self.host}/api/embeddings"
            
            payload = {
                "model": model,
                "prompt": text,
            }

            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("embedding")
            else:
                print(f"Embedding error: {response.status_code}")
                return None
        except Exception as e:
            print(f"Embedding failed: {str(e)}")
            return None

    def chat(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Chat with the model using message history
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use
            temperature: Temperature for sampling
            
        Returns:
            Model response
        """
        if model is None:
            model = self.model

        try:
            url = f"{self.host}/api/chat"
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "stream": False,
            }

            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("message", {}).get("content", "")
            else:
                return f"Error: {response.status_code}"
        except Exception as e:
            return f"Chat failed: {str(e)}"


# Global Ollama service instance
ollama_service = OllamaService()
